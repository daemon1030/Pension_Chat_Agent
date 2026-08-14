"""DOC_011~022에서 원문에 명시된 핵심 수치 Fact를 보강한다."""
import json
from pathlib import Path

BASE = Path("data/base_processed")
FACTS = {
  11: {2: [("irp_mandatory_transfer_exception_age", 55, "year"), ("irp_mandatory_transfer_exception_retirement_benefit_amount", 3000000, "KRW")]},
  12: {2: [("maximum_administrative_fine", 5000000, "KRW")], 3: [("new_business_retirement_plan_establishment_deadline", 1, "year")], 4: [("maximum_penalty_fine", 5000000, "KRW")]},
  13: {3: [("retirement_benefit_exclusion_minimum_service_period", 1, "year"), ("retirement_benefit_exclusion_weekly_work_hours", 15, "hour/week"), ("reduced_work_hours_minimum_continuous_period", 3, "month")]},
  14: {2: [("retirement_benefit_voluntary_deposit_deadline", 60, "day"), ("annual_contribution_limit", 18000000, "KRW/year"), ("annual_tax_credit_contribution_limit", 9000000, "KRW/year"), ("risky_asset_investment_limit", 70, "percent"), ("unavoidable_withdrawal_medical_treatment_period", 6, "month")], 4: [("minimum_pension_receipt_age", 55, "year"), ("minimum_pension_payment_period", 5, "year"), ("bankruptcy_or_rehabilitation_lookback_period", 5, "year")]},
  16: {2: [("retirement_benefit_irp_seizure_protection_effective_date", "2022-04-14", None)]},
  17: {2: [("unpaid_contribution_payment_deadline_after_retirement", 14, "day"), ("late_contribution_interest_rate_before_retirement", 10, "percent/year"), ("late_contribution_interest_rate_after_retirement", 20, "percent/year")], 3: [("unpaid_contribution_penalty_imprisonment_maximum", 3, "year"), ("unpaid_contribution_penalty_fine_maximum", 30000000, "KRW")]},
  20: {1: [("minimum_pension_withdrawal_age", 55, "year"), ("unavoidable_withdrawal_medical_treatment_period", 6, "month"), ("pension_income_tax_rate_minimum", 3.3, "percent"), ("pension_income_tax_rate_maximum", 5.5, "percent"), ("non_pension_withdrawal_other_income_tax_rate", 16.5, "percent")]},
  22: {2: [("unavoidable_withdrawal_medical_treatment_period", 3, "month")], 3: [("minimum_pension_receipt_age", 55, "year")], 4: [("minimum_pension_account_subscription_period", 5, "year")], 5: [("retirement_income_tax_rate_after_10_years", 40, "percent"), ("retirement_income_tax_rate_after_20_years", 50, "percent")]},
}

for number, sections in FACTS.items():
    path = BASE / f"DOC_{number:03d}_structured.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for section_number, values in sections.items():
        target = data["sections"][section_number - 1]["structured_facts"]
        existing = {(item["attribute"], item["value"], item.get("unit")) for item in target}
        for attribute, value, unit in values:
            if (attribute, value, unit) not in existing:
                target.append({"attribute": attribute, "value": value, "unit": unit})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("DOC_011~022 Fact 보강 완료")
