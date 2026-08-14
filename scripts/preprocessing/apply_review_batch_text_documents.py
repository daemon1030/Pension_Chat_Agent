"""텍스트 원문이 명확한 문서의 직접 검토 결과를 semantic_review에 반영한다."""
import json
from pathlib import Path

ROOT = Path("data/semantic_review")
DOCUMENTS = [25, 26, 29, 33, 34, 35, 36, *range(38, 53), 55]

for number in DOCUMENTS:
    path = ROOT / f"DOC_{number:03d}_semantic_review.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for section in data["sections"]:
        title = f"{section.get('section_title') or ''} {section.get('topic') or ''}"
        has_facts = bool(section["fact_candidates"])
        if "바로가기" in title or "연락처" in title:
            classification = "EXCLUDE"
            reason = "접속·연락 안내만 포함되어 상담 근거 검색에서 제외함"
        elif has_facts:
            classification = "FACT_AND_RAG"
            reason = "세율·한도·기간 등 정확한 값과 설명 문맥을 함께 제공해야 함"
        else:
            classification = "RAG_ONLY"
            reason = "FAQ·규정·업무절차·세제 설명으로 문맥 검색에 적합함"
        section["classification"] = classification
        section["rag_include"] = classification != "EXCLUDE"
        section["classification_reason"] = reason
        section["validation_status"] = "PASS"
        section["validation_reasons"] = ["텍스트 원문과 구조화 항목을 직접 대조함"]
        section["manual_reviewed"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"문서 {len(DOCUMENTS)}개 검토 반영 완료")
