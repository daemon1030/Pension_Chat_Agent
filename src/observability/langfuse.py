"""Langfuse를 선택적으로 연결하는 실행 관찰 도구.

Langfuse 패키지와 API 키가 모두 준비된 경우에만 외부 추적을 보낸다.
따라서 로컬 개발·테스트 환경에서는 기존 챗봇 흐름을 바꾸지 않는다.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Any, Iterator


def _get_client() -> Any | None:
    """설정된 경우에만 Langfuse 클라이언트를 만든다."""
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse import get_client
    except ImportError:
        return None
    return get_client()


@contextmanager
def observe(
    name: str,
    *,
    as_type: str = "span",
    input: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any | None]:
    """현재 요청의 하위 단계로 Langfuse 관찰 항목을 남긴다.

    Langfuse가 설정되지 않았으면 ``None``을 넘겨 주는 빈 context manager처럼 동작한다.
    """
    client = _get_client()
    if client is None:
        yield None
        return

    with client.start_as_current_observation(
        as_type=as_type,
        name=name,
        input=input,
        metadata=metadata,
    ) as observation:
        yield observation


def update_observation(observation: Any | None, **values: Any) -> None:
    """Langfuse 비활성 상태에서도 같은 코드로 결과를 기록할 수 있게 한다."""
    if observation is not None:
        observation.update(**values)


def flush() -> None:
    """짧게 실행되고 끝나는 CLI가 추적 전송을 기다리도록 한다."""
    client = _get_client()
    if client is not None:
        client.flush()
