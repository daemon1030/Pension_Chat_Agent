# HyperCLOVA 튜닝 JSONL 작성 형태

아래 객체 하나를 한 줄로 저장한다. 실제 학습 데이터에서는 문서 ID·페이지·원문을 검증된 제공 데이터로 교체한다.

## `query_analysis_train.jsonl`

```json
{
  "System_Prompt": "연금 상담 질문을 JSON으로 분석하세요. 질문에 직접 없는 사용자 조건·상품명·규정·수치는 추측하지 마세요. 검색용 질의는 원문 뜻만 짧게 풀어 쓰세요. 추천에는 PRODUCT_DB와 PRODUCT_RAG를 모두 선택하세요. 설명 없이 QueryAnalysis JSON 객체 하나만 출력하세요.",
  "C_ID": 0,
  "T_ID": 0,
  "Text": "[사용자 질문]\nIRP에서 안전하게 10년 동안 노후 준비를 하고 싶어. 상품을 추천해줘.",
  "Completion": "{\"is_pension_related\":true,\"intent\":\"PENSION_RECOMMENDATION\",\"retrieval_sources\":[\"PRODUCT_DB\",\"PRODUCT_RAG\"],\"search_queries\":[\"IRP 안정형 노후 준비 상품\",\"IRP 장기 운용 안정형 상품 특징\"],\"user_conditions\":{\"account_type\":\"IRP\",\"risk_preference\":\"CONSERVATIVE\",\"investment_horizon_years\":10,\"goal\":\"RETIREMENT_PREPARATION\"}}"
}
```


### 질문 분석 Completion (`QueryAnalysis`)

| 필드 | 형식 | 가능한 값 / 작성 방법 |
| --- | --- | --- |
| `is_pension_related` | boolean | `true`, `false` |
| `intent` | string 또는 null | `PENSION_INFO`, `PENSION_RECOMMENDATION`, `null` |
| `retrieval_sources` | string 배열 | `PRODUCT_DB`, `POLICY_RAG`, `PRODUCT_RAG` |
| `search_queries` | string 배열 | 원문 뜻을 풀어 쓴 검색 질의 1~2개. 질문에 없는 상품명·수치·규정은 추가하지 않음 |
| `user_conditions` | object | 아래 조건 필드만 사용 |


### `user_conditions`

| 필드 | 형식 | 가능한 값 |
| --- | --- | --- |
| `age` | integer | 나이 |
| `employment_status` | string | `EMPLOYED`, `SELF_EMPLOYED`, `UNEMPLOYED`, `RETIRED` |
| `income_type` | string | 질문에 나온 소득 형태 |
| `monthly_income` | integer | 월 소득(원) |
| `annual_income` | integer | 연 소득(원) |
| `risk_preference` | string | `CONSERVATIVE`, `BALANCED`, `AGGRESSIVE` |
| `goal` | string | 예: `RETIREMENT_PREPARATION`, `TAX_SAVING` |
| `investment_horizon_years` | integer | 투자 기간(년) |
| `account_type` | string | `IRP`, `PENSION_SAVINGS`, `RETIREMENT_PENSION` |
| `sales_channel` | string | `ONLINE`, `OFFLINE`, `ONLINE_SUPER` |
| `contribution_amount` | integer | 납입 금액(원) |
| `tax_year` | integer | 적용 연도 |
| `withdrawal_reason` | string | 질문에 나온 중도인출 사유 |
| `product_names` | string 배열 | 질문에 나온 상품명 |
| `comparison_criteria` | string 배열 | 질문에 나온 비교 기준 |


---


## `information_answer_train.jsonl`

```json
{
  "System_Prompt": "검색 근거와 사용자 제공 조건만 사용해 쉽게 답하세요. 근거 밖의 사실·수치·조건은 추측하지 마세요. 개인 조건이 부족하면 필요한 항목만 질문하세요. 수익·세무·법률 결과를 단정하지 말고, RagAnswer JSON 객체 하나만 출력하세요.",
  "C_ID": 0,
  "T_ID": 0,
  "Text": "[사용자 질문]\nIRP는 언제부터 수령할 수 있나요?\n\n[질문 분석 및 후보 결과]\n{\"intent\":\"PENSION_INFO\",\"retrieval_sources\":[\"POLICY_RAG\"],\"user_conditions\":{},\"candidate_products\":[]}\n\n[검색 근거]\n[DOC_001 p.3 | 수령 조건]\nIRP는 만 55세 이후 연금으로 수령할 수 있습니다.",
  "Completion": "{\"status\":\"ANSWER\",\"answer\":\"제공된 문서 기준으로 IRP는 만 55세 이후 연금으로 받을 수 있습니다.\",\"missing_fields\":[],\"follow_up_question\":null}"
}
```


