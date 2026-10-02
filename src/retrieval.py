"""Housing-type and topic-aware BM25 retrieval over CEA agreement clauses."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it",
    "of", "on", "or", "that", "the", "this", "to", "with", "will", "shall", "tenant",
    "landlord", "agreement", "premises", "flat",
}


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOP_WORDS]


def query_topics(query: str) -> set[str]:
    """Collect independent obligations; do not stop at the first topic keyword.

    Deposit sizing, set-off and deduction lists do not by themselves introduce
    separate rent, repair or utility obligations. Notice/cure within those
    processes is not automatically a tenancy-termination topic.
    """
    topics: set[str] = set()
    process_context: str | None = None
    for sentence in re.split(r"(?<=[.;])\s+", query.lower()):
        deposit = bool(re.search(r"\b(?:deposit\w*|deduct\w*|refund\w*)\b", sentence))
        repair = bool(re.search(r"\b(?:repair\w*|structural|plumbing|wiring|maintenance(?! fee))\b", sentence))
        termination = bool(re.search(r"\bterminat\w*\b|\bend (?:the |this )?(?:tenancy|agreement)\b", sentence))
        # A refund at expiry/termination describes deposit settlement, not an exit right.
        if deposit and re.search(r"\brefund\w*\b", sentence) and not re.search(
            r"\b(?:may|can|shall|will)\s+(?:also\s+)?(?:end|terminate)\b|\bterminates? early\b", sentence
        ):
            termination = False
        if deposit:
            topics.add("security_deposit")
        if repair and (not deposit or re.search(r"\bresponsib\w*\b|\bmaintain\w*\b|\b(?:cap|limit)\b", sentence)):
            topics.add("minor_repair")
        service_method = re.search(r"\b(?:notice|notices)\b[^.;]*\b(?:served|deliver\w*|post\w*|emoji|email|whatsapp)\b", sentence)
        procedural_notice = not deposit and not repair and re.search(r"\b(?:notice|breach|emoji)\b", sentence)
        if termination or service_method or (procedural_notice and process_context not in {"security_deposit", "minor_repair"}):
            topics.add("termination_notice")
        if re.search(r"\b(?:occup\w*|resid\w*|sublet\w*|sub-?tenant\w*|assign\w*|guest\w*|anyone|people|immigration|foreign)\b", sentence):
            # Owner occupation mentioned as an exit ground is still a termination issue.
            if not termination or re.search(r"\b(?:tenant|sublet\w*|immigration|foreign)\b", sentence):
                topics.add("occupancy_subletting")
        incidental_payment = deposit and not re.search(
            r"\bfirst month\S* rent\b|\brent continues\b|\b(?:additional|increased|higher|extra) (?:monthly )?rent\b|"
            r"\b(?:rent|utilities|utility charges)\s+(?:shall |must |is )?(?:be )?(?:paid|payable|due)\b", sentence
        )
        if not incidental_payment:
            if re.search(r"\b(?:utilit\w*|water|electric\w*|gas|sewer\w*)\b", sentence) and not repair:
                topics.add("utilities")
            if re.search(r"\b(?:rent|late|fees?)\b", sentence) or (not topics and "charge" in sentence):
                topics.add("rent")
        if termination:
            process_context = "termination_notice"
        elif deposit:
            process_context = "security_deposit"
        elif repair:
            process_context = "minor_repair"
    return topics


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    housing_type: str
    source_kind: str
    title: str
    page_number: int
    section: str
    text: str
    score: float
    clause_id: str = ""
    topics: tuple[str, ...] = ()


class LocalBM25Retriever:
    """A dependency-free BM25 retriever that never mixes housing types."""

    def __init__(self, chunks: Iterable[dict[str, object]]) -> None:
        self.chunks = list(chunks)
        self.term_frequencies = [Counter(tokenize(str(chunk["text"]))) for chunk in self.chunks]
        self.document_frequencies: Counter[str] = Counter()
        for frequencies in self.term_frequencies:
            self.document_frequencies.update(frequencies.keys())
        self.lengths = [sum(frequencies.values()) for frequencies in self.term_frequencies]
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 1.0

    @classmethod
    def from_jsonl(cls, path: Path) -> "LocalBM25Retriever":
        with path.open(encoding="utf-8") as file:
            return cls(json.loads(line) for line in file if line.strip())

    def search(self, query: str, housing_type: str, limit: int = 4) -> list[RetrievedChunk]:
        if housing_type not in {"HDB", "Private Residential"} or limit < 1:
            return []

        query_terms = tokenize(query)
        if not query_terms:
            return []
        desired_topics = query_topics(query)

        corpus_size = len(self.chunks)
        candidates: list[RetrievedChunk] = []
        for index, chunk in enumerate(self.chunks):
            if chunk["housing_type"] != housing_type or chunk["source_kind"] != "tenancy_agreement_template":
                continue
            if desired_topics and not desired_topics.intersection(chunk.get("topics", [])):
                continue

            frequencies = self.term_frequencies[index]
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                document_frequency = self.document_frequencies[term]
                inverse_document_frequency = math.log(1 + (corpus_size - document_frequency + 0.5) / (document_frequency + 0.5))
                denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * self.lengths[index] / self.average_length)
                score += inverse_document_frequency * frequency * 2.5 / denominator

            chunk_topics = set(chunk.get("topics", []))
            if desired_topics & chunk_topics:
                score += 5.0
            lowered = str(chunk["text"]).lower()
            query_lowered = query.lower()
            if re.search(r"\b(late|overdue)\b", query_lowered) and "default in rent" in lowered:
                score += 3.0
            if re.search(r"\b(change|adjust|increase)\b", query_lowered) and "rental amount" in lowered:
                score += 2.0
            if "occupancy_subletting" in desired_topics and re.search(r"\b(anyone|people|resid\w*|occup\w*)\b", query_lowered) and chunk.get("clause_id") == "1.1":
                score += 5.0
            if "occupancy_subletting" in desired_topics and re.search(r"\b(named|names?|listed)\b", query_lowered) and chunk.get("clause_id") == "ITEM6":
                score += 10.0
            if "rent" in desired_topics and re.search(r"\b(payable|monthly|advance)\b", query_lowered) and chunk.get("clause_id") in {"1.3", "1.4", "2.1"}:
                score += 4.0
            if "notice" in query_lowered and "service of notices" in lowered:
                score += 2.0
            if re.search(r"\b(end|terminate|termination)\b", query_lowered) and "right to terminate" in lowered:
                score += 2.0
            if "termination_notice" in desired_topics and "right to terminate" in lowered:
                score += 4.0
                if "terminated by the landlord in writing" in lowered and not re.search(r"\b(?:destroy\w*|damage\w*)\b", query_lowered):
                    score += 8.0
            if re.search(r"\b(?:sublet\w*|assign\w*)\b", query_lowered) and "sublet" in lowered:
                # Prefer the parent covenant with its 'will not' over a bare d) fragment.
                score += 8.0 if re.search(r"\btenant\b.{0,35}\bwill not\b", lowered) else 3.0

            if score > 0:
                candidates.append(
                    RetrievedChunk(
                        source_id=str(chunk["source_id"]),
                        housing_type=str(chunk["housing_type"]),
                        source_kind=str(chunk["source_kind"]),
                        title=str(chunk["title"]),
                        page_number=int(chunk["page_number"]),
                        section=str(chunk["section"]),
                        text=str(chunk["text"]),
                        score=round(score, 6),
                        clause_id=str(chunk.get("clause_id", "")),
                        topics=tuple(chunk.get("topics", [])),
                    )
                )

        ranked = sorted(candidates, key=lambda item: (-item.score, item.source_id, item.page_number))
        selected: list[RetrievedChunk] = []
        for topic in sorted(desired_topics):
            match = next((item for item in ranked if topic in item.topics and item not in selected), None)
            if match is not None:
                selected.append(match)
        for item in ranked:
            if item in selected:
                continue
            if any(item.text in chosen.text[:2200] for chosen in selected):
                continue
            selected.append(item)
        return selected[:limit]
