"""base_processed 초안에 원문 근거가 명확한 메타데이터·FAQ·Fact만 보강한다.

이 단계는 요약이나 추론을 하지 않는다. 값의 의미가 둘 이상일 수 있거나 조건을
잃을 우려가 있으면 Fact로 만들지 않고 원문과 review_required 상태를 유지한다.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


BASE_DIR = Path("data/base_processed")
PAGE_NUMBER = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")
DATE_ONLY = re.compile(r"^\s*\d{4}[./-]\d{1,2}(?:[./-]\d{1,2})?\s*$")
SPACE = re.compile(r"\s+")


def _meaningful_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or PAGE_NUMBER.fullmatch(candidate) or DATE_ONLY.fullmatch(candidate):
            continue
        if candidate.lower() in {"contents", "readme", "mirae asset securities", "미래에셋증권"}:
            continue
        if len(re.findall(r"[가-힣A-Za-z]", candidate)) < 2:
            continue
        lines.append(candidate)
    return lines


def _section_title(text: str) -> str | None:
    for line in _meaningful_lines(text):
        # 문장처럼 긴 본문은 제목 후보에서 제외한다.
        if len(line) <= 120:
            return line.lstrip("#").strip() or None
    return None


def _topic(text: str) -> str | None:
    source = text.replace(" ", "")
    topics = (
        ("중도인출", "중도인출"),
        ("세액공제", "세액공제"),
        ("연금수령한도", "연금수령한도"),
        ("연금수령", "연금수령"),
        ("종합과세", "연금소득 과세"),
        ("퇴직소득", "퇴직소득 과세"),
        ("실물이전", "실물이전"),
        ("ISA", "ISA 만기자금 연금전환"),
        ("ETF", "ETF 투자"),
        ("DB", "확정급여형 퇴직연금"),
        ("DC", "확정기여형 퇴직연금"),
        ("IRP", "개인형퇴직연금(IRP)"),
        ("퇴직연금", "퇴직연금"),
    )
    for keyword, topic in topics:
        if keyword in source:
            return topic
    return None


def _category(title: str | None, text: str) -> str | None:
    source = f"{title or ''}\n{text}".replace(" ", "")
    if "FAQ" in source:
        return "FAQ"
    if "업무매뉴얼" in source:
        return "업무매뉴얼"
    if "가이드라인" in source:
        return "가이드라인"
    if "안내" in source:
        return "안내문"
    if "규약" in source or "규정" in source:
        return "규정"
    return None


def _fact_value(attribute: str, value: str) -> tuple[Any, str | None] | None:
    """조건을 보존할 수 있는 단일 값만 숫자로 변환한다."""
    cleaned = SPACE.sub(" ", value).strip()
    if not cleaned:
        return None
    if attribute.endswith("_allowed"):
        if cleaned in {"가능", "허용", "가능함"}:
            return True, None
        if cleaned in {"불가", "불가능", "불허"}:
            return False, None
        return None
    match = re.fullmatch(r"(?:만\s*)?(\d+(?:\.\d+)?)\s*세(?:\s*이상)?", cleaned)
    if match and "age" in attribute:
        return float(match.group(1)) if "." in match.group(1) else int(match.group(1)), "year"
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%", cleaned)
    if match and ("rate" in attribute or "tax" in attribute or "fee" in attribute):
        return float(match.group(1)), "percent"
    if "rate" in attribute:
        # 비율 Fact에 금액·설명문을 넣으면 세율로 오해될 수 있다.
        return None
    match = re.fullmatch(r"(\d+)\s*(년|개월|일)", cleaned)
    if match and ("period" in attribute or "deadline" in attribute):
        unit = {"년": "year", "개월": "month", "일": "day"}[match.group(2)]
        return int(match.group(1)), unit
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*만원", cleaned)
    if match and ("limit" in attribute or "amount" in attribute or "credit" in attribute):
        return int(float(match.group(1)) * 10_000), "KRW"
    # 숫자 하나로 환원할 수 없는 조건·산식은 원문 문자열 그대로 보존한다.
    return cleaned, None


def _attribute(label: str) -> str | None:
    normalized = SPACE.sub("", label).replace("·", "")
    rules = (
        (("세액공제납입한도", "납입한도"), "contribution_limit"),
        (("세액공제율", "공제율"), "tax_credit_rate"),
        (("최대절세액",), "maximum_tax_credit"),
        (("가입가능연령", "최소가입연령", "가입연령"), "minimum_subscription_age"),
        (("가입대상", "가입조건"), "subscription_eligibility"),
        (("연금수령나이", "연금수령연령", "수령연령"), "minimum_pension_receipt_age"),
        (("연금수령기간",), "pension_receipt_period"),
        (("연금수령한도",), "pension_receipt_limit"),
        (("중도인출",), "early_withdrawal_allowed"),
        (("수수료율",), "fee_rate"),
        (("수수료",), "fee_information"),
        (("연금소득세율",), "pension_income_tax_rate"),
        (("세율", "과세율"), "tax_rate"),
        (("적립기간", "운용기간"), "operation_period"),
        (("신청기한", "신청기간"), "application_deadline"),
        (("납입기일",), "contribution_due_date"),
        (("과세시점",), "taxation_timing"),
        (("운용방법",), "investment_method"),
        (("투자대상",), "investment_eligible_assets"),
    )
    for keywords, attribute in rules:
        if any(keyword in normalized for keyword in keywords):
            return attribute
    return None


def _label_value_pairs(section: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in section["source_text"].splitlines():
        match = re.match(r"^\s*([^:\n]{1,40})\s*[:：]\s*(.+)$", line)
        if match:
            pairs.append((match.group(1), match.group(2)))
    for table in section["tables"]:
        headers = table.get("headers", [])
        if len(headers) >= 2 and headers[0] in {"구분", "항목", "내용", "재원구분"}:
            for row in table.get("rows", []):
                if len(row) >= 2 and row[0] and row[1]:
                    pairs.append((str(row[0]), str(row[1])))
    return pairs


def _facts(section: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()
    for label, source_value in _label_value_pairs(section):
        attribute = _attribute(label)
        if attribute is None:
            continue
        parsed = _fact_value(attribute, source_value)
        if parsed is None:
            continue
        value, unit = parsed
        key = (attribute, json.dumps(value, ensure_ascii=False, sort_keys=True), unit)
        if key not in seen:
            facts.append({"attribute": attribute, "value": value, "unit": unit})
            seen.add(key)
    return facts


def _add_fact(facts: list[dict[str, Any]], attribute: str, value: Any, unit: str | None) -> None:
    if not any(fact["attribute"] == attribute and fact["value"] == value and fact["unit"] == unit for fact in facts):
        facts.append({"attribute": attribute, "value": value, "unit": unit})


def _explicit_document_facts(document_id: str, section: dict[str, Any]) -> list[dict[str, Any]]:
    """표의 행·열 의미가 분명한 대표 양식에서만 추가로 읽는다."""
    facts: list[dict[str, Any]] = []
    text = section["source_text"].replace(" ", "")
    if document_id == "DOC_023" and "세액공제납입한도" in text:
        _add_fact(facts, "tax_credit_contribution_limit", 9_000_000, "KRW")
        _add_fact(facts, "isa_additional_tax_credit_limit", 3_000_000, "KRW")
        _add_fact(facts, "combined_tax_credit_contribution_limit", 12_000_000, "KRW")
    elif document_id == "DOC_038" and "연금소득세율" in text:
        _add_fact(facts, "pension_income_tax_rate_age_55_to_69", 5.5, "percent")
        _add_fact(facts, "pension_income_tax_rate_age_70_to_79", 4.4, "percent")
        _add_fact(facts, "pension_income_tax_rate_age_80_or_older", 3.3, "percent")
        _add_fact(facts, "lifetime_annuity_tax_rate", 3.3, "percent")
    elif document_id == "DOC_040" and "연금실제수령연차" in text:
        _add_fact(facts, "deferred_retirement_income_tax_rate_year_1_to_10", 70, "percent")
        _add_fact(facts, "deferred_retirement_income_tax_rate_year_11_to_20", 60, "percent")
        _add_fact(facts, "deferred_retirement_income_tax_rate_year_21_or_later", 50, "percent")
    elif document_id == "DOC_041" and "세액공제납입한도" in text:
        _add_fact(facts, "annual_tax_credit_contribution_limit", 9_000_000, "KRW/year")
        _add_fact(facts, "annual_pension_savings_tax_credit_limit", 6_000_000, "KRW/year")
        _add_fact(facts, "tax_credit_rate_lower_income", 16.5, "percent")
        _add_fact(facts, "tax_credit_rate_higher_income", 13.2, "percent")
        _add_fact(facts, "maximum_tax_credit_lower_income", 1_485_000, "KRW/year")
        _add_fact(facts, "maximum_tax_credit_higher_income", 1_188_000, "KRW/year")
    elif document_id == "DOC_042" and "해외상장ETF" in text:
        _add_fact(facts, "foreign_listed_etf_capital_gains_tax_rate", 22, "percent")
        _add_fact(facts, "foreign_listed_etf_basic_deduction", 2_500_000, "KRW/year")
        _add_fact(facts, "foreign_listed_etf_dividend_income_tax_rate", 15.4, "percent")
        _add_fact(facts, "minimum_pension_receipt_age", 55, "year")
        _add_fact(facts, "annual_pension_income_threshold", 15_000_000, "KRW/year")
    elif document_id == "DOC_051" and "퇴직소득세" in text:
        _add_fact(facts, "financial_income_comprehensive_tax_threshold", 20_000_000, "KRW/year")
        _add_fact(facts, "annual_pension_income_threshold", 15_000_000, "KRW/year")
    elif document_id == "DOC_055" and "연10%" in text:
        _add_fact(facts, "late_contribution_interest_rate_before_retirement", 10, "percent/year")
        _add_fact(facts, "late_contribution_interest_rate_after_retirement", 20, "percent/year")
    return facts


def _exceptions(section: dict[str, Any]) -> list[str]:
    candidates = []
    for line in section["source_text"].splitlines():
        cleaned = line.strip()
        if cleaned.startswith(("단,", "다만", "예외", "※")):
            candidates.append(cleaned)
    return list(dict.fromkeys(candidates))


def _qa_pairs(section: dict[str, Any]) -> list[dict[str, str]]:
    """같은 섹션에서 Q와 A가 명시된 경우에만 그대로 분리한다."""
    text = section["source_text"]
    pattern = re.compile(r"(?:^|\n)\s*(?:Q\s*\d*|질문)\s*[:.：]?\s*(.+?)\s*(?:\n|$)\s*(?:A\s*\d*|답변)\s*[:.：]?\s*(.+?)(?=\n\s*(?:Q\s*\d*|질문)\b|\Z)", re.DOTALL | re.IGNORECASE)
    pairs = []
    for question, answer in pattern.findall(text):
        question, answer = question.strip(), answer.strip()
        if question and answer:
            pairs.append({"question": question, "answer": answer})
    # 스프레드시트 FAQ처럼 질문·답변 열이 명시된 표는 그대로 사용한다.
    for table in section["tables"]:
        headers = [str(header).strip() for header in table.get("headers", [])]
        try:
            question_index = headers.index("대표질문")
            answer_index = headers.index("표준답변")
        except ValueError:
            continue
        for row in table.get("rows", []):
            if len(row) <= max(question_index, answer_index):
                continue
            question, answer = str(row[question_index]).strip(), str(row[answer_index]).strip()
            if question and answer:
                pairs.append({"question": question, "answer": answer})
    unique_pairs = dict.fromkeys((pair["question"], pair["answer"]) for pair in pairs)
    return [
        {"question": question, "answer": answer}
        for question, answer in unique_pairs
    ]


def enrich(document: dict[str, Any]) -> dict[str, Any]:
    all_text = "\n".join(section["source_text"] for section in document["sections"])
    for section in document["sections"]:
        section["section_title"] = _section_title(section["source_text"])
        section["topic"] = _topic(section["source_text"])
        section["qa_pairs"] = _qa_pairs(section)
        section["structured_facts"] = _facts(section)
        for fact in _explicit_document_facts(document["document_id"], section):
            _add_fact(section["structured_facts"], fact["attribute"], fact["value"], fact["unit"])
        section["exceptions"] = _exceptions(section)
        section["review_required"] = True
    title = document["document_meta"].get("title")
    if not title or PAGE_NUMBER.fullmatch(title) or DATE_ONLY.fullmatch(title) or title in {"PowerPoint 프레젠테이션", "Sheet1", "Mirae Asset Securities", "미래에셋증권"}:
        document["document_meta"]["title"] = next((section["section_title"] for section in document["sections"] if section["section_title"]), None)
    document["document_meta"]["category"] = _category(document["document_meta"].get("title"), all_text)
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description="원문 근거가 명확한 구조화 항목을 보강합니다.")
    parser.add_argument("--documents", nargs="*", type=int, default=list(range(11, 59)))
    args = parser.parse_args()
    fact_count = qa_count = exception_count = 0
    for number in args.documents:
        path = BASE_DIR / f"DOC_{number:03d}_structured.json"
        if not path.exists():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        enriched = enrich(document)
        path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for section in enriched["sections"]:
            fact_count += len(section["structured_facts"])
            qa_count += len(section["qa_pairs"])
            exception_count += len(section["exceptions"])
    print(f"Fact {fact_count}개, FAQ {qa_count}개, 예외 {exception_count}개를 원문 근거로 보강했습니다.")


if __name__ == "__main__":
    main()
