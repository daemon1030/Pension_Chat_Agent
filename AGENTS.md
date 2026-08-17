# AGENTS.md

## 0. 현재 구현 컨텍스트 (2026-08-16)

이 문서의 아키텍처는 프로젝트의 **목표 상태**를 포함한다. 현재 체크아웃은 그중 문서 전처리와 로컬 JSONL 기반 RAG CLI까지 구현한 MVP다.

- 현재 사용자 진입점: `scripts/rag/chat.py`
- 현재 런타임 흐름: 질문 범위 확인 → CLOVA 임베딩 검색 → 근거 구성 → HyperCLOVA X 답변 → Pydantic JSON 검증
- 현재 저장소: `src/graph`, `src/rag`, `src/llm`
- 부분 구현: `scripts/preprocessing`의 원본 변환·보강·검토·RAG/Fact 분기 도구
- 아직 미구현: FastAPI, PostgreSQL/pgvector, Structured DB 조회, Rule Engine, 세션 복원, 완전한 Input/Output Guard
- `data/**`와 `config/**`는 Git에서 제외되므로 README에 적힌 데이터 산출물이 현재 작업공간에 없을 수 있다. 코드 리뷰와 실행 전에 실제 디렉터리를 확인한다.
- 현재 의존성 manifest가 없으므로 테스트 실행 가능 여부는 로컬 가상환경에 따라 달라진다.

코드 리뷰를 시작할 때는 `docs/code_review_guide.html`을 진입점으로 사용한다. 사실 확인 우선순위는 **실제 파일과 import 경로 → 테스트 → README → 이 문서의 목표 설계** 순서로 둔다. 목표 구조를 현재 구현으로 간주하지 않는다.

## 1. 프로젝트 개요

이 프로젝트는 **연금 관련 제공 문서와 구조화 데이터를 근거로 답변하는 AI 연금 상담 에이전트**를 구현하는 프로젝트다.

시스템은 단순한 문서 검색형 챗봇이 아니라 다음 흐름을 수행해야 한다.

0. 사용자의 질문이 보안적으로 잘못된것이 없는지 체크한다.
1. 사용자의 질문을 이해한다.
2. 질문의 의도와 필요한 고객 조건을 추출한다.
3. 답변 또는 판단에 필요한 정보가 부족하면 역질문한다.
4. 제공된 연금 문서와 구조화 DB에서 관련 정보를 검색한다.
5. 규정, 세제, 상품 정보와 고객 조건을 종합한다.
6. 명확한 조건은 Rule Engine으로 판단한다.
7. 검색된 근거에 기반하여 답변을 생성한다.
8. 근거가 부족한 내용은 추측하지 않는다.
9. 금융 상담에 적합한 안전한 표현으로 최종 답변한다.
10. 답변 시 인용한 정보를 포함해 출력한다. 

핵심 원칙:

> LLM은 이해와 설명을 담당하고, Rule Engine은 명확한 판단을 담당하며, RAG는 근거를 담당한다.

---

## 2. 목표 아키텍처

```text
User / Test Client
        |
        v
     FastAPI
        |
        v
   Input Guard
        |
        v
     LangGraph
        |
        v
Intent / Customer Condition Extraction
        |
        v
필요한 고객 정보가 충분한가?
   /                    \
 NO                     YES
 |                       |
역질문                 Retrieval
 |                       |
 |               +-------+-------+
 |               |               |
 |              RAG        Structured DB
 |               |               |
 |            pgvector       PostgreSQL
 |               +-------+-------+
 |                       |
 |                  Rule Engine
 |                       |
 |                후보 / 조건 판단
 |                       |
 +---------------------->|
                         v
                  HyperCLOVA X
                   Answer Generation
                         |
                         v
                 Grounding Checker
                         |
                         v
                   Output Guard
                         |
                         v
                    API Response
```

---

## 3. 기술 스택

### Core

- Python
- FastAPI
- LangGraph
- LangChain
- HyperCLOVA X API
- PostgreSQL
- pgvector
- Pydantic

### Data Processing

문서 유형에 따라 필요한 라이브러리를 선택한다.

후보:

- PyMuPDF
- Docling
- pandas
- openpyxl

PDF 파서는 특정 라이브러리에 강하게 종속되지 않도록 인터페이스를 분리한다.

### Infrastructure

- Docker
- `.env` 기반 환경변수 관리

