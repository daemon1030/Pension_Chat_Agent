"""범용 문서 JSON을 임베딩용 RAG·Fact JSON 출력으로 변환한다.

``data/base_processed``에 이미 있는 필드만 사용한다. 이 스크립트는 새로운
금융 규정·값·조건·예외를 추론하지 않는다.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "base_processed"
DEFAULT_RAG_OUTPUT_DIR = PROJECT_ROOT / "data" / "rag_ready"
DEFAULT_FACT_OUTPUT_DIR = PROJECT_ROOT / "data" / "facts"
DEFAULT_ENTITY_MAPPING_PATH = PROJECT_ROOT / "config" / "entity_mappings.json"

_DATE_PATTERN = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})$")
_KOREAN_SECTION_MARKER = re.compile(r"^[가-하]\s*\.\s*")
_MAX_RAG_CONTENT_LENGTH = 1_600
_NON_SEMANTIC_LINES = {"contents", "감사합니다", "mirae asset securities"}
_STANDALONE_TABLE_HEADERS = {"구분", "내용", "비고", "수량·금액", "권리유형"}


def _compact(value: str) -> str:
    """출력에 저장되는 텍스트를 바꾸지 않고 비교용으로만 공백을 제거한다."""

    return re.sub(r"\s+", "", value)


def _load_entity_mappings(mapping_path: Path) -> dict[str, dict[str, str | None]]:
    """사람이 검토한 section별 엔티티 매핑을 읽는다."""

    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    mappings = data.get("entities")
    if not isinstance(mappings, dict):
        raise ValueError("엔티티 매핑의 entities 객체가 필요합니다.")
    for key, entity in mappings.items():
        if not isinstance(entity, dict) or set(entity) != {"type", "name"}:
            raise ValueError(f"잘못된 엔티티 매핑: {key}")
    return mappings


def _entity_for_section(
    document: dict[str, Any],
    section: dict[str, Any],
    mappings: dict[str, dict[str, str | None]],
) -> tuple[dict[str, str | None], bool]:
    """설정된 엔티티를 복사하고, 매핑이 없으면 검토 대상으로 남긴다."""

    mapping_key = f"{document['document_id']}_{section['section_id']}"
    entity = mappings.get(mapping_key)
    if entity is None:
        return {"type": None, "name": None}, True
    return {"type": entity["type"], "name": entity["name"]}, entity["type"] is None


def _value_payload(value: Any, unit: str | None) -> dict[str, Any]:
    """표현이 명확한 값만 프로그램 비교용 형태로 정규화한다."""

    if isinstance(value, bool):
        return {
            "raw": "true" if value else "false",
            "normalized": value,
            "data_type": "boolean",
            "unit": unit,
        }
    if isinstance(value, int):
        return {
            "raw": str(value),
            "normalized": value,
            "data_type": "integer",
            "unit": unit,
        }
    if isinstance(value, float):
        return {
            "raw": str(value),
            "normalized": value,
            "data_type": "number",
            "unit": unit,
        }

    raw = str(value)
    date_match = _DATE_PATTERN.fullmatch(raw)
    if date_match:
        year, month, day = (int(part) for part in date_match.groups())
        try:
            normalized = date(year, month, day).isoformat()
        except ValueError:
            normalized = None
        if normalized is not None:
            return {
                "raw": raw,
                "normalized": normalized,
                "data_type": "date",
                "unit": unit,
            }
    return {
        "raw": raw,
        "normalized": raw,
        "data_type": "string",
        "unit": unit,
    }


def _supporting_source_text(section: dict[str, Any], raw_value: str) -> tuple[str, bool]:
    """가능하면 Fact 값을 포함하는 최소 원문 행을 찾는다.

    직접 근거 행을 안전하게 특정할 수 없으면 임의로 더 좁은 인용문을 만들지
    않고 section 원문 전체를 보존한 뒤 해당 Fact를 검토 대상으로 표시한다.
    """

    source_text = str(section.get("source_text") or "")
    target = _compact(raw_value)
    candidates = [
        line.strip()
        for line in source_text.splitlines()
        if line.strip() and target and target in _compact(line.strip())
    ]
    # 짧은 값도 원문의 한 행에만 등장하면 안전하게 인용할 수 있다. 여러 행이
    # 후보면 어떤 문장이 근거인지 모호하므로 검토 대상으로 남긴다.
    if len(candidates) == 1:
        return candidates[0], False
    return source_text, True


def _clean_rag_lines(section: dict[str, Any]) -> list[str]:
    """임베딩에 불필요한 문서 형식 표시는 제외하고 의미 문장은 유지한다.

    절차 순서를 나타낼 수 있는 숫자 항목(예: ``1.``, ``2)``)은 삭제하지
    않는다. 반면 한국어 장·절 표기인 ``가.``, ``나.`` 등은 검색 의미가
    없으므로 행의 시작 부분에서만 제거한다.
    """

    section_title = _compact(str(section.get("section_title") or ""))
    lines: list[str] = []
    for line in str(section.get("source_text") or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower() in _NON_SEMANTIC_LINES:
            continue
        if stripped in _STANDALONE_TABLE_HEADERS or stripped.isdecimal():
            continue
        if section_title and _compact(stripped) == section_title:
            continue
        stripped = _KOREAN_SECTION_MARKER.sub("", stripped)
        if not stripped:
            continue
        lines.append(stripped)
    return lines


def _split_lines(lines: list[str]) -> list[str]:
    """문장·항목 경계를 유지하며 긴 section을 임베딩 가능한 길이로 나눈다."""

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for line in lines:
        additional_length = len(line) + (1 if current else 0)
        if current and current_length + additional_length > _MAX_RAG_CONTENT_LENGTH:
            chunks.append("\n".join(current))
            current = []
            current_length = 0
        current.append(line)
        current_length += len(line) + (1 if current_length else 0)
    if current:
        chunks.append("\n".join(current))
    return chunks


def _rag_record(
    document: dict[str, Any],
    section: dict[str, Any],
    content: str,
    chunk_suffix: str | None,
) -> dict[str, Any]:
    """원문 참조 정보와 임베딩할 검색 문맥을 담은 RAG 레코드를 만든다."""

    metadata = document.get("document_meta") or {}
    chunk_id = f"{document['document_id']}_{section['section_id']}"
    if chunk_suffix is not None:
        chunk_id = f"{chunk_id}_{chunk_suffix}"
    return {
        "chunk_id": chunk_id,
        "document_id": document["document_id"],
        "section_id": section["section_id"],
        "document_title": metadata.get("title"),
        "document_type": metadata.get("category"),
        "category": metadata.get("category"),
        "section_title": section.get("section_title"),
        "topic": section.get("topic"),
        "content": content,
        "page_start": section.get("page_start"),
        "page_end": section.get("page_end"),
        "effective_date": metadata.get("effective_date"),
        "revision": metadata.get("revision"),
        "review_required": bool(section.get("review_required", False)),
    }


def _rag_records(document: dict[str, Any], section: dict[str, Any]) -> list[dict[str, Any]]:
    """FAQ는 질문·답변 단위로, 일반 section은 구조 보존 chunk로 변환한다."""

    qa_pairs = section.get("qa_pairs") or []
    records: list[dict[str, Any]] = []
    if qa_pairs:
        for index, pair in enumerate(qa_pairs, start=1):
            question = str(pair.get("question") or "").strip()
            answer = str(pair.get("answer") or "").strip()
            if not question or not answer:
                continue
            content = f"질문: {question}\n답변: {answer}"
            records.append(
                _rag_record(document, section, content, f"CHUNK{index:03d}")
            )
        return records

    chunks = _split_lines(_clean_rag_lines(section))
    for index, content in enumerate(chunks, start=1):
        suffix = None if len(chunks) == 1 else f"CHUNK{index:03d}"
        records.append(_rag_record(document, section, content, suffix))
    return records


def _fact_records(
    document: dict[str, Any],
    section: dict[str, Any],
    entity_mappings: dict[str, dict[str, str | None]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()
    entity, entity_needs_review = _entity_for_section(
        document, section, entity_mappings
    )

    for item in section.get("structured_facts") or []:
        attribute = item.get("attribute")
        if not isinstance(attribute, str) or "value" not in item:
            continue
        value = _value_payload(item["value"], item.get("unit"))
        duplicate_key = (attribute, value["raw"], value["unit"])
        if duplicate_key in seen:
            continue
        seen.add(duplicate_key)

        source_text, source_needs_review = _supporting_source_text(
            section, value["raw"]
        )
        fact_number = len(records) + 1
        records.append(
            {
                "fact_id": (
                    f"{document['document_id']}_{section['section_id']}_"
                    f"FACT{fact_number:03d}"
                ),
                "entity": entity.copy(),
                "attribute": attribute,
                "value": value,
                "conditions": [],
                "exceptions": [],
                "validity": {
                    "effective_from": None,
                    "effective_to": None,
                },
                "source": {
                    "page": section.get("page_start"),
                    "source_text": source_text,
                },
                "review_required": bool(section.get("review_required", False))
                or source_needs_review
                or entity_needs_review,
            }
        )
    return records


def transform_document(
    document: dict[str, Any],
    entity_mappings: dict[str, dict[str, str | None]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """검증된 범용 문서 객체 하나를 RAG·Fact 출력 객체로 변환한다."""

    rag_data: list[dict[str, Any]] = []
    structured_data: list[dict[str, Any]] = []
    for section in document.get("sections") or []:
        if section.get("source_text"):
            rag_data.extend(_rag_records(document, section))
        structured_data.extend(_fact_records(document, section, entity_mappings))
    return {"rag_data": rag_data}, {"structured_data": structured_data}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(value, ensure_ascii=False, indent=2)}\n", encoding="utf-8"
    )


def transform_directory(
    input_dir: Path,
    rag_output_dir: Path,
    fact_output_dir: Path,
    entity_mappings: dict[str, dict[str, str | None]],
) -> tuple[int, int]:
    """각 범용 JSON 입력마다 임베딩용 RAG 파일과 Fact 파일을 작성한다."""

    documents = sorted(input_dir.glob("DOC_*_structured.json"))
    fact_count = 0
    for input_path in documents:
        document = json.loads(input_path.read_text(encoding="utf-8"))
        rag_output, fact_output = transform_document(document, entity_mappings)
        document_id = document["document_id"]
        _write_json(rag_output_dir / f"{document_id}_rag_ready.json", rag_output)
        _write_json(fact_output_dir / f"{document_id}_facts.json", fact_output)
        fact_count += len(fact_output["structured_data"])
    return len(documents), fact_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--rag-output-dir", type=Path, default=DEFAULT_RAG_OUTPUT_DIR)
    parser.add_argument("--fact-output-dir", type=Path, default=DEFAULT_FACT_OUTPUT_DIR)
    parser.add_argument(
        "--entity-mapping-path",
        type=Path,
        default=DEFAULT_ENTITY_MAPPING_PATH,
        help="section별 엔티티 매핑 JSON 경로",
    )
    args = parser.parse_args()

    entity_mappings = _load_entity_mappings(args.entity_mapping_path)
    document_count, fact_count = transform_directory(
        args.input_dir, args.rag_output_dir, args.fact_output_dir, entity_mappings
    )
    print(
        f"문서 {document_count}개를 임베딩용 RAG와 Fact {fact_count}개로 변환했습니다."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
