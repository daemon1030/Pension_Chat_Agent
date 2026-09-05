# API 서버 요청 방법

기본 서버 주소는 `http://101.79.24.1`입니다

## macOS (zsh)

서버 상태를 확인합니다.

```bash
SERVER_URL="http://101.79.24.1"
curl "$SERVER_URL/health"
```

정상 응답:

```json
{"status":"ok"}
```

연금 질문을 보냅니다.

```bash
SERVER_URL="http://101.79.24.1"

curl -G "$SERVER_URL/answer" \
  --data-urlencode "question_id=test-001" \
  --data-urlencode "question=IRP가 무엇인지 알려줘"
```

응답을 보기 좋게 출력하려면 마지막에 `| python3 -m json.tool --no-ensure-ascii`를 추가합니다.

## Windows (PowerShell)

서버 상태를 확인합니다.

```powershell
$ServerUrl = "http://101.79.24.1"
curl.exe "$ServerUrl/health"
```

연금 질문을 보냅니다.

```powershell
$ServerUrl = "http://101.79.24.1"

curl.exe -G "$ServerUrl/answer" `
  --data-urlencode "question_id=test-001" `
  --data-urlencode "question=IRP가 무엇인지 알려줘"
```

## 응답 형식

`/answer`는 다음 형식으로 응답합니다.

```json
{
  "question_id": "test-001",
  "question": "IRP가 무엇인지 알려줘",
  "retrieved_context": [
    {"document_id": "DOC_014", "page": 1}
  ],
  "think_trace": "연금 정보 질문으로 분류 → POLICY_RAG 문서 5건 검색 → 근거 기반 답변 생성",
  "answer": "근거 기반 답변"
}
```

`503`과 함께 `현재 답변을 생성할 수 없습니다`가 응답되면 서버에서 다음 로그를 확인합니다.

```bash
docker compose -p pension-agent logs --tail=100 app
```