API Key, DB Password 등 Secret은 절대 코드에 직접 작성하지 않는다.

---

# 4. 구현 우선순위

다음 순서대로 구현한다.

## Phase 1. 데이터 탐색

먼저 전체 제공 데이터를 파악한다.

확인할 항목:

- 파일명
- 파일 형식
- 문서 유형
- 연금 종류
- 주요 주제
- 시행일 / 개정일
- 구조화 가능 여부
- RAG 필요 여부

원본 파일은 수정하지 않는다.

```text
data/
├── raw/
├── processed/
├── tuning/
└── evaluation/
```

---

## Phase 2. 범용 전처리 구조

모든 문서를 하나의 고정된 금융 Schema에 강제로 맞추지 않는다.

먼저 문서를 **의미 단위(Semantic Unit / Section)** 로 분해한 뒤 공통 JSON 형태로 변환한다.

예시:

```json
{
  "document_id": "DOC_001",
  "title": "연금저축 안내서",
  "document_type": "업무매뉴얼",
  "category": "연금저축",
  "effective_date": null,
  "sections": [
    {
      "section_id": "SEC_001",
      "topic": "가입대상",
      "page": 1,
      "source_text": "원문 내용",
      "structured_facts": {},
      "use_for": ["rag"]
    }
  ]
}
```

### 반드시 유지할 정보

가능한 경우 모든 Section에 아래 출처 정보를 유지한다.

- `document_id`
- `document_name`
- `page`
- `section_id`
- `section_title`
- `source_text`
- `effective_date`
- `revision`
- `source`

원본으로 역추적할 수 없는 구조화 데이터는 만들지 않는다.

---

# 5. 데이터 분류 원칙

문서 단위가 아니라 **내용 단위로 분류**한다.

한 문서의 서로 다른 Section이 서로 다른 저장 경로로 갈 수 있다.

```text
Document
   |
   +-- 가입조건 ------> DB + RAG + Rule
   |
   +-- 세제 설명 -----> RAG + 일부 DB
   |
   +-- 중도인출 ------> RAG + 일부 Rule
   |
   +-- 상품 특징 -----> RAG + 일부 DB
   |
   +-- 복잡한 예외 ---> RAG
```

같은 정보가 RAG와 DB 양쪽에 존재해도 된다.

역할이 다르기 때문이다.

---

# 6. Structured DB

정확한 비교, 필터링, 계산이 필요한 값은 PostgreSQL에 저장한다.

예:

- 상품명
- 연금 유형
- 위험 등급
- 수수료
- 가입 연령
- 납입 한도
- 적립 기간
- 상품 상태
- 명확한 자격 조건

예상 테이블 후보:

```text
pension_product
pension_policy
product_eligibility
tax_rule
```

처음부터 모든 필드를 테이블화하지 않는다.

복잡하고 자주 변하는 자연어 예외 규정은 RAG에 유지한다.

유동적인 부가 정보가 필요하면 PostgreSQL `JSONB` 사용을 고려한다.

---

# 7. Vector DB / RAG

RAG의 목적은 연금 관련 사실의 **근거 검색**이다.

RAG 대상 예:

- 연금 제도
- 세제 규정
- 상품 설명
- FAQ
- 중도인출 규정
- 예외 조건
- 업무 매뉴얼

처리 흐름:

```text
Processed JSON
      |
Semantic Section
      |
Structure-aware Chunking
      |
Embedding
      |
Vector
      |
pgvector
```

Vector DB에는 최소 다음을 함께 저장한다.

```text
embedding
content
document_id
document_name
page
section
topic
effective_date
```

숫자 벡터만 저장해서 원문과 연결이 끊어지지 않도록 한다.

---

# 8. Chunking 원칙

고정 글자 수만으로 무조건 자르지 않는다.

금융 규정은 다음 우선순위를 사용한다.

1. 문서 제목
2. 장 / 절
3. 표의 행 또는 항목
4. 규정 / 조건 단위
5. 문단

조건과 예외사항이 서로 다른 Chunk로 분리되어 의미가 훼손되지 않도록 한다.

Chunk에는 출처 Metadata를 반드시 연결한다.

---

# 9. LLM 기반 데이터 구조화

LLM은 전처리의 보조 도구로 사용한다.

사용 가능 업무:

