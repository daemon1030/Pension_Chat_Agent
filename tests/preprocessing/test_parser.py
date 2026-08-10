from pathlib import Path

import pymupdf

from src.preprocessing.parser import PyMuPDFParser, calculate_sha256
from src.preprocessing.schemas import ExtractionStatus


def _create_pdf(path: Path, page_texts: list[str | None]) -> Path:
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        if text is not None:
            page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path


def test_pdf_is_extracted_by_page_and_page_numbers_are_preserved(
    tmp_path: Path,
) -> None:
    pdf_path = _create_pdf(tmp_path / "two-pages.pdf", ["first", "second"])

    parsed = PyMuPDFParser().parse(pdf_path)

    assert parsed.page_count == 2
    assert [page.page for page in parsed.pages] == [1, 2]
    assert "first" in parsed.pages[0].raw_text
    assert "second" in parsed.pages[1].raw_text
    assert parsed.extraction_status == ExtractionStatus.SUCCESS


def test_sha256_is_stable_for_the_same_file(tmp_path: Path) -> None:
    pdf_path = _create_pdf(tmp_path / "hash.pdf", ["same content"])

    assert calculate_sha256(pdf_path) == calculate_sha256(pdf_path)


def test_pdf_without_text_layer_is_returned_without_exception(
    tmp_path: Path,
) -> None:
    pdf_path = _create_pdf(tmp_path / "image-only-candidate.pdf", [None, None])

    parsed = PyMuPDFParser().parse(pdf_path)

    assert parsed.extraction_status == ExtractionStatus.NO_TEXT_LAYER
    assert parsed.pages_without_text == [1, 2]
    assert [page.raw_text for page in parsed.pages] == ["", ""]
