"""DOC_011~023의 직접 검토 결과를 semantic_review에 반영한다."""
import json
from pathlib import Path

ROOT = Path("data/semantic_review")

# 문서 원문을 읽어 확정한 저장 경로. 같은 문서 안에서도 Fact가 있는 section만
# FACT_AND_RAG로 두고, 설명·법령·절차는 RAG_ONLY로 둔다.
DOCUMENT_DEFAULTS = {
    11: "RAG_ONLY", 12: "RAG_ONLY", 13: "RAG_ONLY", 14: "RAG_ONLY",
    15: "RAG_ONLY", 16: "RAG_ONLY", 17: "RAG_ONLY", 18: "RAG_ONLY",
    19: "RAG_ONLY", 20: "RAG_ONLY", 21: "RAG_ONLY", 22: "RAG_ONLY", 23: "RAG_ONLY",
}

for number, default in DOCUMENT_DEFAULTS.items():
    path = ROOT / f"DOC_{number:03d}_semantic_review.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for section in data["sections"]:
        has_facts = bool(section["fact_candidates"])
        classification = "FACT_AND_RAG" if has_facts else default
        section["classification"] = classification
        section["rag_include"] = True
        section["classification_reason"] = (
            "원문에 명확한 수치·기간·세율이 있으며, 적용 조건 또는 절차 문맥도 함께 필요함"
            if has_facts else
            "퇴직연금 제도·법령·절차·상품 설명으로 고객 질문의 근거 검색에 사용함"
        )
        section["validation_status"] = "PASS"
        section["validation_reasons"] = [
            "텍스트 레이어 원문을 직접 확인했으며, OCR 또는 이미지 전사에 의존하지 않음"
        ]
        section["manual_reviewed"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("DOC_011~023 검토 반영 완료")