- 문서 유형 분류
- Topic 분류
- Section 인식
- 핵심 Fact 추출
- Metadata 후보 생성
- 비정형 문장을 JSON Schema로 변환

LLM에게 다음 업무를 전적으로 맡기지 않는다.

- DB Schema를 임의로 생성
- 원문에 없는 값 추론
- 금융 수치 수정
- 최종 사실 확정

LLM 출력은 반드시 Pydantic 등의 코드로 검증한다.

규칙:

> 문서에 없는 값은 추론하지 말고 `null`로 반환한다.

---

# 10. Rule Engine

명확한 조건 판단은 가능한 한 LLM이 아니라 코드에서 처리한다.

예:

- 최소 연령 충족 여부
- 가입 대상 여부
- 특정 조건 만족 여부
- 상품 후보 제외
- 명확한 한도 계산

구조:

```text
Customer Condition
        +
Structured DB
        |
        v
    Rule Engine
        |
        v
PASS / FAIL / NEED_MORE_INFO
```

Rule은 독립 모듈로 만들어 LLM 없이 테스트 가능해야 한다.

---

# 11. HyperCLOVA X 역할

HyperCLOVA X는 다음 역할을 담당한다.

- 고객 질문 의도 파악
- 고객 조건 추출
- 부족한 정보 판단 보조
- 자연스러운 역질문 생성
- RAG / DB / Rule 결과 설명
- 금융 상담에 맞는 답변 생성

HyperCLOVA가 담당하지 않는 것:

- 임의의 연금 규정 생성
- 근거 없는 상품 추천
- 확정적인 법률 / 세무 판단
- Rule Engine을 대체하는 결정론적 판단

---

# 12. HyperCLOVA Tuning

튜닝의 목적은 **연금 지식을 외우게 하는 것보다 상담 행동을 학습시키는 것**이다.

튜닝 데이터 예:

```json
{
  "input": "나한테 좋은 연금 추천해줘",
  "output": "적합한 연금을 확인하려면 현재 나이, 소득 유형, 기존 연금 가입 여부와 노후 준비 목적을 먼저 확인해야 합니다."
}
```

포함할 상황:

- 정보가 충분한 질문
- 정보가 부족한 질문
- 역질문이 필요한 질문
- 질문의 의도가 모호한 경우
- 여러 목적이 섞인 질문
- 제공 문서에 근거가 없는 질문
- 과도한 수익 보장 요구
- 금융 상담에서 안전한 표현이 필요한 경우

튜닝 데이터는 가능하면 JSONL로 관리한다.

```text
data/tuning/
├── train.jsonl
├── validation.jsonl
└── test.jsonl
```

튜닝 데이터는 전처리된 자료를 근거로 생성할 수 있지만 자동 생성 결과를 그대로 사용하지 않는다.

```text
Validated Source
      |
     LLM
      |
Synthetic Q&A
      |
Fact Validation
      |
Human / Rule Review
      |
Tuning Dataset
```

---

# 13. 튜닝 구현 순서

튜닝부터 먼저 진행하지 않는다.

다음 순서를 우선한다.

```text
Base HyperCLOVA
      +
Prompt
      +
RAG
      +
DB
      +
Rule
      |
Evaluation
      |
Failure Cases
      |
Tuning Dataset
      |
HyperCLOVA Tuning
```

튜닝 전 / 후 성능을 비교할 수 있도록 동일 평가 데이터셋을 유지한다.

---

# 14. LangGraph State

대화 중 고객 정보를 유지해야 한다.

State 후보:

```python
session_id
user_message
intent

age
employment_type
income
existing_pension
goal
risk_preference
retirement_age

missing_fields

retrieved_documents
structured_results
rule_results

candidate_products

answer
sources
```

모든 필드를 처음부터 필수로 만들지 않는다.

고객이 제공하지 않은 값은 임의로 채우지 않는다.

---

# 15. LangGraph 기본 흐름

```text
START
  |
  v
Input Guard
  |
  v
Analyze Query
  |
  v
Extract Customer Conditions
  |
  v
Required information sufficient?
   /                 \
 NO                  YES
 |                    |
Generate           Retrieve
Follow-up          /      \
Question          RAG      DB
 |                  \      /
END                  Rule Engine
                        |
                        v
                 Generate Answer
                        |
                        v
                Grounding Checker
                        |
                        v
                  Output Guard
                        |
                        v
                       END
```

