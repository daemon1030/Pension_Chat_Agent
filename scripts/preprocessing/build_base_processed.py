"""원본 문서를 범용 구조화 JSON의 안전한 초안으로 변환한다.

이 스크립트는 의미를 추론하거나 요약하지 않는다. PDF는 페이지, PPTX는 슬라이드,
XLSX는 시트 단위로 원문을 보존하며, 자동으로 확신할 수 없는 항목은 검토 대상으로 남긴다.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pymupdf


RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/base_processed")
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DRAWING_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _empty_section(section_id: str, page: int | None = 1) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "section_title": None,
        "topic": None,
        "page_start": page,
        "page_end": page,
        "source_text": "",
        "qa_pairs": [],
        "tables": [],
        "images": [],
        "structured_facts": [],
        "exceptions": [],
        "review_required": True,
    }


def _first_text_line(text: str) -> str | None:
    """원문을 고치지 않고 첫 번째 의미 있는 줄을 제목 후보로만 사용한다."""
    for line in text.splitlines():
        candidate = line.strip()
        if candidate and len(candidate) <= 160:
            return candidate
    return None


def _document(document_id: str, title: str | None, sections: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "document_meta": {
            "title": title,
            "category": None,
            "effective_date": None,
            "revision": None,
        },
        "sections": sections,
    }


def _pdf_tables(page: pymupdf.Page) -> list[dict[str, Any]]:
    """라이브러리가 명확히 인식한 표만 행/열 그대로 기록한다."""
    try:
        found = page.find_tables().tables
    except Exception:
        return []

    tables: list[dict[str, Any]] = []
    for table in found:
        rows = table.extract()
        if not rows:
            continue
        normalized_rows = [
            ["" if value is None else str(value) for value in row]
            for row in rows
        ]
        tables.append({"headers": normalized_rows[0], "rows": normalized_rows[1:]})
    return tables


def _from_pdf(path: Path, document_id: str) -> dict[str, Any]:
    pdf = pymupdf.open(path)
    try:
        sections: list[dict[str, Any]] = []
        for index, page in enumerate(pdf, start=1):
            text = page.get_text("text")
            section = _empty_section(f"SEC_{index:03d}", index)
            section["section_title"] = _first_text_line(text)
            section["source_text"] = text
            section["tables"] = _pdf_tables(page)
            # 이미지의 의미는 자동으로 판단하지 않으므로 존재 여부만 검토 대상으로 남긴다.
            section["images"] = []
            section["review_required"] = True
            sections.append(section)
        if not sections:
            sections.append(_empty_section("SEC_001"))
        title = (pdf.metadata or {}).get("title") or _first_text_line(sections[0]["source_text"])
        return _document(document_id, title, sections)
    finally:
        pdf.close()


def _xml_text(element: ET.Element, tag: str) -> str:
    return "".join(node.text or "" for node in element.iter(f"{WORD_NS}{tag}"))


def _from_docx(path: Path, document_id: str) -> dict[str, Any]:
    """DOCX 본문의 문단·표를 XML 순서대로 읽는다. 실제 쪽수는 파일에 없으므로 1로 둔다."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    body = root.find(f"{WORD_NS}body")
    source_parts: list[str] = []
    tables: list[dict[str, Any]] = []
    if body is not None:
        for child in body:
            if child.tag == f"{WORD_NS}p":
                text = _xml_text(child, "t")
                if text:
                    source_parts.append(text)
            elif child.tag == f"{WORD_NS}tbl":
                rows: list[list[str]] = []
                for row in child.findall(f"{WORD_NS}tr"):
                    cells = [_xml_text(cell, "t") for cell in row.findall(f"{WORD_NS}tc")]
                    rows.append(cells)
                    source_parts.append("\t".join(cells))
                if rows:
                    tables.append({"headers": rows[0], "rows": rows[1:]})

    section = _empty_section("SEC_001")
    section["section_title"] = _first_text_line("\n".join(source_parts))
    section["source_text"] = "\n".join(source_parts)
    section["tables"] = tables
    return _document(document_id, section["section_title"], [section])


