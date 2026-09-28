"""Download the versioned CEA source registry without committing source PDFs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "data" / "source_registry.csv"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "source_documents"


def download_source(url: str, destination: Path, overwrite: bool) -> str:
    if destination.exists() and not overwrite:
        return "skipped"

    request = Request(url, headers={"User-Agent": "PE6201-source-downloader/1.0"})
    with urlopen(request, timeout=30) as response:
        content_type = response.headers.get_content_type()
        payload = response.read()

    if content_type != "application/pdf" or not payload.startswith(b"%PDF"):
        raise ValueError(f"Expected a PDF from {url}, received {content_type!r}")

    destination.write_bytes(payload)
    return "downloaded"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true", help="Re-download existing files.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with args.registry.open(encoding="utf-8", newline="") as source_file:
        sources = list(csv.DictReader(source_file))

    required_fields = {"source_id", "url", "local_filename"}
    if not sources or not required_fields.issubset(sources[0]):
        raise ValueError("Source registry is missing required columns.")

    for source in sources:
        destination = args.output_dir / source["local_filename"]
        status = download_source(source["url"], destination, args.force)
        print(f"{source['source_id']}: {status} -> {destination.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
