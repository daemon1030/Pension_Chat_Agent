import json
from pathlib import Path

import pymupdf

from scripts.preprocess import preprocess_directory
from src.preprocessing.schemas import ExtractionStatus, ProcessedDocument


def _create_pdf(path: Path, page_texts: list[str | None]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        if text is not None:
            page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path


def test_pipeline_validates_and_writes_no_text_pdf_without_stopping(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    _create_pdf(input_dir / "blank.pdf", [None])
    _create_pdf(input_dir / "text.pdf", ["pension"])

    written, failures = preprocess_directory(input_dir, output_dir)

    assert failures == []
    assert len(written) == 2
    blank_data = json.loads((output_dir / "blank.json").read_text("utf-8"))
    blank_document = ProcessedDocument.model_validate(blank_data)
    assert blank_document.extraction_status == ExtractionStatus.NO_TEXT_LAYER
    assert blank_document.pages[0].page == 1


def test_identical_files_are_marked_as_duplicates_not_deleted(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    first = _create_pdf(input_dir / "a.pdf", ["same"])
    second = input_dir / "b.pdf"
    second.write_bytes(first.read_bytes())

    written, failures = preprocess_directory(input_dir, output_dir)

    assert failures == []
    assert len(written) == 2
    first_data = json.loads((output_dir / "a.json").read_text("utf-8"))
    second_data = json.loads((output_dir / "b.json").read_text("utf-8"))
    assert first_data["file_hash"] == second_data["file_hash"]
    assert second_data["duplicate_of_document_id"] == first_data["document_id"]
