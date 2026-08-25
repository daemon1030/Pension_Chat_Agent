"""rag_ready JSON의 모든 Chunk를 CLOVA Studio 임베딩으로 변환한다."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.naver_embedding import ClovaEmbeddingClient, EmbeddingRateLimitError
from src.rag.retriever import load_rag_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="CLOVA Studio로 RAG Chunk 임베딩 생성")
    parser.add_argument("--input-dir", type=Path, default=PROJECT_ROOT / "data/rag_ready")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/embeddings/rag_embeddings.jsonl")
    parser.add_argument("--delay-seconds", type=float, default=1.1, help="요청 사이 대기 시간 (기본 1.1초)")
    parser.add_argument("--max-retries", type=int, default=8, help="속도 제한 발생 시 최대 재시도 횟수")
    args = parser.parse_args()

    client = ClovaEmbeddingClient.from_env()
    chunks = load_rag_chunks(args.input_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = args.output.with_suffix(args.output.suffix + ".tmp")
    progress_path = temporary_path if temporary_path.exists() else args.output
    completed_ids: set[str] = set()
    if progress_path.exists():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                completed_ids.add(json.loads(line)["chunk_id"])
    if progress_path == args.output and completed_ids:
        # 기존 완료 파일은 손대지 않고, 새 Chunk가 생겼을 때만 이어서 작성한다.
        args.output.replace(temporary_path)

    print(f"재개 지점: {len(completed_ids)}/{len(chunks)}개 완료")
    with temporary_path.open("a", encoding="utf-8") as output:
        for index, chunk in enumerate(chunks, 1):
            if chunk.chunk_id in completed_ids:
                continue
            text = "\n".join(filter(None, [chunk.document_title, chunk.section_title, chunk.topic, chunk.content]))
            for attempt in range(args.max_retries + 1):
                try:
                    embedding = client.embed(text)
                    break
                except EmbeddingRateLimitError as error:
                    if attempt == args.max_retries:
                        raise
                    wait_seconds = max(error.retry_after_seconds or 0, min(5 * (2**attempt), 60))
                    print(f"요청 한도 초과. {wait_seconds:.0f}초 대기 후 재시도 ({attempt + 1}/{args.max_retries})")
                    time.sleep(wait_seconds)
            record = {**chunk.to_dict(), "embedding": embedding}
            record.pop("score", None)
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            completed_ids.add(chunk.chunk_id)
            print(f"{index}/{len(chunks)} 임베딩 완료: {chunk.chunk_id}")
            time.sleep(args.delay_seconds)
    temporary_path.replace(args.output)
    print(f"완료: {len(chunks)}개 Chunk → {args.output}")


if __name__ == "__main__":
    main()
