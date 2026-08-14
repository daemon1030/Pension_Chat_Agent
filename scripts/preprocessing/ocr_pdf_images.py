"""PDF 페이지의 이미지 영역을 OCR해 base_processed의 images 필드에 보관한다."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import pymupdf


RAW = Path("data/raw")
BASE = Path("data/base_processed")
TESSERACT = Path("/opt/homebrew/opt/tesseract/bin/tesseract")


def run_ocr(image_path: Path) -> str:
    result = subprocess.run(
        [str(TESSERACT), str(image_path), "stdout", "-l", "kor+eng", "--psm", "6"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def process(document_number: int) -> tuple[int, int]:
    pdf_path = RAW / f"doc{document_number}.pdf"
    output_path = BASE / f"DOC_{document_number:03d}_structured.json"
    if not pdf_path.exists() or not output_path.exists():
        return 0, 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    pdf = pymupdf.open(pdf_path)
    processed = retained = 0
    try:
        if len(data["sections"]) != len(pdf):
            print(f"DOC_{document_number:03d}: 페이지와 section 구조가 달라 자동 OCR 제외")
            return 0, 0
        for number, page in enumerate(pdf, start=1):
            if not page.get_images(full=True):
                continue
            section = data["sections"][number - 1]
            # 이미 수기로 검토한 이미지형 문서는 덮어쓰지 않는다.
            if any(item.get("kind") == "visual_transcription" for item in section["images"] if isinstance(item, dict)):
                continue
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png") as temp:
                pixmap.save(temp.name)
                text = run_ocr(Path(temp.name))
            if not text:
                continue
            section["images"] = [item for item in section["images"] if not (isinstance(item, dict) and item.get("kind") == "ocr_text")]
            section["images"].append({"kind": "ocr_text", "text": text})
            section["review_required"] = True
            processed += 1
            retained += len(text)
    finally:
        pdf.close()
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return processed, retained


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF 이미지 OCR 결과를 base_processed에 저장합니다.")
    parser.add_argument("--documents", nargs="*", type=int, default=list(range(1, 59)))
    args = parser.parse_args()
    pages = chars = 0
    for number in args.documents:
        count, length = process(number)
        pages += count
        chars += length
        if count:
            print(f"DOC_{number:03d}: 이미지 페이지 {count}개 OCR")
    print(f"OCR 완료: 이미지 페이지 {pages}개, 텍스트 {chars}자")


if __name__ == "__main__":
    main()
