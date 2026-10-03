"""Private external-run integrity checks and a fail-closed metered transport.

The predictor never parses the label file. No API call is made by preflight.
The existing review prompts and label-decision pipeline are not modified.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, TextIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
INPUT_FIELDS = {"case_id", "housing_type", "clause_text"}


def byte_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def safe_member(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and not Path(relative).is_absolute(), "Invalid relative path")
    target = (root / relative).resolve()
    require(target.is_relative_to(root.resolve()) and target != root.resolve(), "Bundle path escapes root")
    return target


def runtime_files(repo: Path) -> list[Path]:
    return sorted([
        *(repo / "src").glob("*.py"), repo / "scripts/run_frozen_external.py",
        repo / "requirements.txt",
    ])


def verify_bundle(bundle: Path, repo: Path) -> dict:
    manifest = read_json(bundle / "manifest.json")
    require(manifest.get("status") == "labels_confirmed_api_authorization_pending", "Unexpected freeze status")
    require(manifest.get("hash_method") == "sha256_exact_bytes", "Unknown hash method")
    require(manifest.get("case_count") == 20, "This run requires exactly 20 cases")
    for entry in manifest["artifacts"]:
        target = safe_member(bundle, entry["path"])
        require(byte_hash(target) == entry["sha256"], f"Frozen artifact changed: {entry['path']}")
    locked_code = manifest["runtime_files"]
    expected_paths = {entry["repo_path"] for entry in locked_code}
    actual_paths = {path.relative_to(repo).as_posix() for path in runtime_files(repo)}
    require(expected_paths == actual_paths, "Runtime file set changed; do not silently reuse this freeze")
    for entry in locked_code:
        require(byte_hash(safe_member(repo, entry["repo_path"])) == entry["sha256"],
                f"Runtime code changed: {entry['repo_path']}")
    cases = read_json(safe_member(bundle, manifest["input_path"]))
    expected_ids = [f"NEW_{number:02d}" for number in range(1, 21)]
    require(isinstance(cases, list) and [row.get("case_id") for row in cases] == expected_ids,
            "Expected 20 ordered unique NEW case IDs")
    for case in cases:
        require(set(case) == INPUT_FIELDS, "Sanitized input includes annotation or unexpected fields")
        require(case["housing_type"] in {"HDB", "Private Residential"}, "Invalid housing type")
        require(isinstance(case["clause_text"], str) and 0 < len(case["clause_text"]) <= 20000,
                "Empty or unbounded case text")
    require(sum(case["housing_type"] == "HDB" for case in cases) == 10, "Housing balance changed")
    config = read_json(safe_member(bundle, manifest["configuration_path"]))
    require(config["models"] == {"draft": "openai/gpt-4.1", "verifier": "openai/gpt-4o"},
            "Unexpected model configuration")
    require(config["retrieval_limit"] == 4, "Retrieval configuration changed")
    require(type(config["max_model_calls"]) is int and 1 <= config["max_model_calls"] <= 40,
            "Invalid call cap")
    require(type(config["max_total_tokens"]) is int and 1000 <= config["max_total_tokens"] <= 200000,
            "Invalid token cap")
    require(Decimal("0") < Decimal(config["max_cost_usd"]) <= Decimal("1.00"), "Invalid dollar cap")
    return {"manifest": manifest, "config": config, "cases": cases,
            "manifest_sha256": byte_hash(bundle / "manifest.json")}


def verify_authorization(path: Path | None, manifest_hash: str, config: dict) -> dict:
    require(path is not None, "A new human authorization record is required for this batch")
    approval = read_json(path)
    require(approval.get("bundle_manifest_sha256") == manifest_hash, "Authorization is for another freeze")
    for field in ("synthetic_no_personal_data_confirmed", "send_to_openrouter_approved"):
        require(approval.get(field) is True, f"Missing human confirmation: {field}")
    require(approval.get("approved_by") == "project_owner"
            and bool(approval.get("authorization_message", "").strip())
            and bool(approval.get("authorized_at_utc", "").strip()), "Incomplete authorization record")
    approved = Decimal(str(approval.get("max_cost_usd", "0")))
    require(approved >= Decimal(config["max_cost_usd"]), "Authorized dollar cap is too low")
    return approval


class BudgetStop(RuntimeError):
    """Stop before another charge, retaining all already-written run artifacts."""


def fetch_completion_body(payload: dict, api_key: str) -> dict:
    request = Request(
        ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "X-Title": "Singapore Rental Contract Review frozen external evaluation"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"OpenRouter returned HTTP {error.code}; no automatic retry.") from None
    except (URLError, TimeoutError, json.JSONDecodeError):
        raise RuntimeError("OpenRouter request failed; charge may be unknown; no automatic retry.") from None
    if not isinstance(body, dict):
        raise RuntimeError("OpenRouter returned an invalid response body; stop without retry.")
    return body


class MeteredTransport:
    def __init__(self, config: dict, log: TextIO, request: Callable = fetch_completion_body):
        self.config, self.log, self.request = config, log, request
        self.calls = self.prompt_tokens = self.completion_tokens = self.total_tokens = 0
        self.cost = Decimal("0")
        self.case_id = ""
        self.stopped = False
        self.unaccounted_attempt = False

    def write_event(self, event: dict) -> None:
        self.log.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.log.flush()

    def reservation(self, payload: dict) -> tuple[dict, int, Decimal]:
        model = payload.get("model")
        require(model in self.config["prices"], "Unapproved model")
        price = self.config["prices"][model]
        completion_cap = price["max_completion_tokens"]
        require(type(payload.get("max_tokens")) is int and 0 < payload["max_tokens"] <= completion_cap,
                "Unapproved completion limit")
        require(payload.get("temperature") == 0, "Unapproved sampling configuration")
        require(set(payload) == {"model", "temperature", "max_tokens", "messages", "response_format"},
                "Unexpected request fields, tools or routing")
        bounded = copy.deepcopy(payload)
        bounded["stream"] = False
        bounded["provider"] = {
            "only": ["openai"], "allow_fallbacks": False, "require_parameters": True,
            "data_collection": "deny",
            "max_price": {"prompt": float(price["input_usd_per_million"]),
                          "completion": float(price["output_usd_per_million"]), "request": 0},
        }
        # UTF-8 byte count includes the schema and is deliberately conservative;
        # add a framing reserve, rather than claiming an exact token prediction.
        prompt_reserve = len(json.dumps(bounded, ensure_ascii=False).encode("utf-8")) + 1024
        token_reserve = prompt_reserve + payload["max_tokens"]
        cost_reserve = (Decimal(prompt_reserve) * Decimal(price["input_usd_per_million"])
                        + Decimal(payload["max_tokens"]) * Decimal(price["output_usd_per_million"])) / 1000000
        return bounded, token_reserve, cost_reserve

    def __call__(self, payload: dict, api_key: str):
        if self.stopped:
            raise BudgetStop("Meter already stopped; no further calls permitted")
        bounded, token_reserve, cost_reserve = self.reservation(payload)
        if (self.calls >= self.config["max_model_calls"]
                or self.total_tokens + token_reserve > self.config["max_total_tokens"]
                or self.cost + cost_reserve > Decimal(self.config["max_cost_usd"])):
            self.stopped = True
            raise BudgetStop("Before-call budget stop: partial output preserved")
        self.calls += 1
        self.unaccounted_attempt = True
        self.write_event({
            "event": "attempt", "case_id": self.case_id, "call_number": self.calls,
            "model": bounded["model"], "reserved_tokens": token_reserve,
            "reserved_cost_usd": str(cost_reserve),
            "request_sha256": hashlib.sha256(json.dumps(bounded, ensure_ascii=False,
                                                      sort_keys=True).encode("utf-8")).hexdigest(),
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        try:
            body = self.request(bounded, api_key)
            self.write_event({"event": "response", "case_id": self.case_id,
                              "call_number": self.calls, "body": body})
            usage = body.get("usage")
            require(isinstance(usage, dict), "Missing provider usage")
            for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
                require(type(usage.get(field)) is int and usage[field] >= 0, "Invalid provider token usage")
            require(usage["total_tokens"] > 0
                    and usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"],
                    "Inconsistent provider token usage")
            require(type(usage.get("cost")) in {int, float, str}, "Missing provider cost")
            cost = Decimal(str(usage["cost"]))
            require(cost.is_finite() and cost >= 0, "Invalid provider cost")
            self.prompt_tokens += usage["prompt_tokens"]
            self.completion_tokens += usage["completion_tokens"]
            self.total_tokens += usage["total_tokens"]
            self.cost += cost
            self.unaccounted_attempt = False
            require(not usage.get("is_byok"), "Unexpected BYOK: account credits do not measure all charges")
            if (usage["total_tokens"] > token_reserve or cost > cost_reserve
                    or self.total_tokens > self.config["max_total_tokens"]
                    or self.cost > Decimal(self.config["max_cost_usd"])):
                raise BudgetStop("Provider accounting exceeded reservation; no further calls permitted")
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content) if isinstance(content, str) else content
            require(isinstance(parsed, dict), "Invalid JSON completion")
            return parsed, {key: usage[key] for key in
                            ("prompt_tokens", "completion_tokens", "total_tokens")}
        except Exception as error:
            self.stopped = True
            self.write_event({"event": "stop", "case_id": self.case_id, "call_number": self.calls,
                              "error_type": type(error).__name__,
                              "unaccounted_attempt": self.unaccounted_attempt})
            raise

    def accounting(self) -> dict:
        return {"api_calls": self.calls, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "total_tokens": self.total_tokens,
                "cost_usd": str(self.cost), "unaccounted_attempt": self.unaccounted_attempt}
