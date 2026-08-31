"""CLOVA 문단 나누기를 규정 RAG 청크 경계에 안전하게 적용한다."""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
import re
from typing import Any, Protocol
from uuid import uuid4

from src.rag.naver_embedding import load_local_env


DEFAULT_HOST = "clovastudio.stream.ntruss.com"
DEFAULT_PATH = "/v1/api-tools/segmentation"
EXCEPTION_PREFIX = re.compile(r"^(?:다만|단\s*[,:：]|예외|※)")


class SegmentationApiError(RuntimeError):
    """CLOVA 문단 나누기 API 호출 또는 응답 형식 오류."""


@dataclass(frozen=True)
class ClovaSegmentationSettings:
    api_key: str
    host: str = DEFAULT_HOST
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "ClovaSegmentationSettings":
        load_local_env()
        api_key = os.getenv("CLOVASTUDIO_API_KEY")
        if not api_key:
            raise SegmentationApiError("CLOVASTUDIO_API_KEY 환경변수가 설정되지 않았습니다.")
        if not api_key.startswith("Bearer "):
            api_key = f"Bearer {api_key}"
        return cls(
            api_key=api_key,
            host=os.getenv("CLOVASTUDIO_SEGMENTATION_HOST", DEFAULT_HOST),
        )


class Segmenter(Protocol):
    def segment(self, text: str) -> list[str]: ...


class ClovaSegmentationClient:
    """CLOVA 문단 나누기 API의 topicSeg 결과를 문자열 문단 목록으로 변환한다."""

    def __init__(
        self,
        settings: ClovaSegmentationSettings,
        *,
        alpha: float = -100,
        segment_count: int = -1,
    ) -> None:
        self._settings = settings
        self._alpha = alpha
        self._segment_count = segment_count

    @classmethod
    def from_env(
        cls, *, alpha: float = -100, segment_count: int = -1
    ) -> "ClovaSegmentationClient":
        return cls(ClovaSegmentationSettings.from_env(), alpha=alpha, segment_count=segment_count)

    def segment(self, text: str) -> list[str]:
        if not text.strip():
            return []
        if len(text) > 120_000:
            raise ValueError("CLOVA 문단 나누기 입력은 120,000자를 초과할 수 없습니다.")
        body = {
            "text": text,
            "alpha": self._alpha,
            "segCnt": self._segment_count,
            # 금융 규정의 조건·예외를 글자 수로 다시 분할하지 않는다.
            "postProcess": False,
        }
        connection = http.client.HTTPSConnection(
            self._settings.host, timeout=self._settings.timeout_seconds
        )
        try:
            connection.request(
                "POST",
                DEFAULT_PATH,
                body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": self._settings.api_key,
                    "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid4()),
                },
            )
            response = connection.getresponse()
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SegmentationApiError("CLOVA 문단 나누기 API 호출에 실패했습니다.") from error
        finally:
            connection.close()

        status = payload.get("status", {})
        if status.get("code") != "20000":
            raise SegmentationApiError(f"CLOVA 문단 나누기 API 오류: {status.get('message', payload)}")
        topic_segments = payload.get("result", {}).get("topicSeg")
        if not isinstance(topic_segments, list):
            raise SegmentationApiError("CLOVA 문단 나누기 응답에 topicSeg 배열이 없습니다.")
        segments: list[str] = []
        for topic in topic_segments:
            if not isinstance(topic, list) or not all(isinstance(sentence, str) for sentence in topic):
                raise SegmentationApiError("CLOVA 문단 나누기 응답의 topicSeg 형식이 올바르지 않습니다.")
            content = "\n".join(sentence.strip() for sentence in topic if sentence.strip())
            if content:
                segments.append(content)
        return segments


def is_exception_segment(segment: str) -> bool:
    """단서로 시작하는 문단은 앞 조건과 분리하면 의미가 달라질 수 있다."""
    first_line = next((line.strip() for line in segment.splitlines() if line.strip()), "")
    return bool(EXCEPTION_PREFIX.match(first_line))


def split_to_max_chars(text: str, *, max_chars: int) -> list[str]:
    """의미 문단이 너무 길 때만 줄 경계에서 추가 분할한다."""
    if len(text) <= max_chars:
        return [text]
    result: list[str] = []
    current: list[str] = []
    length = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if current and length + len(line) + 1 > max_chars:
            result.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        result.append("\n".join(current))
    return result or [text]


def refine_section(
    text: str,
    segmenter: Segmenter,
    *,
    max_chars: int = 1200,
) -> list[str]:
    """주제 문단을 만들고 예외 문단을 직전 조건 문단과 결합한다.

    문단 나누기는 청크 경계 후보일 뿐이다. ``다만``·``예외``로 시작하는
    문단은 독립 청크가 되지 않게 하며, 최대 길이는 그 외 긴 문단에만 적용한다.
    """
    segments = [segment.strip() for segment in segmenter.segment(text) if segment.strip()]
    if not segments:
        return []

    protected: list[tuple[str, bool]] = []
    for segment in segments:
        if protected and is_exception_segment(segment):
            previous, _ = protected[-1]
            protected[-1] = (f"{previous}\n{segment}", True)
        else:
            protected.append((segment, is_exception_segment(segment)))

    result: list[str] = []
    for segment, contains_exception in protected:
        if contains_exception:
            # 조건과 예외가 합쳐진 청크는 최대 길이보다 의미 보존을 우선한다.
            result.append(segment)
        else:
            result.extend(split_to_max_chars(segment, max_chars=max_chars))
    return result
