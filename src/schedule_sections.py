"""Extract the few CEA schedule fields needed to interpret operative clauses."""

from __future__ import annotations

import re
from collections.abc import Iterable

from src.source_sections import compact, is_page_furniture


ITEM_START = re.compile(r"^(\d{1,2})\.\s+(.+)$")
SELECTED_TOPICS = {
    "5": ["occupancy_subletting"],
    "6": ["occupancy_subletting"],
    "8": ["rent"],
    "9": ["security_deposit"],
    "10": ["minor_repair"],
}


def item_topics(item_id: str, text: str) -> list[str]:
    if item_id in SELECTED_TOPICS:
        return SELECTED_TOPICS[item_id]
    if re.search(r"DIPLOMATIC\s*/\s*BREAK CLAUSE", text):
        return ["termination_notice"]
    if "PROBLEM-FREE PERIOD" in text:
        return ["minor_repair"]
    return []


def split_schedule_items(pages: Iterable[tuple[int, str]], source: dict[str, str]) -> list[dict[str, object]]:
    """Keep only named occupants and configurable rent/deposit/repair fields."""
    result: list[dict[str, object]] = []
    current_id: str | None = None
    current_lines: list[tuple[int, str]] = []

    def emit() -> None:
        if current_id is None or not current_lines:
            return
        text = compact(" ".join(line for _, line in current_lines))
        topics = item_topics(current_id, text)
        if len(text) < 10 or not topics:
            return
        first_page, last_page = current_lines[0][0], current_lines[-1][0]
        locator = f"Schedule ITEM {current_id} / PDF page {first_page}"
        if last_page != first_page:
            locator += f"-{last_page}"
        result.append({
            "source_id": source["source_id"],
            "housing_type": source["housing_type"],
            "source_kind": source["source_kind"],
            "title": source["title"],
            "page_number": first_page,
            "section": locator,
            "clause_id": f"ITEM{current_id}",
            "topics": topics,
            "text": text,
        })

    in_schedule = False
    for page_number, raw_text in pages:
        in_footnote = False
        for raw_line in raw_text.splitlines():
            line = compact(raw_line)
            if is_page_furniture(line):
                continue
            # A superscript-number footnote has no item dot. It is retained in
            # the page index, not falsely appended to the last schedule item.
            if re.match(r"^\d{1,2}\s+[A-Z][a-z]", line):
                in_footnote = True
            if in_footnote:
                continue
            if line == "SCHEDULE":
                in_schedule = True
            if line == "OPERATIVE PART":
                emit()
                return result
            if not in_schedule or not line:
                continue
            match = ITEM_START.match(line)
            if match:
                emit()
                current_id = match.group(1)
                current_lines = [(page_number, line)]
            elif current_id is not None and not re.fullmatch(r"[_ ]+", line):
                current_lines.append((page_number, line))
    emit()
    return result
