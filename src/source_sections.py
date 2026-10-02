"""Build bounded, traceable CEA operative-clause excerpts from PDF text."""

from __future__ import annotations

import re
from collections.abc import Iterable


CLAUSE_START = re.compile(r"^(\d{1,2}\.\d{1,2})\b(?:\s+(.*))?$")
PAGE_HEADER = re.compile(r"^[HDP RIVATE] +[A-Z ]+P a g e\s+\d+ of \d+", re.IGNORECASE)
MAX_CHARS = 1700


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def short_heading(line: str) -> bool:
    return bool(
        line and len(line) <= 85 and not line.endswith((".", ";", ","))
        and not re.match(r"^(?:[a-z]\)|\d+(?:\.\d+)?\b)", line)
    )


def topics_for_clause(clause_id: str, text: str) -> list[str]:
    lowered = text.lower()
    topics: set[str] = set()
    if clause_id == "1.1" or (clause_id == "1.2" and "hdb" in lowered) or "sublet" in lowered or "unauthorised occup" in lowered:
        topics.add("occupancy_subletting")
    if clause_id == "2.2" or "security deposit" in lowered:
        topics.add("security_deposit")
    if clause_id == "2.3" or (clause_id != "2.1" and ("utilities" in lowered or "water, electricity" in lowered)):
        topics.add("utilities")
    if clause_id in {"1.3", "1.4", "2.1"} or "default in rent" in lowered or "rental amount" in lowered:
        topics.add("rent")
    if clause_id in {"4.1", "4.2"} or "maintenance of premises" in lowered or "structural condition" in lowered:
        topics.add("minor_repair")
    if "right to terminate" in lowered or "termination" in lowered or "service of notices" in lowered:
        topics.add("termination_notice")
    if "immigration authority" in lowered or "lawfully resident" in lowered:
        topics.add("occupancy_subletting")
    return sorted(topics)


def split_operative_sections(pages: Iterable[tuple[int, str]], source: dict[str, str]) -> list[dict[str, object]]:
    """Split numbered clauses, keeping page metadata and bounded prompt text."""
    chunks: list[dict[str, object]] = []
    current_id: str | None = None
    current_lines: list[tuple[int, str]] = []
    in_operative_part = False

    def emit_clause() -> None:
        if current_id is None:
            return
        if len(compact(" ".join(line for _, line in current_lines))) > MAX_CHARS:
            for start, item in enumerate(current_lines):
                subclause = re.match(r"^([a-z])\)\s", item[1])
                if not subclause:
                    continue
                end = next(
                    (position for position in range(start + 1, len(current_lines))
                     if re.match(r"^[a-z]\)\s", current_lines[position][1])),
                    len(current_lines),
                )
                subitems = current_lines[start:end]
                for position, (_, line) in enumerate(subitems[1:], start=1):
                    if short_heading(line) or re.match(r"^\d+\.\s+[A-Z ]+$", line):
                        subitems = subitems[:position]
                        break
                excerpt = compact(" ".join(line for _, line in subitems))
                if not 35 <= len(excerpt) <= MAX_CHARS:
                    continue
                topics = topics_for_clause(current_id, excerpt)
                if not topics:
                    continue
                first_page, last_page = subitems[0][0], subitems[-1][0]
                locator = f"Clause {current_id}({subclause.group(1)}) / PDF page {first_page}"
                if last_page != first_page:
                    locator += f"-{last_page}"
                chunks.append({
                    "source_id": source["source_id"],
                    "housing_type": source["housing_type"],
                    "source_kind": source["source_kind"],
                    "title": source["title"],
                    "page_number": first_page,
                    "section": locator,
                    "clause_id": current_id,
                    "topics": topics,
                    "text": excerpt,
                })
        groups: list[list[tuple[int, str]]] = []
        group: list[tuple[int, str]] = []
        for item in current_lines:
            candidate = compact(" ".join(text for _, text in [*group, item]))
            if group and len(candidate) > MAX_CHARS:
                groups.append(group)
                group = []
            group.append(item)
        if group:
            groups.append(group)
        for part, items in enumerate(groups, start=1):
            excerpt = compact(" ".join(line for _, line in items))
            if len(excerpt) < 35:
                continue
            first_page = items[0][0]
            last_page = items[-1][0]
            locator = f"Clause {current_id} / PDF page {first_page}"
            if last_page != first_page:
                locator += f"-{last_page}"
            if len(groups) > 1:
                locator += f" / part {part}"
            chunks.append(
                {
                    "source_id": source["source_id"],
                    "housing_type": source["housing_type"],
                    "source_kind": source["source_kind"],
                    "title": source["title"],
                    "page_number": first_page,
                    "section": locator,
                    "clause_id": current_id,
                    "topics": topics_for_clause(current_id, excerpt),
                    "text": excerpt,
                }
            )

    for page_number, raw_text in pages:
        for raw_line in raw_text.splitlines():
            line = compact(raw_line)
            if not line or PAGE_HEADER.match(line):
                continue
            if line == "OPERATIVE PART":
                in_operative_part = True
                continue
            if not in_operative_part:
                continue
            match = CLAUSE_START.match(line)
            if match:
                heading: tuple[int, str] | None = None
                if current_lines and short_heading(current_lines[-1][1]):
                    heading = current_lines.pop()
                emit_clause()
                current_id = match.group(1)
                current_lines = ([heading] if heading else []) + [(page_number, line)]
            elif current_id is not None:
                current_lines.append((page_number, line))
    emit_clause()
    return chunks
