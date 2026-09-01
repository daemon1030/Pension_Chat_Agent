# 연금 RAG 상담 API

연금 제도·규정 문서와 상품 데이터를 검색해 답변하는 FastAPI 서비스입니다.

## 사전 준비

프로젝트 루트에 `.env` 파일을 만들고 CLOVA Studio API 키와 PostgreSQL 설정을 입력합니다.

```bash
cp .env.example .env
```

최소한 아래 값은 설정해야 합니다.

```dotenv
CLOVASTUDIO_API_KEY=발급받은_API_키
POSTGRES_DB=pension_agent
POSTGRES_USER=pension_app
POSTGRES_PASSWORD=안전한_비밀번호
```

Docker로 최초 실행하기 전에 아래 데이터 파일이 있어야 합니다.

```text
data/embeddings/rag_embeddings.jsonl
data/embeddings/product_embeddings_from_preprocessing.jsonl
data/product_db_ready/product_classes.json
```

## Docker 실행

### 처음 실행: DB 생성과 데이터 적재

```bash
docker compose -p pension-agent up -d postgres
docker compose -p pension-agent --profile seed run --rm seed
docker compose -p pension-agent up -d --build app
```

서비스 상태를 확인합니다.

```bash
curl http://localhost/health
```

정상 응답:

```json
{"status":"ok"}
```

질문을 보냅니다.

```bash
curl -G "http://localhost/answer" \
  --data-urlencode "question_id=test-001" \
  --data-urlencode "question=IRP가 무엇인지 알려줘" \
  | python3 -m json.tool
```

코드를 수정한 뒤 앱만 다시 반영하려면 다음을 실행합니다.

```bash
docker compose -p pension-agent up -d --build --force-recreate app
```

로그 확인:

```bash
docker compose -p pension-agent logs -f app
```

서비스를 중지하려면:

```bash
docker compose -p pension-agent down
```

`down`은 컨테이너와 네트워크만 중지합니다. DB 데이터까지 지우려면 별도로 볼륨을 삭제해야 하며, 이는 복구하기 어렵습니다.

## 로컬 실행

로컬에서 실행하려면 PostgreSQL + pgvector가 실행 중이고, `.env`의 `PENSION_DATABASE_DSN`이 그 DB를 가리켜야 합니다. DB에는 위 RAG·상품 데이터가 미리 적재돼 있어야 합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-app.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

다른 터미널에서 실행을 확인합니다.

```bash
curl http://localhost:8000/health
```

## API 응답 형태

```json
{
  "question_id": "test-001",
  "question": "IRP가 무엇인지 알려줘",
  "retrieved_context": [
    {"document_id": "DOC_014", "page": 1}
  ],
  "think_trace": "연금 정보 질문으로 분류 → POLICY_RAG 문서 5건 검색 → 근거 기반 답변 생성",
  "answer": "IRP는 ..."
}
```
