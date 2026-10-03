"""Read PDF rows in physical layout order, not content-stream object order."""

from pathlib import Path
import re

from pypdf import PdfReader


MARGIN_CLAUSE = re.compile(r"^\s{0,8}(\d{1,2}\.\d{1,2})\b(?:\s+(.*))?$")


def align_numbered_paragraphs(text: str) -> str:
    """Move a vertically centred margin label to its own paragraph's start.

    Layout rows fix object order, but CEA also centres some number cells on
    the second body line. Empty physical rows delimit the paragraph. Only a
    block with exactly one margin number is moved; dense ambiguous blocks
    retain their order rather than guessing at a boundary.
    """
    result: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines = block.splitlines()
        numbered = [(index, MARGIN_CLAUSE.match(line)) for index, line in enumerate(lines)]
        numbered = [(index, match) for index, match in numbered if match is not None]
        if len(numbered) == 1:
            position, match = numbered[0]
            if position > 0:
                lines[0] = f"{match.group(1)} {lines[0].strip()}"
                lines[position] = match.group(2) or ""
        result.append("\n".join(lines))
    return "\n\n".join(result)


def extract_layout_pages(path: Path) -> list[tuple[int, str]]:
    """Keep a left-column clause number beside the right-column paragraph.

    CEA's PDF content streams sometimes list several clause numbers before
    their paragraphs. Plain extraction then silently attributes both bodies
    to the last number. Pypdf's layout mode orders text by its page position.
    Do not fall back to plain extraction if layout extraction fails.
    """
    return [
        (number, align_numbered_paragraphs(page.extract_text(extraction_mode="layout") or ""))
        for number, page in enumerate(PdfReader(path).pages, start=1)
    ]
