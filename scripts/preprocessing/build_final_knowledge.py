"""semantic_review를 RAG 검색용 Chunk JSON으로 확정 변환한다."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BASE = Path("data/base_processed")
REVIEW = Path("data/semantic_review")
RAG_OUT = Path("data/rag_ready")
MAX_CHARS = 1200


def compact(value: object) -> str:
    return re.sub(r"\s+", "", str(value))


def clean_lines(text: str) -> list[str]:
    excluded = {"contents", "mirae asset securities", "감사합니다"}
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower() in excluded or line.isdecimal():
            continue
        lines.append(line)
    return lines


def chunks(lines: list[str]) -> list[str]:
    result: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        if current and length + len(line) + 1 > MAX_CHARS:
            result.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        result.append("\n".join(current))
    return result


def ocr_text(section: dict[str, Any]) -> str:
    return "\n".join(
        item.get("text", "") for item in section.get("images", [])
        if isinstance(item, dict) and item.get("kind") == "ocr_text"
    )


def main() -> None:
    RAG_OUT.mkdir(parents=True, exist_ok=True)
    total_chunks = 0
    for review_path in sorted(REVIEW.glob("DOC_*_semantic_review.json")):
        review = json.loads(review_path.read_text(encoding="utf-8"))
        doc_id = review["document_id"]
        base = json.loads((BASE / f"{doc_id}_structured.json").read_text(encoding="utf-8"))
        base_sections = {section["section_id"]: section for section in base["sections"]}
        rag_data: list[dict[str, Any]] = []
        for decision in review["sections"]:
            source = base_sections[decision["section_id"]]
            if decision["rag_include"]:
                text = source.get("source_text", "")
                image_text = ocr_text(source)
                if image_text and compact(image_text) not in compact(text):
                    text = f"{text}\n[이미지 OCR 텍스트]\n{image_text}"
                for index, content in enumerate(chunks(clean_lines(text)), 1):
                    rag_data.append({
                        "chunk_id": f"{doc_id}_{decision['section_id']}_CHUNK{index:03d}",
                        "document_id": doc_id,
                        "document_title": review["document_meta"].get("title"),
                        "section_id": decision["section_id"],
                        "section_title": decision.get("section_title"),
                        "topic": decision.get("topic"),
                        "content": content,
                        "page_start": decision.get("page_start"),
                        "page_end": decision.get("page_end"),
                        "validation_status": decision["validation_status"],
                    })
        (RAG_OUT / f"{doc_id}_rag_ready.json").write_text(json.dumps({"rag_data": rag_data}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total_chunks += len(rag_data)
    print(f"RAG Chunk {total_chunks}개 생성")


if __name__ == "__main__":
    main()
