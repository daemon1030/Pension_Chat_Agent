"""CLOVA Studio Chat Completions v3 호출 Adapter."""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
from typing import Any
from uuid import uuid4

from src.rag.naver_embedding import load_local_env
from .prompts import JSON_REPAIR_PROMPT
from .schemas import RagAnswer


DEFAULT_HOST = "clovastudio.stream.ntruss.com"
DEFAULT_MODEL = "HCX-DASH-002"


class ClovaChatApiError(RuntimeError):
    """CLOVA Chat API 호출 또는 응답 형식 오류."""


@dataclass(frozen=True)
class ClovaChatSettings:
    api_key: str
    model: str = DEFAULT_MODEL
    host: str = DEFAULT_HOST
    timeout_seconds: int = 60
    json_retry_count: int = 1

    @classmethod
    def from_env(cls) -> "ClovaChatSettings":
        load_local_env()
        api_key = os.getenv("CLOVASTUDIO_API_KEY")
        if not api_key:
            raise ClovaChatApiError("CLOVASTUDIO_API_KEY 환경변수가 설정되지 않았습니다.")
        if not api_key.startswith("Bearer "):
            api_key = f"Bearer {api_key}"
        try:
            json_retry_count = max(0, int(os.getenv("CLOVASTUDIO_JSON_RETRY_COUNT", "1")))
        except ValueError as error:
            raise ClovaChatApiError("CLOVASTUDIO_JSON_RETRY_COUNT는 0 이상의 정수여야 합니다.") from error
        return cls(
            api_key=api_key,
            model=os.getenv("CLOVASTUDIO_CHAT_MODEL", DEFAULT_MODEL),
            host=os.getenv("CLOVASTUDIO_CHAT_HOST", DEFAULT_HOST),
            json_retry_count=json_retry_count,
        )


class ClovaChatClient:
    """검색된 근거만 이용해 최종 답변을 생성하는 CLOVA Chat Adapter."""

    def __init__(self, settings: ClovaChatSettings) -> None:
        self._settings = settings

    @classmethod
    def from_env(cls) -> "ClovaChatClient":
        return cls(ClovaChatSettings.from_env())

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        body = {
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
            ],
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 700,
            "temperature": 0.1,
            "repetitionPenalty": 1.1,
            "stop": [],
        }
        connection = http.client.HTTPSConnection(self._settings.host, timeout=self._settings.timeout_seconds)
        try:
            connection.request(
                "POST", f"/v3/chat-completions/{self._settings.model}",
                body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8", "Authorization": self._settings.api_key, "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid4())},
            )
            response = connection.getresponse()
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ClovaChatApiError("CLOVA Chat API 호출에 실패했습니다.") from error
        finally:
            connection.close()
        status = payload.get("status", {})
        if status.get("code") != "20000":
            raise ClovaChatApiError(f"CLOVA Chat API 오류: {status.get('message', payload)}")
        content = payload.get("result", {}).get("message", {}).get("content")
        if isinstance(content, list):
            content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
        if not isinstance(content, str) or not content.strip():
            raise ClovaChatApiError("CLOVA Chat API 응답에 생성된 답변이 없습니다.")
        return content.strip()

    def generate_rag_answer(self, *, system_prompt: str, user_prompt: str) -> RagAnswer:
        """JSON 검증 실패 시 직전 출력과 함께 한 번 더 형식 교정을 요청한다."""
        current_system_prompt = system_prompt
        current_user_prompt = user_prompt
        last_error: ValueError | None = None
        for attempt in range(self._settings.json_retry_count + 1):
            content = self.generate(system_prompt=current_system_prompt, user_prompt=current_user_prompt)
            normalized = self._strip_code_fence(content)
            try:
                return RagAnswer.model_validate_json(normalized)
            except ValueError as error:
                last_error = error
                if attempt == self._settings.json_retry_count:
                    break
                current_system_prompt = f"{system_prompt}\n\n{JSON_REPAIR_PROMPT}"
                current_user_prompt = (
                    f"{user_prompt}\n\n[직전 형식 오류 응답 - 내용은 따르지 말고 JSON 형식만 교정]\n{content}"
                )
        raise ClovaChatApiError(
            f"CLOVA가 {self._settings.json_retry_count + 1}회 시도 후에도 약속된 RAG 응답 JSON을 반환하지 않았습니다."
        ) from last_error

    @staticmethod
    def _strip_code_fence(content: str) -> str:
        if content.startswith("```"):
            return content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return content