사용자가 역질문에 답하면 같은 `session_id`의 State를 복원하여 다시 진행한다.

---

# 16. Input Guard

Input Guard는 단순 Regex만 사용하지 않는다.

최소 다음 위험을 고려한다.

- Prompt Injection
- System Prompt Extraction
- 내부 문서 전체 출력 요구
- 데이터 탈취
- 서비스 범위를 벗어난 요청
- 비정상적으로 긴 입력

가능한 결과:

```text
ALLOW
PROMPT_INJECTION
SYSTEM_PROMPT_EXTRACTION
DATA_EXFILTRATION
OUT_OF_SCOPE
INVALID_INPUT
```

사용자 입력을 System Prompt와 문자열로 단순 연결하지 않는다.

System / User 메시지 역할을 명확히 분리한다.

---

# 17. Grounding 원칙

최종 답변의 사실, 숫자, 조건은 가능한 한 다음 중 하나로 추적되어야 한다.

1. RAG에서 검색된 원문
2. Structured DB
3. 사용자 직접 제공 정보
4. Rule Engine 결과

근거가 없는 주장이라면:

- 삭제
- 재생성
- 또는 답변 불가 처리

중 하나를 수행한다.

기본 답변 원칙:

> 제공된 자료에서 확인되지 않는 사실은 추측하지 않는다.

---

# 18. Output Guard

최종 출력에서 확인할 사항:

- 근거 없는 사실
- 수익 보장 표현
- 과도한 상품 권유
- 확정적인 세무 / 법률 판단
- 내부 System Prompt 노출
- 내부 문서 원문 전체 유출
- 개인정보 노출

필요할 경우 안전한 표현으로 재작성한다.

---

# 19. API

프론트엔드는 필수 구현 범위가 아니다.

FastAPI로 최소 API를 제공한다.

예:

```http
POST /chat
```

Request:

```json
{
  "session_id": "user001",
  "message": "절세하면서 노후 준비하고 싶어요."
}
```

정보 부족 Response:

```json
{
  "status": "NEED_MORE_INFO",
  "answer": "현재 소득 유형과 기존 연금 가입 여부를 알려주세요."
}
```

최종 Response 예:

```json
{
  "status": "ANSWER",
  "answer": "근거 기반 답변",
  "candidates": [],
  "sources": [
    {
      "document_id": "DOC_001",
      "document_name": "문서명",
      "page": 5
    }
  ]
}
```

---

# 20. 권장 프로젝트 구조

```text
project/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── tuning/
│   └── evaluation/
│
├── scripts/
│   ├── ingest.py
│   ├── preprocess.py
│   ├── build_embeddings.py
│   └── build_tuning_dataset.py
│
├── src/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   └── schemas/
│   │
│   ├── preprocessing/
│   │   ├── parser.py
│   │   ├── classifier.py
│   │   ├── extractor.py
│   │   ├── chunker.py
│   │   └── schemas.py
│   │
│   ├── rag/
│   │   ├── embeddings.py
│   │   ├── retriever.py
│   │   └── reranker.py
│   │
│   ├── database/
│   │   ├── models.py
│   │   ├── repository.py
│   │   └── connection.py
│   │
│   ├── rules/
│   │   └── pension_rules.py
│   │
│   ├── llm/
│   │   ├── hyperclova.py
│   │   └── prompts.py
│   │
│   ├── graph/
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── edges.py
│   │   └── workflow.py
│   │
│   ├── guardrails/
│   │   ├── input_guard.py
│   │   ├── grounding.py
│   │   └── output_guard.py
│   │
│   └── config/
│       └── settings.py
│
└── tests/
    ├── preprocessing/
    ├── rag/
    ├── rules/
    ├── graph/
    └── evaluation/
```

처음부터 모든 파일을 생성할 필요는 없다.

현재 Phase에 필요한 디렉터리와 파일부터 최소 단위로 만든다.

---

# 21. 구현 규칙

## 일반 규칙

- 단일 파일에 지나치게 많은 책임을 넣지 않는다.
- 비즈니스 로직과 API 코드를 분리한다.
- 외부 API 호출 코드는 Adapter 형태로 분리한다.
- 함수와 클래스에는 명확한 타입 힌트를 사용한다.
- 환경변수는 Settings 모듈에서 관리한다.
- 하드코딩을 최소화한다.
- Secret을 Git에 Commit하지 않는다.

