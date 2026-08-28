# 연금 상담 RAG 챗봇

연금 제도 문서와 상품 데이터를 근거로 답하는 챗봇입니다. 질문을 받으면 HyperCLOVA가 질문의 뜻, 사용자가 직접 말한 조건, 필요한 데이터원을 먼저 정리하고, 코드가 PostgreSQL과 pgvector에서 해당 정보를 조회한 뒤 근거 기반 답변을 생성합니다.

## 현재 동작 흐름

```text
사용자 질문
  ↓
1차 키워드 확인
  ├─ 연금 관련 단어가 없음 → 안내 후 종료
  └─ 연금 관련 가능성 있음
       ↓
2차 LLM 질문 분석
  ├─ 실제 연금 상담 질문인지 확인
  ├─ 추천 질문인지 / 제도·규정 질문인지 구분
  └─ 사용자가 말한 나이·고용 형태·위험 선호·목적 등 조건 추출
  └─ PRODUCT_DB / POLICY_RAG / PRODUCT_RAG 중 조회할 데이터원 선택
       ↓
코드가 필요한 정보가 충분한지 확인
  ├─ 부족함 → 필요한 정보만 역질문
  └─ 충분함
       ↓
LLM이 선택한 데이터원 조회
  ├─ POLICY_RAG → 제도·세제·수령·중도인출 문서 검색
  ├─ PRODUCT_RAG → 상품 설명·특징 문서 검색
  └─ PRODUCT_DB → 추천 질문에서 조건에 맞는 후보 상품 필터
       ↓
검색 근거 + 질문 + 사용자 조건
  ↓
HyperCLOVA 최종 답변 생성
  ↓
답변·출처·처리 로그 저장
```

핵심 원칙은 다음과 같습니다.

```text
LLM  → 질문 이해, 사용자 조건 추출, 필요한 데이터원 선택, 답변 설명
DB   → 상품 조건을 정확하게 비교·필터링
RAG  → 제도·상품 문서에서 답변 근거 검색
코드 → 정보 부족 판단과 흐름 제어
```

## 데이터 흐름

```text
원본 문서
  → base_processed       원문·페이지·표·이미지 보존
  → semantic_review      섹션과 RAG 포함 여부 검토
  → rag_ready            검색용 Chunk 생성
  → embeddings           CLOVA 임베딩 JSONL 생성
  → PostgreSQL / pgvector 적재
  → 챗봇 검색에 사용
```

임베딩 JSONL은 DB 적재를 위한 중간 산출물입니다. 채팅 실행 시에는 로컬 JSONL을 직접 검색하지 않고 PostgreSQL + pgvector만 사용합니다.

## 주요 디렉터리

```text
data/
├── raw/                 # 원본 PDF·Office 문서
├── base_processed/      # 원문 보존형 중간 JSON
├── semantic_review/     # RAG 포함 여부 검토 JSON
├── rag_ready/           # 확정된 RAG Chunk JSON
├── embeddings/          # DB 적재용 임베딩 JSONL
├── products.json        # 상품 조건 DB 적재용 데이터
└── evaluation/          # 대표 질문·평가 결과

database/
├── init.sql             # 새 PostgreSQL·pgvector 테이블 정의
└── migrations/          # 이미 만든 로컬 DB용 마이그레이션

src/
├── database/            # 상품 DB와 벡터 검색 Repository
├── graph/               # LangGraph 질문 처리 흐름
├── llm/                 # HyperCLOVA 호출·프롬프트·JSON 검증
├── observability/       # 요청·분석·검색·답변 로그
├── products/            # 추천에 필요한 필수 사용자 조건 정의
└── rag/                 # RAG Chunk 모델·임베딩 API·PostgreSQL Retriever

scripts/
├── database/            # DB 초기화·데이터 적재
├── evaluation/          # 대표 질문 일괄 평가
├── preprocessing/       # 원본 전처리·검토·Chunk 생성
└── rag/                 # 임베딩 생성·챗봇 실행
```

## 주요 코드 역할

| 위치 | 역할 |
|---|---|
| `scripts/rag/chat.py` | PostgreSQL 기반 챗봇 실행 진입점입니다. |
| `src/graph/workflow.py` | 질문 분석, DB 필터, RAG 검색, 답변 생성을 연결합니다. |
| `src/graph/nodes.py` | 질문 범위 확인, LLM 분석, 정보 부족 판단, 근거 구성 역할을 수행합니다. |
| `src/database/repository.py` | 상품 조건 필터와 pgvector 검색 SQL을 실행합니다. |
| `src/rag/postgres_retriever.py` | 질문을 임베딩하고 PostgreSQL에서 Policy/Product 문서를 검색합니다. |
| `src/llm/hyperclova.py` | HyperCLOVA API 호출과 JSON 형식 재시도를 담당합니다. |
| `src/observability/chat_log.py` | 분석 단계와 최종 답변 단계를 JSONL 로그로 남깁니다. |

## 실행 방법

프로젝트 루트에서 실행합니다. Python 가상환경과 Docker가 준비되어 있어야 합니다.

### 1. 환경 변수 설정

`.env.example`을 참고해 프로젝트 루트에 `.env`를 만듭니다. 실제 API 키와 운영용 DB 비밀번호는 Git에 올리지 않습니다.

