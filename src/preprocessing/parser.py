"""PDF parsing adapters for structure-preserving first-pass extraction."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Protocol

import pymupdf

from src.preprocessing.schemas import ExtractionStatus, PDFMetadata


@dataclass(frozen=True, slots=True)
class ParsedPage:
    """Unmodified text extracted from a single source page."""

    page: int
    raw_text: str


@dataclass(frozen=True, slots=True)
class ParsedPDF:
    """Library-neutral parsed PDF data before cleaning and validation."""

    file_hash: str
    file_size_bytes: int
    page_count: int
    metadata: PDFMetadata
    extraction_status: ExtractionStatus
    pages_without_text: list[int]
    pages: list[ParsedPage]


class PDFParser(Protocol):
    """Adapter boundary for future PDF engines or block/table extraction."""

    def parse(self, pdf_path: Path) -> ParsedPDF:
        """Parse one PDF without changing its extracted page text."""


def calculate_sha256(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return a streaming SHA-256 hash without loading the whole file."""

    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_metadata_value(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_pdf_metadata(metadata: dict[str, Any]) -> PDFMetadata:
    return PDFMetadata(
        title=_optional_metadata_value(metadata, "title"),
        author=_optional_metadata_value(metadata, "author"),
        subject=_optional_metadata_value(metadata, "subject"),
        keywords=_optional_metadata_value(metadata, "keywords"),
        creator=_optional_metadata_value(metadata, "creator"),
        producer=_optional_metadata_value(metadata, "producer"),
        creation_date=_optional_metadata_value(metadata, "creationDate"),
        modification_date=_optional_metadata_value(metadata, "modDate"),
        pdf_format=_optional_metadata_value(metadata, "format"),
    )


class PyMuPDFParser:
    """PyMuPDF adapter using page-level plain-text extraction.

    The adapter deliberately does not infer tables or reorder content with
    ``sort=True``. A later adapter can expose blocks/tables behind the same
    parser boundary after layout-specific validation.
    """

    def parse(self, pdf_path: Path) -> ParsedPDF:
        path = Path(pdf_path)
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"not a PDF file: {path}")
        if not path.is_file():
            raise FileNotFoundError(path)

        file_hash = calculate_sha256(path)
        file_size_bytes = path.stat().st_size

        with pymupdf.open(path) as document:
            pages = [
                ParsedPage(
                    page=page_index + 1,
                    raw_text=document.load_page(page_index).get_text(
                        "text", sort=False
                    ),
                )
                for page_index in range(document.page_count)
            ]
            metadata = _to_pdf_metadata(document.metadata or {})

        pages_without_text = [
            page.page for page in pages if not page.raw_text.strip()
        ]
        if pages and len(pages_without_text) == len(pages):
            status = ExtractionStatus.NO_TEXT_LAYER
        elif pages_without_text:
            status = ExtractionStatus.PARTIAL_TEXT
        else:
            status = ExtractionStatus.SUCCESS

        return ParsedPDF(
            file_hash=file_hash,
            file_size_bytes=file_size_bytes,
            page_count=len(pages),
            metadata=metadata,
            extraction_status=status,
            pages_without_text=pages_without_text,
            pages=pages,
        )