### 답변 Completion (`RagAnswer`)

| 필드 | 형식 | 가능한 값 / 작성 방법 |
| --- | --- | --- |
| `status` | string | `ANSWER`, `NEED_MORE_INFO` |
| `answer` | string | 쉬운 말의 근거 기반 답변 또는 부족 이유 |
| `missing_fields` | string 배열 | `ANSWER`면 `[]`, `NEED_MORE_INFO`면 필요한 정보 1~3개 |
| `follow_up_question` | string 또는 null | `ANSWER`면 `null`, `NEED_MORE_INFO`면 한 문장 질문 |

---

## `recommendation_answer_train.jsonl`

```json
{
  "System_Prompt": "후보 결과와 검색 근거만 사용해 쉽게 추천을 설명하세요. 후보 밖의 상품은 추천하지 말고, 조건 일치는 matched_conditions로만 설명하세요. 근거 밖의 특징·수치·조건은 추측하지 마세요. RagAnswer JSON 객체 하나만 출력하세요.",
  "C_ID": 0,
  "T_ID": 0,
  "Text": "[사용자 질문]\nIRP에서 안정적으로 운용할 상품을 추천해줘.\n\n[질문 분석 및 후보 결과]\n{\"intent\":\"PENSION_RECOMMENDATION\",\"retrieval_sources\":[\"PRODUCT_DB\",\"PRODUCT_RAG\"],\"user_conditions\":{\"account_type\":\"IRP\",\"risk_preference\":\"CONSERVATIVE\"},\"candidate_products\":[{\"product_id\":\"P001\",\"class_id\":\"C001\",\"total_fee_rate\":\"0.185\",\"matched_conditions\":[{\"message\":\"IRP에서 가입 가능한 클래스입니다.\"}]}]}\n\n[검색 근거]\n[P001 p.1 | 투자 전략]\n주로 채권에 투자하며 가격 변동 위험이 있을 수 있습니다.",
  "Completion": "{\"status\":\"ANSWER\",\"answer\":\"P001 클래스는 IRP에서 가입 가능한 후보입니다. 문서에서는 주로 채권에 투자하며 가격이 변동할 수 있다고 안내합니다. 총보수율은 0.185%입니다.\",\"missing_fields\":[],\"follow_up_question\":null}"
}
```


### 추천 Text의 `candidate_products`

| 필드 | 형식 | 내용 |
| --- | --- | --- |
| `class_id` | string | 상품 클래스 ID |
| `class_name` | string | 상품 클래스명 |
| `product_id` | string | 상품 ID |
| `product_name` | string | 상품명 |
| `risk_grade` | integer | 위험 등급(1~6) |
| `asset_type` | string | 자산 유형 |
| `investment_region` | string | 투자 지역 |
| `eligible_account_types` | string 배열 | 가입 가능한 계좌 유형 |
| `sales_channel` | string | 판매 채널 |
| `capital_protection` | string | 원금 보장 여부 |
| `redemption_available` | string | 환매 가능 여부 |
| `redemption_fee_type` | string | 환매 수수료 유형 |
| `total_fee_rate` | number 또는 string | 총보수율 |
| `upfront_fee_rate` | number 또는 string | 선취 수수료율 |
| `status` | string | 상품 판매 상태 |
| `source_page` | integer | 상품 정보 출처 페이지 |
| `matched_conditions` | object 배열 | 코드가 확인한 조건 일치 이유 |

### 검색 근거 블록

| 필드 | 형식 | 내용 |
| --- | --- | --- |
| `document_id` | string | 문서 ID |
| `document_title` | string | 문서명 |
| `section_id` | string | 섹션 ID |
| `section_title` | string | 섹션 제목 |
| `topic` | string | 주제 |
| `content` | string | 답변에 필요한 원문 |
| `page_start` | integer 또는 null | 시작 페이지 |
| `page_end` | integer 또는 null | 끝 페이지 |
| `product_id` | string 또는 null | 상품 근거일 때 상품 ID |
| `validation_status` | string | 원문 검토 상태 |




## 추론 API

```json
{
  "messages": [
    {
      "role": "system",
      "content": "튜닝 데이터의 System_Prompt와 같은 문자열"
    },
    {
      "role": "user",
      "content": "튜닝 데이터의 Text와 같은 구조의 문자열"
    }
  ]
}
```
