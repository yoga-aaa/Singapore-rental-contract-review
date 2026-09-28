"""Local, housing-type-filtered BM25 retrieval over CEA source pages."""

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

    def search(self, query: str, housing_type: str, limit: int = 3) -> list[RetrievedChunk]:
        if housing_type not in {"HDB", "Private Residential"}:
            return []

        query_terms = tokenize(query)
        if not query_terms:
            return []

        corpus_size = len(self.chunks)
        candidates: list[RetrievedChunk] = []
        for index, chunk in enumerate(self.chunks):
            if chunk["housing_type"] != housing_type:
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
                    )
                )

        return sorted(candidates, key=lambda item: (-item.score, item.source_id, item.page_number))[:limit]
