"""CLOVA Studio 임베딩 API Adapter.

API 키는 환경변수에서만 읽으며, 코드나 생성 데이터에 기록하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_HOST = "clovastudio.stream.ntruss.com"
DEFAULT_PATH = "/v1/api-tools/embedding/v2"


class EmbeddingApiError(RuntimeError):
    """CLOVA Studio 임베딩 API 호출 또는 응답 형식 오류."""


class EmbeddingRateLimitError(EmbeddingApiError):
    """API 요청 한도를 초과한 경우. 재시도 대기 시간을 함께 보관한다."""

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def load_local_env(path: Path = Path(".env")) -> None:
    """의존성 없이 프로젝트 루트의 .env를 읽는다.

    이미 배포 환경에 설정된 값은 덮어쓰지 않는다.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class ClovaEmbeddingSettings:
    api_key: str
    host: str = DEFAULT_HOST
    request_id: str | None = None
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "ClovaEmbeddingSettings":
        load_local_env()
        api_key = os.getenv("CLOVASTUDIO_API_KEY")
        if not api_key:
            raise EmbeddingApiError("CLOVASTUDIO_API_KEY 환경변수가 설정되지 않았습니다.")
        if not api_key.startswith("Bearer "):
            api_key = f"Bearer {api_key}"
        return cls(
            api_key=api_key,
            host=os.getenv("CLOVASTUDIO_EMBEDDING_HOST", DEFAULT_HOST),
            request_id=os.getenv("CLOVASTUDIO_REQUEST_ID"),
        )


class ClovaEmbeddingClient:
    """질문과 RAG Chunk를 동일한 CLOVA 임베딩 모델로 변환한다."""

    def __init__(self, settings: ClovaEmbeddingSettings) -> None:
        self._settings = settings

    @classmethod
    def from_env(cls) -> "ClovaEmbeddingClient":
        return cls(ClovaEmbeddingSettings.from_env())

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("빈 문자열은 임베딩할 수 없습니다.")
        request_id = self._settings.request_id or str(uuid4())
        connection = http.client.HTTPSConnection(self._settings.host, timeout=self._settings.timeout_seconds)
        try:
            connection.request(
                "POST",
                DEFAULT_PATH,
                body=json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": self._settings.api_key,
                    "X-NCP-CLOVASTUDIO-REQUEST-ID": request_id,
                },
            )
            response = connection.getresponse()
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            retry_after = response.getheader("Retry-After")
        except (OSError, json.JSONDecodeError) as error:
            raise EmbeddingApiError("CLOVA Studio 임베딩 API 호출에 실패했습니다.") from error
        finally:
            connection.close()

        status = payload.get("status", {})
        if status.get("code") != "20000":
            message = str(status.get("message", payload))
            if "rate" in message.lower() or "too many requests" in message.lower():
                try:
                    retry_after_seconds = float(retry_after) if retry_after else None
                except ValueError:
                    retry_after_seconds = None
                raise EmbeddingRateLimitError(f"임베딩 API 요청 한도 초과: {message}", retry_after_seconds)
            raise EmbeddingApiError(f"임베딩 API 오류: {message}")
        embedding = payload.get("result", {}).get("embedding")
        if not isinstance(embedding, list) or not all(isinstance(value, (int, float)) for value in embedding):
            raise EmbeddingApiError("임베딩 API 응답에 숫자 벡터가 없습니다.")
        return [float(value) for value in embedding]
