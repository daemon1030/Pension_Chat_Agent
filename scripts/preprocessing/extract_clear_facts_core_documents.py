"""원문에 명시된 규정상 수치만 Fact로 보강한다.

사례 금액, 수익률 가정, FAQ 번호, 단순 서류 발급일 같은 값은 넣지 않는다.
각 값은 해당 문서의 ``source_text``에서 직접 확인한 값이다.
"""

import json
from pathlib import Path


BASE = Path("data/base_processed")

# {문서번호: {섹션번호: [(attribute, value, unit), ...]}}
FACTS = {
    15: {1: [
        ("db_retirement_benefit_average_wage_days", 30, "day"),
        ("average_wage_calculation_period", 3, "month"),
    ], 2: [
        ("dc_minimum_annual_employer_contribution_ratio", "1/12", "annual_wage"),
    ], 3: [
        ("minimum_retirement_benefit_per_service_year", 30, "average_wage_day"),
    ]},
    18: {1: [("retirement_pension_subscriber_education_minimum_frequency", 1, "count/year")],
         3: [("failure_to_provide_subscriber_education_maximum_fine", 10000000, "KRW"),
             ("db_education_contribution_history_period", 3, "year")],
         4: [("retirement_pension_education_institution_minimum_instructor_count", 1, "count"),
             ("retirement_pension_education_instructor_minimum_experience", 3, "year")]},
    21: {1: [
        ("unavoidable_withdrawal_medical_basic_pension_income_limit", 2000000, "KRW"),
        ("unavoidable_withdrawal_disaster_basic_pension_income_limit", 2000000, "KRW"),
        ("retirement_income_tax_payment_rate_up_to_10_years", 70, "percent"),
        ("retirement_income_tax_payment_rate_over_10_years", 60, "percent"),
        ("retirement_income_tax_payment_rate_over_20_years", 50, "percent"),
        ("pension_income_comprehensive_taxation_threshold", 15000000, "KRW/year"),
        ("pension_withdrawal_limit_multiplier", 120, "percent"),
    ]},
    25: {1: [
        ("old_personal_pension_income_deduction_rate", 40, "percent"),
        ("old_personal_pension_annual_income_deduction_limit", 720000, "KRW/year"),
        ("old_personal_pension_quarterly_contribution_limit", 3000000, "KRW/quarter"),
        ("old_personal_pension_annual_contribution_limit", 12000000, "KRW/year"),
        ("old_personal_pension_minimum_receipt_age", 55, "year"),
        ("old_personal_pension_minimum_subscription_period", 10, "year"),
        ("old_personal_pension_minimum_receipt_period", 5, "year"),
        ("old_personal_pension_early_termination_tax_rate", 15.4, "percent"),
        ("old_personal_pension_retirement_proof_submission_deadline", 6, "month"),
    ]},
    26: {1: [
        ("retirement_income_after_tax_deposit_deadline", 60, "day"),
        ("pension_income_tax_rate_minimum", 3.3, "percent"),
        ("pension_income_tax_rate_maximum", 5.5, "percent"),
        ("pension_income_comprehensive_taxation_threshold", 15000000, "KRW/year"),
        ("regional_health_insurance_financial_income_threshold", 10000000, "KRW/year"),
    ]},
    27: {1: [
        ("retirement_pension_fee_billing_period", 3, "month"),
        ("retirement_benefit_processing_average_period", 7, "business_day"),
    ], 2: [
        ("mutual_aid_pension_receipt_period_change_interval", 5, "year"),
        ("mutual_aid_pension_monthly_payment_day", 15, "day"),
        ("mutual_aid_pension_change_request_deadline_before_payment", 5, "day"),
        ("retirement_benefit_payment_deadline_after_claim", 14, "day"),
        ("deposit_insurance_limit", 50000000, "KRW"),
        ("retirement_pension_risky_asset_indirect_investment_limit", 70, "percent"),
    ], 3: [
        ("mutual_aid_pension_minimum_receipt_age", 55, "year"),
        ("mutual_aid_pension_minimum_receipt_period", 10, "year"),
        ("mutual_aid_pension_maximum_receipt_period", 35, "year"),
        ("mutual_aid_pension_receipt_period_change_interval", 5, "year"),
    ]},
    36: {1: [
        ("general_account_domestic_listed_overseas_etf_tax_rate", 15.4, "percent"),
        ("financial_income_comprehensive_taxation_threshold", 20000000, "KRW/year"),
        ("pension_income_comprehensive_taxation_threshold", 15000000, "KRW/year"),
        ("pension_income_tax_rate_minimum", 3.3, "percent"),
        ("pension_income_tax_rate_maximum", 5.5, "percent"),
        ("non_pension_withdrawal_other_income_tax_rate", 16.5, "percent"),
    ]},
    39: {1: [
        ("minimum_pension_account_subscription_period", 5, "year"),
        ("minimum_pension_receipt_age", 55, "year"),
        ("pension_withdrawal_limit_multiplier", 120, "percent"),
        ("pension_withdrawal_limit_removed_from_year", 11, "year"),
        ("old_account_special_receipt_year_start", 6, "year"),
        ("old_account_special_receipt_year_cutoff", "2013-03-01", None),
        ("retirement_income_tax_payment_rate_year_1_to_10", 70, "percent"),
        ("retirement_income_tax_payment_rate_year_11_to_20", 60, "percent"),
        ("retirement_income_tax_payment_rate_year_21_or_later", 50, "percent"),
        ("pension_income_tax_rate_age_55_to_69", 5.5, "percent"),
        ("pension_income_tax_rate_age_70_to_79", 4.4, "percent"),
        ("pension_income_tax_rate_age_80_or_later", 3.3, "percent"),
        ("pension_income_comprehensive_taxation_threshold", 15000000, "KRW/year"),
        ("non_pension_withdrawal_other_income_tax_rate", 16.5, "percent"),
    ]},
    33: {2: [("isa_to_pension_account_transfer_deadline", 60, "day")],
         3: [("isa_to_pension_account_transfer_deadline", 60, "day")],
         5: [("isa_to_pension_account_transfer_deadline", 60, "day")]},
    34: {1: [("savings_bank_deposit_insurance_limit", 100000000, "KRW")]},
    35: {1: [("in_kind_transfer_system_effective_date", "2024-10-31", None)]},
    43: {1: [
        ("financial_income_comprehensive_taxation_threshold", 20000000, "KRW/year"),
        ("minimum_pension_receipt_age", 55, "year"),
        ("pension_income_comprehensive_taxation_threshold", 15000000, "KRW/year"),
        ("pension_income_tax_rate_minimum", 3.3, "percent"),
        ("pension_income_tax_rate_maximum", 5.5, "percent"),
        ("regional_health_insurance_financial_income_threshold", 10000000, "KRW/year"),
        ("regional_health_insurance_financial_income_rate", 8.13, "percent"),
        ("overseas_listed_etf_capital_gains_tax_rate", 22, "percent"),
        ("overseas_listed_etf_capital_gains_basic_deduction", 2500000, "KRW/year"),
    ]},
    44: {1: [
        ("annual_pension_account_contribution_limit", 18000000, "KRW/year"),
        ("financial_income_comprehensive_taxation_threshold", 20000000, "KRW/year"),
        ("regional_health_insurance_financial_income_threshold", 10000000, "KRW/year"),
        ("annual_tax_credit_contribution_limit", 9000000, "KRW/year"),
        ("tax_credit_rate_low_income", 16.5, "percent"),
        ("tax_credit_rate_general", 13.2, "percent"),
    ]},
    45: {1: [
        ("executive_retirement_income_limit_multiplier_2012_to_2019", 3, "multiple"),
        ("executive_retirement_income_limit_multiplier_2020_or_later", 2, "multiple"),
        ("executive_retirement_income_limit_salary_basis_period", 3, "year"),
        ("executive_retirement_income_limit_salary_factor", 10, "percent"),
        ("employment_income_progressive_tax_rate_minimum", 6.6, "percent"),
        ("employment_income_progressive_tax_rate_maximum", 49.5, "percent"),
    ]},
    46: {1: [
        ("medical_withdrawal_required_treatment_period", 6, "month"),
        ("medical_withdrawal_medical_expense_income_ratio", 12.5, "percent"),
        ("medical_withdrawal_application_deadline_after_treatment", 1, "month"),
        ("medical_withdrawal_income_basis_period", 1, "year"),
        ("medical_withdrawal_resident_record_issue_period", 3, "month"),
        ("medical_withdrawal_medical_certificate_issue_period", 6, "month"),
        ("medical_withdrawal_lineal_ascendant_age", 60, "year"),
        ("medical_withdrawal_lineal_descendant_age_limit", 20, "year"),
    ]},
    47: {1: [
        ("rehabilitation_withdrawal_application_deadline", 5, "year"),
        ("bankruptcy_withdrawal_application_deadline", 5, "year"),
        ("rehabilitation_case_search_document_issue_period", 1, "month"),
    ]},
    48: {1: [
        ("lease_deposit_withdrawal_application_deadline_after_final_payment", 1, "month"),
        ("dc_lease_deposit_withdrawal_maximum_count_per_employer", 1, "count"),
        ("resident_record_issue_period", 3, "month"),
        ("building_register_issue_period", 1, "month"),
    ]},
    49: {1: [
        ("home_purchase_withdrawal_application_deadline_after_registration", 1, "month"),
        ("resident_record_issue_period", 3, "month"),
        ("building_register_issue_period", 1, "month"),
        ("home_sale_must_precede_purchase_by_at_least", 1, "day"),
    ]},
    50: {1: [
        ("disaster_withdrawal_application_deadline", 3, "month"),
        ("disaster_withdrawal_required_hospitalization_period", 15, "day"),
        ("disaster_withdrawal_lineal_ascendant_age", 60, "year"),
        ("disaster_withdrawal_lineal_descendant_age_limit", 20, "year"),
    ]},
    52: {1: [
        ("retirement_income_correction_claim_deadline", 5, "year"),
        ("retirement_income_correction_claim_start_day_after_next_month", 10, "day"),
        ("retirement_service_deduction_per_year_up_to_5_years", 1000000, "KRW/year"),
        ("retirement_service_deduction_base_6_to_10_years", 5000000, "KRW"),
        ("retirement_service_deduction_per_year_6_to_10_years", 2000000, "KRW/year"),
        ("retirement_service_deduction_base_11_to_20_years", 15000000, "KRW"),
        ("retirement_service_deduction_per_year_11_to_20_years", 2500000, "KRW/year"),
        ("retirement_service_deduction_base_over_20_years", 40000000, "KRW"),
        ("retirement_service_deduction_per_year_over_20_years", 3000000, "KRW/year"),
    ]},
    53: {1: [
        ("retirement_pension_physical_etf_allowed_from", 2012, "year"),
        ("retirement_pension_synthetic_etf_allowed_from", 2016, "year"),
        ("retirement_pension_synthetic_etf_risk_limit", 100, "percent"),
    ], 2: [
        ("tdf_dc_irp_investment_limit", 100, "percent"),
        ("tdf_db_investment_limit", 70, "percent"),
        ("tdf_target_date_minimum_after_fund_inception", 5, "year"),
        ("tdf_equity_limit_before_target_date", 80, "percent"),
        ("tdf_equity_limit_after_target_date", 40, "percent"),
        ("tdf_non_investment_grade_debt_limit_of_assets", 20, "percent"),
        ("tdf_non_investment_grade_debt_limit_of_debt", 50, "percent"),
    ]},
    56: {1: [
        ("retirement_exchange_traded_product_trading_start", "09:00", None),
        ("retirement_exchange_traded_product_trading_end", "15:30", None),
        ("listed_reit_sale_tax_rate_2025", 0.15, "percent"),
        ("listed_reit_sale_tax_rate_2026", 0.20, "percent"),
        ("retirement_exchange_traded_product_cash_margin", 100, "percent"),
        ("db_non_risky_asset_limit", 100, "percent"),
        ("db_risky_asset_limit", 70, "percent"),
        ("db_single_issuer_concentration_limit", 10, "percent"),
        ("db_local_or_special_bond_concentration_limit", 50, "percent"),
        ("db_affiliated_group_concentration_limit", 15, "percent"),
    ], 2: [
        ("dc_irp_non_risky_asset_limit", 100, "percent"),
        ("dc_irp_risky_asset_limit", 70, "percent"),
        ("dc_irp_single_issuer_concentration_limit", 30, "percent"),
        ("dc_irp_local_or_special_bond_concentration_limit", 30, "percent"),
        ("dc_irp_affiliated_group_concentration_limit", 40, "percent"),
        ("dc_equity_method_related_party_limit", 20, "percent"),
        ("irp_equity_method_related_party_limit", 30, "percent"),
    ]},
    57: {1: [("retirement_benefit_direct_claim_minimum_continuous_service_period", 1, "year")]},
    58: {1: [
        ("tdf_equity_limit_before_target_date", 80, "percent"),
        ("tdf_equity_limit_after_target_date", 40, "percent"),
        ("tdf_non_investment_grade_debt_limit_of_assets", 20, "percent"),
        ("tdf_non_investment_grade_debt_limit_of_debt", 50, "percent"),
        ("tdf_100_percent_investment_effective_date", "2018-09-17", None),
    ], 3: [
        ("tdf_dc_irp_investment_limit", 100, "percent"),
        ("tdf_db_investment_limit", 70, "percent"),
    ]},
}


def main() -> None:
    added = 0
    for number, sections in FACTS.items():
        path = BASE / f"DOC_{number:03d}_structured.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        for section_number, values in sections.items():
            target = document["sections"][section_number - 1]["structured_facts"]
            existing = {(item["attribute"], item["value"], item.get("unit")) for item in target}
            for attribute, value, unit in values:
                if (attribute, value, unit) not in existing:
                    target.append({"attribute": attribute, "value": value, "unit": unit})
                    added += 1
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"명시적 Fact {added}개 보강 완료")


if __name__ == "__main__":
    main()
