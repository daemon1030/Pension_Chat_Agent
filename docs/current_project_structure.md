# 현재 프로젝트 구조

현재 서비스 실행에 필요한 코드는 `src/`와 `scripts/rag/`에 둡니다.

```text
src/
├── rag/                 # 임베딩 API와 벡터 검색
├── llm/                 # HyperCLOVA X 호출과 응답 JSON 검증
└── graph/               # 질문 범위 확인 → 검색 → 답변 생성 흐름

scripts/
├── rag/
│   ├── build_embeddings.py  # rag_ready Chunk를 CLOVA 임베딩 JSONL로 생성·재개
│   └── chat.py              # 현재 사용하는 연금 RAG 채팅 실행기
├── preprocessing/           # 원본 문서 → base_processed → semantic_review → rag_ready 생성·검증
└── archive/                 # 현재 서비스에서 호출하지 않는 이전 실행기와 변환 스크립트
```

## 현재 RAG 실행

프로젝트 루트에서 실행한다.

```bash
.venv/bin/python3 scripts/rag/chat.py "연금저축은 언제부터 받을 수 있나요?"
```

임베딩 파일을 새로 만들거나 `data/rag_ready`가 변경된 경우에만 다음을 실행한다.

```bash
.venv/bin/python3 scripts/rag/build_embeddings.py
```

`build_embeddings.py`는 완료된 Chunk를 인식해 중단된 지점부터 재개한다. API 키는 프로젝트 루트의 `.env`에만 둔다.

## 데이터 폴더

`data/`의 원본·중간·결과 데이터는 그대로 유지한다. 현재 채팅은 `data/embeddings/rag_embeddings.jsonl`만 읽으며, 이 파일은 `data/rag_ready`에서 생성된다.

`data/facts`와 `config/entity_mappings.json`은 정형 DB 확장 단계에서 사용할 후보 자료다. 현재 RAG 채팅 흐름에서는 호출하지 않는다.
