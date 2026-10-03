"""Separate current layout-corrected indexes from locked historical indexes."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_SECTION_INDEX = REPO_ROOT / "data" / "derived" / "source_sections_v15.jsonl"
CURRENT_PAGE_INDEX = REPO_ROOT / "data" / "derived" / "source_pages_v15.jsonl"
LEGACY_SECTION_INDEX = REPO_ROOT / "data" / "derived" / "source_sections.jsonl"
LEGACY_PAGE_INDEX = REPO_ROOT / "data" / "derived" / "source_pages.jsonl"
