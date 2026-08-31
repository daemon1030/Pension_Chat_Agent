"""semantic_review를 RAG 검색용 Chunk JSON으로 확정 변환한다."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.semantic_chunker import ClovaSegmentationClient, Segmenter, refine_section

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


def build_chunk_contents(text: str, segmenter: Segmenter | None = None) -> list[str]:
    """기존 Section을 주제 문단 단위로 세분화하되, API 미사용 시 기존 동작을 유지한다."""
    lines = clean_lines(text)
    if not lines:
        return []
    if segmenter is None:
        return chunks(lines)
    return refine_section("\n".join(lines), segmenter, max_chars=MAX_CHARS)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="semantic_review를 RAG 청크로 변환합니다.")
    parser.add_argument(
        "--use-clova-segmentation",
        action="store_true",
        help="각 기존 Section 내부를 CLOVA 주제 문단으로 세분화합니다.",
    )
    parser.add_argument(
        "--segmentation-alpha",
        type=float,
        default=-100,
        help="CLOVA 문단 나누기 alpha 값(-100: 자동, 기본값: -100).",
    )
    parser.add_argument(
        "--segmentation-count",
        type=int,
        default=-1,
        help="CLOVA 문단 개수(-1: 자동, 기본값: -1).",
    )
    args = parser.parse_args()

    segmenter: Segmenter | None = None
    if args.use_clova_segmentation:
        segmenter = ClovaSegmentationClient.from_env(
            alpha=args.segmentation_alpha,
            segment_count=args.segmentation_count,
        )
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
                for index, content in enumerate(build_chunk_contents(text, segmenter), 1):
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
    method = "CLOVA 문단 나누기" if segmenter else "기존 줄 길이 분할"
    print(f"RAG Chunk {total_chunks}개 생성 ({method})")


if __name__ == "__main__":
    main()
