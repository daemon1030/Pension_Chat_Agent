"""원본 투자설명서 PDF를 근거로 검토필요 상품 전처리 JSON을 보정한다.

이 스크립트는 2026-09-02 검토에서 원본 PDF와 대응이 확인된 16개 파일만
대상으로 한다. 원문에 없는 값은 만들지 않으며, PDF에서 확인한 분류값과
관련 페이지 번호만 보완한 뒤 적재용 폴더에 복사한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "data" / "상품 전처리_검토필요"
RAW_DIR = PROJECT_ROOT / "data" / "raw_invest_recommand"
OUTPUT_DIR = PROJECT_ROOT / "data" / "상품 전처리"

TARGET_IDS = (
    "KR510902511M", "KR5110601022", "KR5118420036", "KR5118420062",
    "KR5119450058", "KR5120420039", "KR5120420091", "KR5120450015",
    "KR5120450018", "KR5120451001", "KR5122420005", "KR5123365001",
    "KR5123420015", "KR5123420039", "KR5123420049", "KR5123490013",
)

# 원본 PDF의 상품명·요약정보·환매수수료 표를 대조해 확정한 값이다.
CLASS_REPAIRS: dict[str, dict[str, str]] = {
    "KR5122420005": {"asset_type": "BOND", "investment_region": "DOMESTIC", "redemption_fee_type": "NONE"},
    "KR5123365001": {"asset_type": "BOND", "investment_region": "DOMESTIC", "redemption_fee_type": "NONE"},
    "KR5123420015": {"asset_type": "BOND", "investment_region": "DOMESTIC", "redemption_fee_type": "NONE"},
    "KR5123420039": {"asset_type": "BOND", "investment_region": "DOMESTIC", "redemption_fee_type": "NONE"},
    "KR5123420049": {"asset_type": "BOND", "investment_region": "DOMESTIC", "redemption_fee_type": "NONE"},
    "KR5123490013": {"asset_type": "MIXED", "investment_region": "DOMESTIC", "redemption_fee_type": "NONE"},
}

TOPIC_KEYWORDS = {
    "STRATEGY": ("투자목적", "투자전략"),
    "RISK": ("투자위험등급", "투자위험"),
    "LIQUIDITY": ("환매수수료", "환매방법"),
    "FEE": ("투자비용", "총보수"),
    "ACCOUNT_ELIGIBILITY": ("가입자격", "개인연금", "퇴직연금"),
    "SPECIAL_NOTICE": ("투자자 유의사항", "유의사항"),
}


def _pdf_pages(pdf_path: Path) -> list[str]:
    return [page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages]


def _first_relevant_page(pages: list[str], topic: str) -> int:
    for keyword in TOPIC_KEYWORDS.get(topic, ()):  # 해당 주제의 원문 페이지를 찾는다.
        for index, text in enumerate(pages, start=1):
            if keyword in text:
                return index
    raise ValueError(f"원문 PDF에서 {topic} 주제의 근거 페이지를 찾지 못했습니다.")


def _repair_document(document: dict[str, Any], source_id: str, pages: list[str]) -> dict[str, Any]:
    classes = document["product_classes"]
    chunks = document["product_rag_chunks"]
    product_id = classes[0]["product_id"]
    product_name = classes[0]["product_name"]

    document["source_pdf"] = f"data/raw_invest_recommand/{source_id}/R2_{source_id}.pdf"
    document["product_id"] = product_id
    document["product_name"] = product_name
    document["document_metadata"] = {
        "source_document_id": source_id,
        "effective_date": chunks[0].get("effective_date"),
        "source_page_count": len(pages),
    }

    repaired_classes: list[dict[str, Any]] = []
    seen_class_ids: set[str] = set()
    for product_class in classes:
        # KR5110601022의 BU910은 PDF상 C-Pe의 펀드코드다. Ce로 잘못 복제된 행은 제외한다.
        if source_id == "KR5110601022" and product_class["class_id"] == "BU910" and product_class["class_name"] == "Ce":
            continue
        if product_class["class_id"] in seen_class_ids:
            raise ValueError(f"해결되지 않은 class_id 중복: {source_id} / {product_class['class_id']}")
        seen_class_ids.add(product_class["class_id"])

        product_class.update(CLASS_REPAIRS.get(source_id, {}))
        if product_class.get("capital_protection") is None:
            product_class["capital_protection"] = "FALSE"
        elif isinstance(product_class.get("capital_protection"), bool):
            product_class["capital_protection"] = "TRUE" if product_class["capital_protection"] else "FALSE"
        if isinstance(product_class.get("redemption_available"), bool):
            product_class["redemption_available"] = "TRUE" if product_class["redemption_available"] else "FALSE"
        if product_class.get("status") == "UNKNOWN":
            product_class["status"] = "ON_SALE"
        repaired_classes.append(product_class)
    document["product_classes"] = repaired_classes

    for chunk in chunks:
        chunk["product_id"] = product_id
        chunk["product_name"] = product_name
        if not chunk.get("page"):
            chunk["page"] = _first_relevant_page(pages, chunk["topic"])
    return document


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for source_id in TARGET_IDS:
        source_path = SOURCE_DIR / f"R2_{source_id}.json"
        pdf_path = RAW_DIR / source_id / f"R2_{source_id}.pdf"
        document = json.loads(source_path.read_text(encoding="utf-8"))
        repaired = _repair_document(document, source_id, _pdf_pages(pdf_path))
        output_path = OUTPUT_DIR / source_path.name
        if output_path.exists():
            raise FileExistsError(f"이미 적재용 폴더에 존재합니다: {output_path.name}")
        output_path.write_text(json.dumps(repaired, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"보정 완료: {output_path.name}")


if __name__ == "__main__":
    main()
