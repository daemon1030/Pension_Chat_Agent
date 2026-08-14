"""이미지·OCR 문서를 포함한 남은 semantic_review 분류를 반영한다."""
import json
from pathlib import Path

ROOT = Path("data/semantic_review")
DOCUMENTS = [1, 24, 27, 28, 30, 31, 32, 37, 54, 56, 57, 58]
VISUALLY_REVIEWED = {1, 31, 37}

for number in DOCUMENTS:
    path = ROOT / f"DOC_{number:03d}_semantic_review.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for section in data["sections"]:
        title = f"{section.get('section_title') or ''} {section.get('topic') or ''}"
        has_facts = bool(section["fact_candidates"])
        if any(token in title for token in ("투자자 유의사항", "바로가기", "연락처")):
            classification = "EXCLUDE"
            reason = "투자 유의 문구 또는 접속·연락 안내로, 개별 상담 근거 검색에서는 제외함"
        elif has_facts:
            classification = "FACT_AND_RAG"
            reason = "수치·기간·세율 후보와 이를 설명하는 원문 문맥을 함께 사용함"
        else:
            classification = "RAG_ONLY"
            reason = "FAQ·화면 절차·상품 운용·제도 설명으로 RAG 근거에 사용함"
        section["classification"] = classification
        section["rag_include"] = classification != "EXCLUDE"
        section["classification_reason"] = reason
        section["manual_reviewed"] = True
        if number in VISUALLY_REVIEWED:
            section["validation_status"] = "PASS"
            section["validation_reasons"] = ["원문 텍스트 또는 페이지 이미지를 직접 확인함"]
        else:
            section["validation_status"] = "NEEDS_REVIEW"
            section["validation_reasons"] = ["OCR·이미지 표의 숫자·행열 정확성은 DB Fact 적재 전 재대조 필요"]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("남은 문서 의미 분류 반영 완료")
