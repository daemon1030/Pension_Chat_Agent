"""semantic_review를 RAG Chunk와 DB 적재 전 Fact JSON으로 확정 변환한다."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BASE = Path("data/base_processed")
REVIEW = Path("data/semantic_review")
RAG_OUT = Path("data/rag_ready")
FACT_OUT = Path("data/facts")
MAX_CHARS = 1200


def compact(value: object) -> str:
    return re.sub(r"\s+", "", str(value))


def value_in_evidence(value: object, unit: str | None, evidence: str) -> bool:
    """원문 속 값과 Fact 값을 표기 차이까지 고려해 대조한다.

    원문은 ``1,500만원``처럼 한글 단위로, Fact는 ``15000000``처럼
    정규화된 원화 값으로 저장될 수 있다. 이 함수는 그 표현 차이만
    허용하며, 계산·추론으로 새로운 값을 만들지는 않는다.
    """
    literal = compact(value)
    if literal in evidence:
        return True

    if isinstance(value, (int, float)) and unit and unit.startswith("KRW"):
        amount = int(value)
        for divisor, suffix in ((100_000_000, "억원"), (10_000, "만원")):
            if amount % divisor:
                continue
            displayed = amount // divisor
            candidates = {f"{displayed}{suffix}", f"{displayed:,}{suffix}"}
            if any(compact(candidate) in evidence for candidate in candidates):
                return True
        if amount % 10_000_000 == 0:
            if f"{amount // 10_000_000}천만원" in evidence:
                return True

    # 날짜의 '-', '.', '년/월/일' 차이만 허용한다.
    if isinstance(value, str) and re.fullmatch(r"\d{4}[-.]\d{1,2}[-.]\d{1,2}", value):
        year, month, day = (int(part) for part in re.split(r"[-.]", value))
        formats = (
            rf"{year}년0?{month}월0?{day}일",
            rf"{year}[.-]0?{month}[.-]0?{day}",
        )
        if any(re.search(pattern, evidence) for pattern in formats):
            return True
    return False


def entity_type(topic: str | None, attribute: str) -> str:
    text = f"{topic or ''} {attribute}"
    if any(word in text for word in ("세액", "과세", "tax", "income_tax")):
        return "tax_rule"
    if any(word in text for word in ("중도인출", "수령", "withdrawal", "receipt")):
        return "pension_withdrawal_rule"
    if any(word in text for word in ("IRP", "가입", "contribution")):
        return "pension_account_rule"
    if any(word in text for word in ("ETF", "투자", "investment")):
        return "investment_rule"
    return "pension_policy_rule"


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
    FACT_OUT.mkdir(parents=True, exist_ok=True)
    total_chunks = total_facts = 0
    for review_path in sorted(REVIEW.glob("DOC_*_semantic_review.json")):
        review = json.loads(review_path.read_text(encoding="utf-8"))
        doc_id = review["document_id"]
        base = json.loads((BASE / f"{doc_id}_structured.json").read_text(encoding="utf-8"))
        base_sections = {section["section_id"]: section for section in base["sections"]}
        rag_data: list[dict[str, Any]] = []
        fact_data: list[dict[str, Any]] = []
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
            if decision["classification"] != "FACT_AND_RAG":
                continue
            evidence = compact(source.get("source_text", "") + "\n" + ocr_text(source))
            for index, fact in enumerate(decision["fact_candidates"], 1):
                value = fact["value"]
                verified = value_in_evidence(value, fact.get("unit"), evidence)
                fact_data.append({
                    "fact_id": f"{doc_id}_{decision['section_id']}_FACT{index:03d}",
                    "entity_type": entity_type(decision.get("topic"), fact["attribute"]),
                    "attribute": fact["attribute"],
                    "value": value,
                    "unit": fact.get("unit"),
                    "conditions": [],
                    "exceptions": decision.get("exceptions", []),
                    "document_id": doc_id,
                    "section_id": decision["section_id"],
                    "page": decision.get("page_start"),
                    "validation_status": "PASS" if verified and decision["validation_status"] == "PASS" else "NEEDS_REVIEW",
                })
        (RAG_OUT / f"{doc_id}_rag_ready.json").write_text(json.dumps({"rag_data": rag_data}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (FACT_OUT / f"{doc_id}_facts.json").write_text(json.dumps({"structured_data": fact_data}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total_chunks += len(rag_data); total_facts += len(fact_data)
    print(f"RAG chunk {total_chunks}개, Fact {total_facts}개 생성")


if __name__ == "__main__":
    main()
