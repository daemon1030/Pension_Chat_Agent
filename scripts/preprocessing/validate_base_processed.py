"""base_processed 결과가 원문 추출값과 일치하는지 검증한다."""

from __future__ import annotations

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_base_processed import RAW_DIR, _convert, _document_id  # noqa: E402


BASE_DIR = Path("data/base_processed")

# Fact별 원문 대조 문자열. 속성명에 포함된 조건까지 원문에서 확인되는 경우만 둔다.
FACT_EVIDENCE: dict[tuple[str, str], tuple[str, ...]] = {
    ("DOC_023", "tax_credit_contribution_limit"): ("900만원",),
    ("DOC_023", "isa_additional_tax_credit_limit"): ("300만원",),
    ("DOC_023", "combined_tax_credit_contribution_limit"): ("1,200만원",),
    ("DOC_038", "pension_income_tax_rate_age_55_to_69"): ("55세이상70세미만", "5.5%"),
    ("DOC_038", "pension_income_tax_rate_age_70_to_79"): ("70세이상80세미만", "4.4%"),
    ("DOC_038", "pension_income_tax_rate_age_80_or_older"): ("80세이상", "3.3%"),
    ("DOC_038", "lifetime_annuity_tax_rate"): ("종신연금수령시", "3.3%"),
    ("DOC_040", "deferred_retirement_income_tax_rate_year_1_to_10"): ("1~10년차", "70%"),
    ("DOC_040", "deferred_retirement_income_tax_rate_year_11_to_20"): ("11~20년차", "60%"),
    ("DOC_040", "deferred_retirement_income_tax_rate_year_21_or_later"): ("21년차", "50%"),
    ("DOC_041", "annual_tax_credit_contribution_limit"): ("연900만원",),
    ("DOC_041", "annual_pension_savings_tax_credit_limit"): ("연금저축단독600만원",),
    ("DOC_041", "tax_credit_rate_lower_income"): ("5,500만원이하", "16.5%"),
    ("DOC_041", "tax_credit_rate_higher_income"): ("5,500만원초과", "13.2%"),
    ("DOC_041", "maximum_tax_credit_lower_income"): ("148만5천원",),
    ("DOC_041", "maximum_tax_credit_higher_income"): ("118만8천원",),
    ("DOC_042", "foreign_listed_etf_capital_gains_tax_rate"): ("해외상장ETF", "22%"),
    ("DOC_042", "foreign_listed_etf_basic_deduction"): ("기본공제250만원",),
    ("DOC_042", "foreign_listed_etf_dividend_income_tax_rate"): ("배당소득세율15.4%",),
    ("DOC_042", "minimum_pension_receipt_age"): ("만55세이후",),
    ("DOC_042", "annual_pension_income_threshold"): ("연1,500만원",),
    ("DOC_051", "financial_income_comprehensive_tax_threshold"): ("연2,000만원초과",),
    ("DOC_051", "annual_pension_income_threshold"): ("연1,500만원초과",),
    ("DOC_055", "late_contribution_interest_rate_before_retirement"): ("퇴직후14일", "연10%"),
    ("DOC_055", "late_contribution_interest_rate_after_retirement"): ("퇴직후14일", "연20%"),
}


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _validate_document(path: Path) -> list[str]:
    document_id = _document_id(path)
    output_path = BASE_DIR / f"{document_id}_structured.json"
    if not output_path.exists():
        return [f"결과 파일 없음: {document_id}"]

    original = _convert(path, document_id)
    actual = json.loads(output_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if len(original["sections"]) != len(actual["sections"]):
        errors.append(f"{document_id}: 섹션 수 불일치")
        return errors

    for expected_section, actual_section in zip(original["sections"], actual["sections"], strict=True):
        section_id = actual_section["section_id"]
        if expected_section["source_text"] != actual_section["source_text"]:
            errors.append(f"{document_id}/{section_id}: source_text 불일치")
        if expected_section["tables"] != actual_section["tables"]:
            errors.append(f"{document_id}/{section_id}: tables 불일치")
        source = _normalized(actual_section["source_text"])
        for item in actual_section["exceptions"]:
            if _normalized(item) not in source:
                errors.append(f"{document_id}/{section_id}: exception 원문 근거 없음")
        for pair in actual_section["qa_pairs"]:
            if _normalized(pair["question"]) not in source or _normalized(pair["answer"]) not in source:
                errors.append(f"{document_id}/{section_id}: FAQ 원문 근거 없음")
        for fact in actual_section["structured_facts"]:
            evidence = FACT_EVIDENCE.get((document_id, fact["attribute"]))
            if evidence is None or not all(_normalized(fragment) in source for fragment in evidence):
                errors.append(f"{document_id}/{section_id}: Fact 원문 근거 없음 ({fact['attribute']})")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="base_processed 원문 일치 여부를 검증합니다.")
    parser.add_argument("--documents", nargs="*", type=int, default=list(range(11, 59)))
    args = parser.parse_args()
    errors: list[str] = []
    raw_files = []
    for path in RAW_DIR.iterdir():
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".docx", ".xlsx", ".pptx"}:
            continue
        if int(_document_id(path).removeprefix("DOC_")) in args.documents:
            raw_files.append(path)
    raw_files.sort()
    for raw_path in raw_files:
        errors.extend(_validate_document(raw_path))

    print(f"원본 {len(raw_files)}개 / DOC_{min(args.documents):03d}~DOC_{max(args.documents):03d} 결과 검증")
    if errors:
        print(f"실패 {len(errors)}건")
        print("\n".join(errors))
        raise SystemExit(1)
    print("통과: source_text, tables, FAQ, exceptions, 생성 Fact의 원문 근거가 모두 일치합니다.")


if __name__ == "__main__":
    main()
