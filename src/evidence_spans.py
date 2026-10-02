"""Deterministic, exact-text evidence spans for model-selectable citations."""

from __future__ import annotations

from dataclasses import dataclass

from src.retrieval import RetrievedChunk


MAX_SPAN_CHARS = 560
MIN_PREFERRED_CHARS = 220


@dataclass(frozen=True)
class EvidenceSpan:
    evidence_id: str
    chunk: RetrievedChunk
    quote: str


def split_exact_spans(text: str, max_chars: int = MAX_SPAN_CHARS) -> list[str]:
    """Split near punctuation while retaining verbatim contiguous substrings."""
    result: list[str] = []
    cursor = 0
    while cursor < len(text):
        limit = min(cursor + max_chars, len(text))
        end = limit
        if limit < len(text):
            candidates = [text.rfind(mark, cursor + MIN_PREFERRED_CHARS, limit) for mark in (". ", "; ")]
            break_at = max(candidates)
            if break_at >= 0:
                end = break_at + 1
            else:
                space = text.rfind(" ", cursor + MIN_PREFERRED_CHARS, limit)
                if space >= 0:
                    end = space
        span = text[cursor:end].strip()
        if span:
            result.append(span)
        cursor = end
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
    return result


def spans_for_chunks(chunks: list[RetrievedChunk]) -> list[EvidenceSpan]:
    spans: list[EvidenceSpan] = []
    for chunk in chunks:
        for quote in split_exact_spans(chunk.text[:2200]):
            spans.append(EvidenceSpan(f"E{len(spans) + 1}", chunk, quote))
    return spans