```dotenv
CLOVASTUDIO_API_KEY=Bearer 발급받은_API_키
CLOVASTUDIO_CHAT_MODEL=HCX-DASH-002
CLOVASTUDIO_JSON_RETRY_COUNT=1

POSTGRES_DB=pension_agent
POSTGRES_USER=pension_app
POSTGRES_PASSWORD=로컬_개발용_비밀번호
POSTGRES_PORT=5433
PENSION_DATABASE_DSN=postgresql://pension_app:로컬_개발용_비밀번호@127.0.0.1:5433/pension_agent
```

### 2. PostgreSQL + pgvector 실행

```bash
docker compose -p pension-agent up -d
```

이미 만든 PostgreSQL 볼륨을 사용 중이라면, 클래스 기반 상품 필터 테이블을 추가합니다.

```bash
docker compose -p pension-agent exec -T postgres psql -U pension_app -d pension_agent < database/migrations/001_product_classes.sql
```

### 3. 문서 전처리와 임베딩 생성

원본 문서를 새로 추가하거나 수정한 경우에만 실행합니다.

```bash
.venv/bin/python3 scripts/rag/build_embeddings.py
```

상품 전처리 결과는 두 가지로 나뉩니다.

- `data/product_db_ready/product_classes.json`: 추천 후보를 정확히 거르는 상품 클래스 데이터
- `data/embeddings/product_embeddings_from_preprocessing.jsonl`: 후보 상품의 설명을 검색하는 Product RAG 임베딩

아래 명령은 규정 RAG, 상품 RAG, 상품 클래스 데이터를 **한 PostgreSQL DB**에 함께 적재합니다. 기본 경로가 위 생성 파일들로 설정되어 있습니다.

```bash
.venv/bin/python3 scripts/database/seed_local_data.py
```

### 4. 챗봇 실행

```bash
.venv/bin/python3 scripts/rag/chat.py "IRP는 어떤 제도야?"
```

추천 질문 예시입니다.

```bash
.venv/bin/python3 scripts/rag/chat.py "IRP에서 안전하게 10년 동안 노후 준비용 연금상품을 추천해줘"
```

출력에는 처리 상태, 답변, 부족한 정보, 후속 질문, 출처가 포함됩니다.

```json
{
  "status": "ANSWER",
  "answer": "검색 근거에 기반한 답변",
  "missing_fields": [],
  "follow_up_question": null,
  "sources": []
}
```

## 로그

`data/logs/chat_interactions.jsonl`에는 요청 하나당 같은 `request_id`를 가진 두 행이 저장됩니다.

1. `QUERY_ANALYSIS`: 원 질문, 연금 관련성, 질문 유형, 추출한 사용자 조건
2. `FINAL_RESPONSE`: RAG 근거를 포함한 최종 LLM 입력, 선택된 문서, 최종 답변

로그에는 사용자가 말한 개인정보가 들어갈 수 있으므로 `data/`는 Git에 포함하지 않습니다.

## Langfuse 실행 추적

Langfuse를 설정하면 한 질문을 하나의 추적으로 보고, 그 안에서 다음 순서를 확인할 수 있습니다.

```text
사용자 질문
  → 질문 분석을 위한 HyperCLOVA 호출
  → 상품 DB 후보 필터(추천 질문일 때)
  → Policy / Product RAG 검색과 선택된 Chunk
  → 최종 답변을 위한 HyperCLOVA 호출
```

먼저 선택 의존성을 설치하고, `.env`에 Langfuse 프로젝트 키를 넣습니다.

```bash
.venv/bin/python3 -m pip install -r requirements-observability.txt
```

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

설정 후 기존과 같은 챗봇 명령을 실행하면 Langfuse 대시보드에서 추적을 볼 수 있습니다. Langfuse에는 질문, LLM 프롬프트·응답, 추출한 사용자 조건, 선택된 문서 ID가 전송되므로 실제 서비스에서는 개인정보 처리 방침과 접근 권한을 먼저 확인해야 합니다. 키 또는 패키지가 없으면 Langfuse는 비활성화되고 로컬 `data/logs/chat_interactions.jsonl` 로그만 남습니다.

## 테스트와 평가

```bash
.venv/bin/python3 -m pytest -q
```

대표 질문 묶음을 실제 챗봇에 실행하려면 다음 명령을 사용합니다.

```bash
.venv/bin/python3 scripts/evaluation/run_chat_cases.py
```

## 현재 범위와 다음 확장

현재는 다음을 구현했습니다.

- PostgreSQL 상품 조건 필터
- pgvector 기반 Policy RAG / Product RAG
- 1차 키워드 확인 + 2차 LLM 연금 관련성 확인
- 추천 질문의 사용자 조건 부족 역질문
- HyperCLOVA 근거 기반 답변과 출처 반환
- 요청·분석·검색 결과·답변 로그

다음 확장 후보입니다.

- 상품 설명·상품 비교 질문에서 상품명으로 `product_id`를 찾는 기능
- 세제·수령·중도인출 같은 세부 질문 유형별 필수 정보 규칙
- LLM이 `PRODUCT_DB`, `POLICY_RAG`, `PRODUCT_RAG` 중 필요한 데이터원을 선택하는 조회 계획
- FastAPI API와 세션 기반 사용자 정보 유지
- Rule Engine, 출력 안전성 검증, 대표 질문 평가 개선
