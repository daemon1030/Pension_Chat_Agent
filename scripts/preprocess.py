"""CLI for first-pass, page-preserving PDF preprocessing."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Iterable

from src.preprocessing.cleaner import clean_text
from src.preprocessing.parser import PDFParser, PyMuPDFParser
from src.preprocessing.schemas import (
    PageText,
    ProcessedDocument,
    RepeatedTextCandidate,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"


def make_document_id(source_path: str) -> str:
    """Create a stable ID from the source-relative path, not inferred content."""

    path_hash = hashlib.sha256(source_path.encode("utf-8")).hexdigest()
    return f"DOC_{path_hash[:12].upper()}"


def _boundary_line(text: str, *, first: bool) -> str | None:
    non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return None
    return non_empty_lines[0] if first else non_empty_lines[-1]


def detect_repeated_boundary_candidates(
    pages: list[PageText],
    *,
    first: bool,
) -> list[RepeatedTextCandidate]:
    """Record repeated first/last lines without deleting them.

    A candidate must occur on at least two pages and on at least half of all
    pages containing text. This keeps detection conservative for short PDFs.
    """

    occurrences: dict[str, list[int]] = defaultdict(list)
    text_page_count = 0
    for page in pages:
        line = _boundary_line(page.cleaned_text, first=first)
        if line is None:
            continue
        text_page_count += 1
        occurrences[line].append(page.page)

    if text_page_count < 2:
        return []

    return [
        RepeatedTextCandidate(
            text=text,
            pages=page_numbers,
            occurrence_count=len(page_numbers),
        )
        for text, page_numbers in sorted(occurrences.items())
        if len(page_numbers) >= 2
        and len(page_numbers) / text_page_count >= 0.5
    ]


def process_pdf(
    pdf_path: Path,
    *,
    input_dir: Path,
    parser: PDFParser,
    duplicate_of_document_id: str | None = None,
) -> ProcessedDocument:
    """Parse, minimally clean, and validate one PDF."""

    relative_path = pdf_path.relative_to(input_dir).as_posix()
    document_id = make_document_id(relative_path)
    parsed = parser.parse(pdf_path)
    pages = [
        PageText(
            page=page.page,
            raw_text=page.raw_text,
            cleaned_text=clean_text(page.raw_text),
        )
        for page in parsed.pages
    ]

    return ProcessedDocument(
        document_id=document_id,
        filename=pdf_path.name,
        source_path=relative_path,
        file_hash=parsed.file_hash,
        file_size_bytes=parsed.file_size_bytes,
        page_count=parsed.page_count,
        extraction_status=parsed.extraction_status,
        pages_without_text=parsed.pages_without_text,
        duplicate_of_document_id=duplicate_of_document_id,
        metadata=parsed.metadata,
        repeated_header_candidates=detect_repeated_boundary_candidates(
            pages, first=True
        ),
        repeated_footer_candidates=detect_repeated_boundary_candidates(
            pages, first=False
        ),
        pages=pages,
    )


def discover_pdfs(input_dir: Path) -> list[Path]:
    """Find PDFs recursively with deterministic ordering."""

    return sorted(
        (
            path
            for path in input_dir.rglob("*")
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: path.relative_to(input_dir).as_posix(),
    )


def output_path_for(pdf_path: Path, input_dir: Path, output_dir: Path) -> Path:
    relative_path = pdf_path.relative_to(input_dir)
    return output_dir / relative_path.with_suffix(".json")


def write_document(document: ProcessedDocument, output_path: Path) -> None:
    """Write validated JSON atomically using UTF-8 Korean text."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    serialized = json.dumps(
        document.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )
    temporary_path.write_text(f"{serialized}\n", encoding="utf-8")
    temporary_path.replace(output_path)


def preprocess_directory(
    input_dir: Path,
    output_dir: Path,
    *,
    parser: PDFParser | None = None,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Process every PDF while isolating failures to individual files."""

    active_parser = parser or PyMuPDFParser()
    written: list[Path] = []
    failures: list[tuple[Path, str]] = []
    first_document_by_hash: dict[str, str] = {}

    for pdf_path in discover_pdfs(input_dir):
        try:
            document = process_pdf(
                pdf_path,
                input_dir=input_dir,
                parser=active_parser,
            )
            duplicate_of = first_document_by_hash.get(document.file_hash)
            if duplicate_of is not None:
                document = document.model_copy(
                    update={"duplicate_of_document_id": duplicate_of}
                )
            else:
                first_document_by_hash[document.file_hash] = document.document_id

            output_path = output_path_for(pdf_path, input_dir, output_dir)
            write_document(document, output_path)
            written.append(output_path)
        except Exception as error:  # isolate malformed/encrypted files
            failures.append((pdf_path, f"{type(error).__name__}: {error}"))

    return written, failures


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract page-level PDF text into validated JSON."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not input_dir.is_dir():
        print(f"Input directory does not exist: {input_dir}", file=sys.stderr)
        return 2

    written, failures = preprocess_directory(input_dir, output_dir)
    for output_path in written:
        print(f"WROTE {output_path}")
    for pdf_path, error in failures:
        print(f"FAILED {pdf_path}: {error}", file=sys.stderr)

    print(f"Processed {len(written)} PDF(s); {len(failures)} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
