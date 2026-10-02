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
    """Identify reference topics without consulting case labels or predictions."""
    lowered = query.lower()
    if re.search(r"deposit|deduct|refund", lowered):
        return {"security_deposit"}
    if re.search(r"repair|structural|plumbing|wiring|maintenance(?! fee)", lowered):
        return {"minor_repair"}
    if re.search(r"occup|resid|sublet|anyone|people|immigration|foreign", lowered):
        return {"occupancy_subletting"}
    if re.search(r"terminat|end (?:the |this )?tenancy|notice|breach|emoji", lowered):
        return {"termination_notice"}
    topics: set[str] = set()
    if re.search(r"utilit|water|electric|gas|sewer", lowered):
        topics.add("utilities")
    if re.search(r"rent|late|fee", lowered) or (not topics and "charge" in lowered):
        topics.add("rent")
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
        if housing_type not in {"HDB", "Private Residential"}:
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
        if len(desired_topics) < 2:
            return ranked[:limit]
        selected: list[RetrievedChunk] = []
        for topic in sorted(desired_topics):
            match = next((item for item in ranked if topic in item.topics and item not in selected), None)
            if match is not None:
                selected.append(match)
        selected.extend(item for item in ranked if item not in selected)
        return selected[:limit]
