"""Stateless, offline-only cloud adapter. The existing predictor is unchanged."""
from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from starlette.concurrency import run_in_threadpool

from src.application import (
    Clause, MAX_BYTES, MAX_CHARS, extract_pdf, load_retriever, run_document, safety_issue,
)
from src.official_sources import load_official_index

ROOT = Path(__file__).resolve().parent
Housing = Literal["HDB", "Private Residential"]
Version = Literal["v17", "v18"]
BODY_LIMIT = 500_000
app = FastAPI(title="Singapore Rental Contract Review — offline demo",
              docs_url=None, redoc_url=None, openapi_url=None)


class ClauseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    clause_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    text: str = Field(min_length=1, max_length=6000)
    pages: list[Annotated[int, Field(strict=True, ge=1, le=20)]] = Field(default_factory=list, max_length=20)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    housing_type: Housing
    review_version: Version = "v17"
    synthetic_confirmed: StrictBool
    extraction_confirmed: StrictBool
    clauses: list[ClauseInput] = Field(min_length=1, max_length=20)


@app.middleware("http")
async def secure_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Do not echo submitted text, identifiers, provider bodies or local paths.
    return JSONResponse({"detail": "Invalid request. Check field types and limits."}, status_code=422)


async def limited_body(request: Request, limit: int) -> bytes:
    length = request.headers.get("content-length")
    if length:
        try:
            parsed = int(length)
        except ValueError:
            raise HTTPException(400, "Invalid content length.") from None
        if parsed < 0 or parsed > limit:
            raise HTTPException(413, "Request exceeds the size limit.")
    parts, total = [], 0
    async for part in request.stream():
        total += len(part)
        if total > limit:
            raise HTTPException(413, "Request exceeds the size limit.")
        parts.append(part)
    return b"".join(parts)


@lru_cache(maxsize=1)
def source_status():
    # Cached only for this immutable deployment; changed sources need a new build.
    templates = load_retriever()
    official = load_official_index(ROOT)
    return {"template_sections": len(templates.chunks), "official_sections": len(official)}


@app.get("/api/health")
def health():
    try:
        counts = source_status()
    except (ValueError, OSError, KeyError):
        raise HTTPException(503, "Pinned references unavailable. Rebuild and verify sources.") from None
    return {"status": "ok", "mode": "offline", "live_enabled": False, "model_api_calls": 0, **counts}


@app.get("/api/config")
def config():
    with (ROOT / "data/source_registry.csv").open(encoding="utf-8", newline="") as file:
        sources = [{"source_id": s["source_id"], "title": s["title"], "url": s["url"],
                    "kind": s["source_kind"], "housing_type": s["housing_type"]}
                   for s in csv.DictReader(file) if s["source_kind"] == "tenancy_agreement_template"]
    registry = json.loads((ROOT / "data/official_reference_registry_v18.json").read_text(encoding="utf-8"))
    sources += [{"source_id": s["source_id"], "title": s["title"], "url": s["url"],
                 "kind": s["source_kind"], "housing_type": s["housing_type"]} for s in registry["sources"]]
    examples = json.loads((ROOT / "data/demo_examples.json").read_text(encoding="utf-8"))
    return {
        "mode": "offline", "live_enabled": False, "examples": examples, "sources": sources,
        "privacy": "Synthetic input is sent to the hosting server, not a model API. "
                   "The application does not save it to disk. Hosting infrastructure may retain operational logs. "
                   "Identifier detection is incomplete; never upload real contracts.",
        "v18_status": "Unmeasured source-expanded experiment. Offline execution still uses historical local rules."
    }


@app.post("/api/review")
async def review(request: Request):
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(415, "Send application/json.")
    payload = await limited_body(request, BODY_LIMIT)
    try:
        data = ReviewInput.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid request. Check confirmations, field types and limits.") from None
    if len({c.clause_id for c in data.clauses}) != len(data.clauses):
        raise HTTPException(422, "Clause IDs must be unique.")
    if sum(len(c.text) for c in data.clauses) > MAX_CHARS:
        raise HTTPException(413, "Selected text exceeds 80,000 characters.")
    clauses = [Clause(c.clause_id, tuple(c.pages), c.text) for c in data.clauses]
    try:
        report = await run_in_threadpool(
            run_document, clauses, data.housing_type,
            synthetic_confirmed=data.synthetic_confirmed, extraction_confirmed=data.extraction_confirmed,
            live=False, spending_confirmed=False, review_version=data.review_version,
        )
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    except Exception:
        raise HTTPException(503, "Review unavailable. Verify the deployment references.") from None
    if report["accounting"]["api_calls"] != 0:
        raise HTTPException(503, "Offline invariant failed; no result released.")
    report["deployment"] = "Public offline demonstration; no model inference"
    return report


@app.post("/api/extract")
async def extract(request: Request, housing_type: Housing):
    if request.headers.get("x-synthetic-confirmed") != "true":
        raise HTTPException(400, "Confirm synthetic data before sending a PDF.")
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/pdf":
        raise HTTPException(415, "Send a readable application/pdf.")
    payload = await limited_body(request, MAX_BYTES)
    try:
        clauses = await run_in_threadpool(extract_pdf, payload)
        issue = safety_issue("\n".join(c.text for c in clauses), housing_type)
        if issue:
            raise ValueError(issue)
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    return {"clauses": [{"clause_id": c.clause_id, "pages": c.pages, "text": c.text} for c in clauses],
            "scope": "Provisional fragments. Check conditions and exceptions against the input PDF."}


@app.get("/api/demo-pdf/{number}")
def demo_pdf(number: Annotated[int, Field(ge=1, le=5)]):
    # Fixed synthetic files only; no arbitrary path or filesystem browsing route.
    return FileResponse(ROOT / f"data/demo_pdfs/demo_{number:02d}.pdf",
                        media_type="application/pdf", filename=f"synthetic_demo_{number:02d}.pdf")


@app.get("/")
def home():
    return FileResponse(ROOT / "public/index.html", media_type="text/html")


@app.get("/app.js")
def javascript():
    return FileResponse(ROOT / "public/app.js", media_type="application/javascript")


@app.get("/styles.css")
def stylesheet():
    return FileResponse(ROOT / "public/styles.css", media_type="text/css")
