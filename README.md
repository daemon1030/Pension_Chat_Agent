# 연금 문서 기반 RAG (현재 MVP)

연금 문서 원본을 페이지·섹션 단위로 보존해 전처리하고, 네이버 CLOVA Studio 임베딩으로 관련 근거를 검색한 뒤 HyperCLOVA X가 근거 기반 답변을 만드는 프로젝트입니다.

현재 구현 범위는 **문서 전처리와 RAG 답변**입니다. PostgreSQL/pgvector 적재, 정형 Fact DB, Rule Engine, FastAPI는 아직 연결하지 않았습니다.

## 동작 구조

```text
data/raw
  → base_processed       원문을 문서·페이지·표·이미지 정보와 함께 보존
  → semantic_review      섹션 제목·주제·RAG 포함 여부·Fact 후보를 검토
  → rag_ready            RAG에 넣을 확정 Chunk 생성
  → embeddings           Chunk + CLOVA 임베딩 벡터(JSONL)
  → LangGraph            질문 범위 확인 → 벡터 검색 → CLOVA 답변 생성
```

현재 채팅 실행기는 `data/embeddings/rag_embeddings.jsonl`만 직접 읽습니다. 원본에서 다시 만들 때는 위 순서대로 전처리 단계를 실행합니다.

## 디렉터리 구조

```text
data/
├── raw/                 # 원본 PDF·Office 문서 (수정하지 않음)
├── base_processed/      # 원문 보존형 중간 JSON
├── semantic_review/     # Section/Topic/RAG·Fact 후보 검토 JSON
├── rag_ready/           # RAG 검색용 확정 Chunk JSON
├── embeddings/          # Chunk와 임베딩 벡터를 담은 JSONL
├── facts/               # 향후 정형 DB 적재용 Fact 후보
└── raw_invest_recommand/# 별도 투자추천 원본 자료, 현재 흐름에서는 미사용

src/
├── rag/                 # 임베딩 생성과 벡터 검색
├── llm/                 # HyperCLOVA X 호출·JSON 검증
└── graph/               # RAG LangGraph 흐름

scripts/
├── rag/                 # 현재 사용하는 실행기
├── preprocessing/       # 원본 전처리·검증·RAG Chunk 생성 도구
└── archive/             # 현재 실행 흐름에서 사용하지 않는 이전 코드

tests/
├── rag/                 # 검색기·임베딩 재개 처리 테스트
├── llm/                 # CLOVA JSON 재시도·정규화 테스트
└── graph/               # 범위 제한·RAG 워크플로 테스트
```

## 코드별 역할

### `src/rag/`

| 파일 | 역할 |
|---|---|
| `naver_embedding.py` | `.env`에서 API 키를 읽고 CLOVA Studio Embedding v2 API를 호출합니다. 요청 한도 초과 시 재시도에 사용할 대기 시간도 전달합니다. |
| `retriever.py` | `rag_ready` JSON을 읽고, 임베딩 이전에 사용할 수 있는 단순 키워드 검색기와 공통 `RagChunk` 모델을 제공합니다. |
| `vector_retriever.py` | 임베딩 JSONL을 메모리에 읽고, 질문을 임베딩한 뒤 코사인 유사도로 Top-K Chunk를 검색합니다. 같은 섹션이 중복 반환되지 않게 합니다. |

### `src/llm/`

| 파일 | 역할 |
|---|---|
| `hyperclova.py` | HyperCLOVA X Chat Completions API 호출 Adapter입니다. 모델 응답이 JSON Schema에 맞지 않으면 JSON만 다시 요청합니다. |
| `prompts.py` | 근거 밖의 내용을 추측하지 않기 위한 시스템 프롬프트와 JSON 재요청 프롬프트를 둡니다. |
| `schemas.py` | 최종 응답 형식(`ANSWER` 또는 `NEED_MORE_INFO`)을 Pydantic으로 검증합니다. 부족 정보의 유사 필드명도 안전하게 정규화합니다. |

### `src/graph/`

| 파일 | 역할 |
|---|---|
| `state.py` | 질문, 검색 결과, 답변, 출처, 부족 정보 등 LangGraph가 전달하는 상태를 정의합니다. |
| `nodes.py` | 연금 질문인지 확인하고, 검색 결과를 근거 문맥과 출처로 만들며, CLOVA 최종 답변을 생성하는 노드입니다. 연금 외 질문은 API 호출 없이 종료합니다. |
| `workflow.py` | `범위 확인 → 벡터 검색 → CLOVA 답변` 순서의 현재 워크플로를 조립합니다. 키워드 검색용·임베딩 검색용 워크플로도 테스트/비교용으로 제공합니다. |

### `scripts/rag/` — 현재 실행 파일

| 파일 | 역할 |
|---|---|
| `build_embeddings.py` | `rag_ready`의 Chunk를 CLOVA 임베딩으로 변환해 `data/embeddings/rag_embeddings.jsonl`에 저장합니다. 중단되면 완료한 Chunk를 건너뛰고 재개하며, API 속도 제한은 지수 대기 후 재시도합니다. |
| `chat.py` | 현재 사용자 질문을 받아 LangGraph RAG를 실행하고 `status`, `answer`, `missing_fields`, `follow_up_question`, `sources` JSON을 출력합니다. |

