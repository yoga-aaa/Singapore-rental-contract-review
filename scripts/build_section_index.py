"""Build a local clause-level index from the registered CEA agreement templates."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.schedule_sections import split_schedule_items  # noqa: E402
from src.source_sections import split_operative_sections  # noqa: E402
from src.index_paths import CURRENT_SECTION_INDEX  # noqa: E402
from src.pdf_text import extract_layout_pages  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "data" / "source_registry.csv")
    parser.add_argument("--document-dir", type=Path, default=REPO_ROOT / "data" / "source_documents")
    parser.add_argument("--output", type=Path, default=CURRENT_SECTION_INDEX)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite an index: {args.output}. Choose a new --output path.")

    with args.registry.open(encoding="utf-8", newline="") as file:
        sources = list(csv.DictReader(file))
    chunks: list[dict[str, object]] = []
    for source in sources:
        if source["use_in_mvp"].lower() != "true" or source["source_kind"] != "tenancy_agreement_template":
            continue
        path = args.document_dir / source["local_filename"]
        if not path.exists():
            raise FileNotFoundError(f"Missing registered source: {path}")
        pages = extract_layout_pages(path)
        source_chunks = split_schedule_items(pages, source) + split_operative_sections(pages, source)
        if not source_chunks:
            raise ValueError(f"No operative clauses found in {path}")
        chunks.extend(source_chunks)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"Built {len(chunks)} clause excerpts from {len(sources)} registered sources: {args.output}")


if __name__ == "__main__":
    main()