## 변경 시 규칙

코드를 수정하기 전에:

1. 관련 파일을 먼저 읽는다.
2. 기존 구조와 Convention을 확인한다.
3. 최소 범위로 수정한다.
4. 기존 동작을 불필요하게 변경하지 않는다.
5. 관련 테스트를 함께 추가하거나 수정한다.

---

# 22. 테스트 전략

최소 다음 레이어를 독립적으로 테스트한다.

### Preprocessing

- PDF / 문서 파싱
- Section 분리
- Metadata 유지
- JSON Schema Validation

### RAG

대표 질문에 대해 관련 Chunk가 Top-K에 포함되는지 확인한다.

예:

```text
"연금저축 중도인출 조건은?"
"세액공제는 어떤 조건에서 달라져?"
"연금은 언제부터 받을 수 있어?"
```

### Rule Engine

입력 조건과 Expected Result를 명확히 두고 Unit Test한다.

### Agent

다음 케이스를 반드시 평가한다.

- 정보 충분
- 정보 부족
- 애매한 질문
- 문서에 없는 질문
- 규정 충돌
- Prompt Injection
- 근거 없는 추천 유도

---

# 23. 평가

단순한 답변 자연스러움만 평가하지 않는다.

가능한 평가 항목:

```text
Retrieval Accuracy
Groundedness
Answer Correctness
Citation Accuracy
Follow-up Question Accuracy
Rule Accuracy
Hallucination Rate
Safety Violation Rate
```

Base Model과 Tuned Model은 동일한 Evaluation Set으로 비교한다.

---

# 24. 초기 MVP 범위

첫 구현에서는 전체 데이터를 한꺼번에 처리하지 않는다.

대표 문서 5~10개 정도로 먼저 MVP를 만든다.

MVP 완료 조건:

```text
원본 문서
   ↓
전처리 JSON 생성
   ↓
PostgreSQL / pgvector 적재
   ↓
RAG 검색 성공
   ↓
기본 HyperCLOVA 연결
   ↓
LangGraph 역질문 동작
   ↓
근거 기반 답변 생성
   ↓
FastAPI /chat 동작
```

튜닝과 고급 Guardrail은 위 흐름이 정상 동작한 후 확장한다.

---

# 25. Codex 작업 원칙

Codex는 사용자의 요청보다 범위를 임의로 확장하지 않는다.

구현 요청을 받으면 다음 순서로 작업한다.

1. 현재 프로젝트 구조 확인
2. 관련 코드 확인
3. 이번 작업의 최소 구현 범위 결정
4. 코드 구현
5. 테스트 또는 검증
6. 수정한 파일과 이유 요약

대규모 구조 변경이 필요한 경우 바로 전체를 재작성하지 말고 이유와 영향 범위를 먼저 설명한다.

외부 라이브러리를 새로 추가할 때는:

- 왜 필요한지
- 기존 의존성으로 해결 가능한지
- 어디에서 사용하는지

를 확인한다.

---

# 26. 현재 최우선 작업

프로젝트 시작 시 다음 작업부터 진행한다.

```text
STEP 1
data/raw에 제공 원본 데이터 배치

STEP 2
문서 Inventory 작성

STEP 3
범용 Document / Section JSON Schema 정의

STEP 4
대표 PDF 1개 Parser 구현

STEP 5
LLM 기반 Section / Topic / Fact Extraction

STEP 6
Pydantic Validation

STEP 7
processed JSON 생성

STEP 8
RAG용 Section과 Structured Fact 분기

STEP 9
PostgreSQL + pgvector 저장

STEP 10
대표 질문으로 Retrieval Test
```

이 단계가 끝나기 전에는 복잡한 Multi-Agent 구조나 대규모 튜닝부터 구현하지 않는다.

---

## 최종 설계 원칙

```text
Knowledge  -> RAG
Facts      -> Structured DB
Decision   -> Rule Engine
Behavior   -> Tuned HyperCLOVA
Workflow   -> LangGraph
Security   -> Guardrails
Interface  -> FastAPI
```

프로젝트의 최우선 목표는 기능 수를 늘리는 것이 아니라:

> **제공된 연금 데이터에 근거해, 필요한 경우 역질문하고, 근거가 없으면 추측하지 않는 연금 상담 에이전트**

를 안정적으로 구현하는 것이다.