def _column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference)
    if not letters:
        return 0
    value = 0
    for character in letters.group(0):
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _from_xlsx(path: Path, document_id: str) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = ["".join(item.itertext()) for item in shared_root.findall(f"{SHEET_NS}si")]

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target_by_id = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships
        }
        sheets = workbook.findall(f"{SHEET_NS}sheets/{SHEET_NS}sheet")
        sections: list[dict[str, Any]] = []

        for index, sheet in enumerate(sheets, start=1):
            relation_id = sheet.attrib.get(f"{REL_NS}id")
            target = target_by_id.get(relation_id or "", "")
            sheet_path = "xl/" + target.lstrip("/")
            root = ET.fromstring(archive.read(sheet_path))
            rows: list[list[str]] = []
            for row in root.findall(f".//{SHEET_NS}sheetData/{SHEET_NS}row"):
                values: list[str] = []
                for cell in row.findall(f"{SHEET_NS}c"):
                    column = _column_number(cell.attrib.get("r", ""))
                    while len(values) <= column:
                        values.append("")
                    kind = cell.attrib.get("t")
                    value = cell.findtext(f"{SHEET_NS}v", default="")
                    if kind == "s" and value.isdigit() and int(value) < len(shared_strings):
                        value = shared_strings[int(value)]
                    elif kind == "inlineStr":
                        value = "".join(cell.itertext())
                    values[column] = value
                rows.append(values)

            section = _empty_section(f"SEC_{index:03d}", index)
            section["section_title"] = sheet.attrib.get("name")
            section["source_text"] = "\n".join("\t".join(row) for row in rows)
            section["tables"] = [{"headers": rows[0], "rows": rows[1:]}] if rows else []
            sections.append(section)

    title = sections[0]["section_title"] if sections else None
    return _document(document_id, title, sections or [_empty_section("SEC_001")])


def _slide_paths(archive: zipfile.ZipFile) -> Iterable[str]:
    paths = [name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
    return sorted(paths, key=lambda name: int(re.search(r"\d+", Path(name).stem).group()))


def _from_pptx(path: Path, document_id: str) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        sections: list[dict[str, Any]] = []
        for index, slide_path in enumerate(_slide_paths(archive), start=1):
            root = ET.fromstring(archive.read(slide_path))
            text = "\n".join(node.text or "" for node in root.iter(f"{DRAWING_NS}t"))
            section = _empty_section(f"SEC_{index:03d}", index)
            section["section_title"] = _first_text_line(text)
            section["source_text"] = text
            sections.append(section)
    title = sections[0]["section_title"] if sections else None
    return _document(document_id, title, sections or [_empty_section("SEC_001")])


def _document_id(path: Path) -> str:
    match = re.fullmatch(r"doc(\d+)", path.stem, re.IGNORECASE)
    if not match:
        raise ValueError(f"지원하지 않는 파일명: {path.name}")
    return f"DOC_{int(match.group(1)):03d}"


def _validate(data: dict[str, Any]) -> None:
    required_section_keys = set(_empty_section("SEC_001"))
    if set(data) != {"document_id", "document_meta", "sections"}:
        raise ValueError("문서 최상위 JSON 구조가 올바르지 않습니다.")
    if not data["sections"]:
        raise ValueError("최소 한 개의 section이 필요합니다.")
    for section in data["sections"]:
        if set(section) != required_section_keys:
            raise ValueError(f"section 구조가 올바르지 않습니다: {section.get('section_id')}")


def _convert(path: Path, document_id: str) -> dict[str, Any]:
    handlers = {
        ".pdf": _from_pdf,
        ".docx": _from_docx,
        ".xlsx": _from_xlsx,
        ".pptx": _from_pptx,
    }
    try:
        return handlers[path.suffix.lower()](path, document_id)
    except KeyError as exc:
        raise ValueError(f"지원하지 않는 파일 형식: {path.suffix}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="원본 문서를 base_processed JSON 초안으로 변환합니다.")
    parser.add_argument("--overwrite", action="store_true", help="이미 존재하는 결과도 다시 만듭니다.")
    parser.add_argument("--documents", nargs="*", type=int, help="지정한 doc 번호만 변환합니다. 예: --documents 11 12")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    created = skipped = failed = 0
    source_files = sorted(path for path in RAW_DIR.iterdir() if path.is_file())
    for path in source_files:
        try:
            document_id = _document_id(path)
        except ValueError:
            continue
        document_number = int(document_id.removeprefix("DOC_"))
        if args.documents and document_number not in args.documents:
            continue
        output_path = OUTPUT_DIR / f"{document_id}_structured.json"
        if output_path.exists() and not args.overwrite:
            skipped += 1
            continue
        try:
            data = _convert(path, document_id)
            _validate(data)
            output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created += 1
        except Exception as exc:
            # 한 파일의 문제로 전체 변환이 멈추지 않도록 검토용 빈 문서를 남긴다.
            fallback = _document(document_id, None, [_empty_section("SEC_001")])
            fallback["sections"][0]["source_text"] = f"추출 실패: {type(exc).__name__}"
            output_path.write_text(json.dumps(fallback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            failed += 1
            print(f"실패: {path.name} ({type(exc).__name__})")
    print(f"생성 {created}개, 기존 보존 {skipped}개, 검토 필요 실패 {failed}개")


if __name__ == "__main__":
    main()
