"""base_processed를 RAG·Fact 분기 전 의미 검토 JSON으로 만든다."""

from __future__ import annotations

import json
from pathlib import Path


INPUT = Path("data/base_processed")
OUTPUT = Path("data/semantic_review")


def decide(section: dict) -> tuple[str, str]:
    text = section.get("source_text", "")
    title = (section.get("section_title") or "") + " " + (section.get("topic") or "")
    if not text.strip() and not section.get("images"):
        return "EXCLUDE", "원문·OCR 텍스트가 없어 검색 또는 Fact 근거로 사용할 수 없음"
    if any(word in title for word in ("로고", "연락처", "바로가기")) and len(text.strip()) < 100:
        return "EXCLUDE", "단순 안내 또는 접속 정보로 상담 근거가 아님"
    if section.get("structured_facts"):
        return "FACT_AND_RAG", "정확한 값과 해당 값의 조건·예외 설명을 함께 제공해야 함"
    return "RAG_ONLY", "수치 DB보다 규정 설명·절차·FAQ 문맥 검색에 적합함"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    totals = {"FACT_AND_RAG": 0, "RAG_ONLY": 0, "FACT_ONLY": 0, "EXCLUDE": 0, "PASS": 0, "NEEDS_REVIEW": 0}
    for source in sorted(INPUT.glob("DOC_*_structured.json")):
        document = json.loads(source.read_text(encoding="utf-8"))
        review_sections = []
        for section in document["sections"]:
            classification, reason = decide(section)
            validation = "NEEDS_REVIEW" if section.get("review_required") else "PASS"
            totals[classification] += 1
            totals[validation] += 1
            review_sections.append({
                "section_id": section["section_id"],
                "page_start": section["page_start"],
                "page_end": section["page_end"],
                "section_title": section.get("section_title"),
                "topic": section.get("topic"),
                "classification": classification,
                "classification_reason": reason,
                "rag_include": classification in {"RAG_ONLY", "FACT_AND_RAG"},
                "fact_candidates": section.get("structured_facts", []),
                "exceptions": section.get("exceptions", []),
                "validation_status": validation,
                "validation_reasons": [
                    "OCR 또는 자동 추출 결과가 포함되어 원문 시각 검토가 필요함"
                ] if validation == "NEEDS_REVIEW" else [
                    "원문 텍스트와 구조화 값의 자동 대조를 통과함"
                ],
            })
        output = {
            "document_id": document["document_id"],
            "document_meta": document["document_meta"],
            "sections": review_sections,
        }
        (OUTPUT / source.name.replace("_structured", "_semantic_review")).write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(totals)


if __name__ == "__main__":
    main()
