"""CLOVA의 구조화된 RAG 응답 Schema."""

import re
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, model_validator


RetrievalSource = Literal["PRODUCT_DB", "POLICY_RAG", "PRODUCT_RAG"]


class RagAnswer(BaseModel):
    status: Literal["ANSWER", "NEED_MORE_INFO"]
    answer: str = Field(min_length=1)
    missing_fields: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices(
            "missing_fields", "missing_information", "required_information",
            "required_info", "needed_info", "additional_info", "information_needed",
        ),
    )
    follow_up_question: str | None = Field(
        default=None,
        validation_alias=AliasChoices("follow_up_question", "followup_question", "additional_question"),
    )

    @model_validator(mode="after")
    def validate_follow_up(self) -> "RagAnswer":
        if self.status == "NEED_MORE_INFO":
            if not self.missing_fields:
                raise ValueError("NEED_MORE_INFO에는 missing_fields가 필요합니다.")
            # 모델이 질문 필드만 빼먹어도 사용자가 다음 대화로 진행할 수
            # 있도록, 모델이 명시한 부족 항목으로 질문을 안전하게 완성한다.
            if not self.follow_up_question:
                self.follow_up_question = f"다음 정보를 알려주세요: {', '.join(self.missing_fields)}."
        elif self.missing_fields or self.follow_up_question:
            raise ValueError("ANSWER에는 부족 정보와 추가 질문을 넣지 않습니다.")
        return self

    @model_validator(mode="before")
    @classmethod
    def normalize_model_field_names(cls, value: Any) -> Any:
        """모델이 문자열 또는 유사한 필드명으로 준 부족 정보를 정규화한다."""
        if not isinstance(value, dict):
            return value
        value = dict(value)
        aliases = (
            "missing_fields", "missing_information", "required_information",
            "required_info", "needed_info", "additional_info", "information_needed",
        )
        raw_fields = next((value[name] for name in aliases if value.get(name)), None)
        if isinstance(raw_fields, str):
            value["missing_fields"] = [field.strip() for field in re.split(r"[,·/\n]", raw_fields) if field.strip()]
        elif isinstance(raw_fields, list):
            value["missing_fields"] = [str(field).strip() for field in raw_fields if str(field).strip()]
        elif value.get("status") == "NEED_MORE_INFO":
            # 일부 모델은 JSON 필드를 생략하고 answer 안에 '- 나이'처럼
            # 부족 항목을 나열한다. 그 항목만 구조화해 다음 질문에 쓴다.
            bullet_fields = re.findall(r"^\s*[-•]\s*(.+?)\s*$", str(value.get("answer", "")), flags=re.MULTILINE)
            if bullet_fields:
                value["missing_fields"] = bullet_fields
        if isinstance(value.get("missing_fields"), list):
            # 첫 역질문은 사용자가 부담 없이 답할 수 있는 범위로 제한한다.
            value["missing_fields"] = value["missing_fields"][:3]
        return value


class UserConditions(BaseModel):
    """첫 질문에서 추출하는 사용자 기본 조건과 이번 질문의 상황 정보."""

    age: int | None = None
    employment_status: Literal["EMPLOYED", "SELF_EMPLOYED", "UNEMPLOYED", "RETIRED"] | None = None
    income_type: str | None = None
    monthly_income: int | None = None
    annual_income: int | None = None
    risk_preference: Literal["CONSERVATIVE", "BALANCED", "AGGRESSIVE"] | None = None
    goal: str | None = None
    investment_horizon_years: int | None = None
    account_type: str | None = None
    contribution_amount: int | None = None
    tax_year: int | None = None
    withdrawal_reason: str | None = None
    product_names: list[str] = Field(default_factory=list)
    comparison_criteria: list[str] = Field(default_factory=list)


class QueryAnalysis(BaseModel):
    """질문 범위·유형·사용자 조건·조회할 데이터원을 담는 첫 분석 결과."""

    is_pension_related: bool
    intent: Literal["PENSION_RECOMMENDATION", "PENSION_INFO"] | None
    retrieval_sources: list[RetrievalSource] = Field(default_factory=list)
    user_conditions: UserConditions = Field(default_factory=UserConditions)

    @model_validator(mode="after")
    def validate_pension_scope(self) -> "QueryAnalysis":
        if self.is_pension_related and self.intent is None:
            raise ValueError("연금 관련 질문에는 intent가 필요합니다.")
        if self.is_pension_related and not self.retrieval_sources:
            raise ValueError("연금 관련 질문에는 조회할 데이터원이 필요합니다.")
        if self.intent == "PENSION_RECOMMENDATION" and not {"PRODUCT_DB", "PRODUCT_RAG"}.issubset(self.retrieval_sources):
            raise ValueError("추천 질문에는 PRODUCT_DB와 PRODUCT_RAG가 필요합니다.")
        if self.intent == "PENSION_INFO" and "PRODUCT_DB" in self.retrieval_sources:
            raise ValueError("일반 정보 질문에는 PRODUCT_DB를 선택하지 않습니다.")
        if not self.is_pension_related and self.intent is not None:
            raise ValueError("연금 무관 질문의 intent는 null이어야 합니다.")
        if not self.is_pension_related and self.retrieval_sources:
            raise ValueError("연금 무관 질문의 retrieval_sources는 빈 목록이어야 합니다.")
        return self