### `scripts/preprocessing/` — 전처리·검증 도구

| 파일 | 역할 |
|---|---|
| `build_base_processed.py` | `raw`의 PDF/Office 원본을 문서·페이지·텍스트·표·이미지 정보가 있는 기본 JSON으로 변환합니다. |
| `enrich_base_processed.py` | 기본 JSON에 문서별 검토·보강 내용을 추가합니다. |
| `ocr_pdf_images.py` | 이미지가 포함된 PDF 페이지를 OCR해 이미지 텍스트를 보관합니다. OCR 결과는 검토 대상으로 표시합니다. |
| `fill_scanned_documents.py` | 텍스트 레이어가 부족한 검토 대상 문서의 확인된 시각 텍스트를 보강합니다. |
| `validate_base_processed.py` | 원본 재변환 결과와 `base_processed`를 대조해 텍스트·표·FAQ·Fact 근거 누락을 검사합니다. |
| `build_semantic_review.py` | `base_processed`를 Section/Topic/RAG 사용 여부/Fact 후보를 검토할 수 있는 형식으로 만듭니다. |
| `apply_review_batch_011_023.py` | DOC 011~023의 검토 결과를 반영합니다. |
| `apply_review_batch_text_documents.py` | 텍스트 레이어가 있는 나머지 문서의 검토 결과를 반영합니다. |
| `apply_remaining_semantic_review.py` | 남은 문서의 의미 검토 결과를 반영합니다. |
| `extract_missing_facts_011_022.py` | DOC 011~022에서 원문에 명시된 핵심 수치 Fact를 보강합니다. |
| `extract_clear_facts_core_documents.py` | 핵심 문서에서 명확히 확인되는 수치 Fact를 보강합니다. |
| `build_final_knowledge.py` | 검토 JSON에서 RAG Chunk와 향후 정형 DB용 Fact 후보를 각각 `rag_ready`, `facts`로 생성합니다. |

`scripts/archive/`의 파일은 이전 검색·변환 방식입니다. 현재 채팅 서비스는 호출하지 않으며, 삭제 대신 이력 보관합니다.

## 실행 방법

명령은 프로젝트 루트에서 실행합니다. 현재 저장소는 기존 `.venv`를 사용합니다.

### 1. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 만들고 키를 넣습니다. `.env`는 Git에 올리지 않습니다.

```dotenv
CLOVASTUDIO_API_KEY=Bearer 발급받은_API_키
# 선택: 기본값은 HCX-DASH-002
CLOVASTUDIO_CHAT_MODEL=HCX-DASH-002
# 선택: 잘못된 JSON 응답을 다시 요청하는 횟수, 기본값 1
CLOVASTUDIO_JSON_RETRY_COUNT=1
```

### 2. 임베딩 생성 또는 재개

`data/rag_ready`가 새로 생성·변경된 경우에만 실행합니다.

```bash
.venv/bin/python3 scripts/rag/build_embeddings.py
```

속도 제한이 발생하면 자동으로 대기 후 재시도합니다. 작업 도중 중단되어도 같은 명령을 실행하면 기존 완료분을 유지하고 이어서 처리합니다.

### 3. RAG 채팅 실행

```bash
.venv/bin/python3 scripts/rag/chat.py "연금저축은 언제부터 받을 수 있나요?"
```

검색할 Chunk 수를 바꾸려면 다음처럼 실행합니다.

```bash
.venv/bin/python3 scripts/rag/chat.py "IRP 세액공제 한도는?" --top-k 5
```

출력 예시는 다음과 같습니다.

```json
{
  "status": "ANSWER",
  "answer": "검색 근거에 기반한 답변",
  "missing_fields": [],
  "follow_up_question": null,
  "sources": [
    {"document_id": "DOC_001", "document_name": "문서명", "page": 1}
  ]
}
```

개인 조건이 필요한 질문에는 `NEED_MORE_INFO`와 함께 필요한 정보 및 역질문을 반환합니다. 연금과 무관한 질문에는 `OUT_OF_SCOPE`를 반환합니다.

### 4. 테스트

```bash
.venv/bin/python3 -m pytest -q
```

## 현재 한계와 다음 단계

- 벡터는 현재 로컬 JSONL을 메모리에 읽어 검색합니다. 운영 규모에서는 `pgvector` 검색기로 교체합니다.
- `data/facts`는 생성돼 있지만 PostgreSQL과 Rule Engine에는 아직 적재·연결하지 않았습니다.
- FastAPI `/chat`, 대화 세션 복원, 정형 DB 조회, 금융 판단 Rule Engine은 아직 구현 대상이 아닙니다.
- OCR과 수기 보강 텍스트는 검토 표시가 남아 있으므로, 운영 반영 전 원문 대조가 필요합니다.
