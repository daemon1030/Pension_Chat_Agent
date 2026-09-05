"""검수된 정보형/추천형 답변 데이터를 HyperCLOVA 튜닝 JSONL로 합친다."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INFORMATION = (
    PROJECT_ROOT
    / "tuning_data"
    / "1 information_answer_train_INFO225_SOURCE_GROUNDED_REVALIDATED.json"
)
DEFAULT_RECOMMENDATION = (
    PROJECT_ROOT / "tuning_data" / "12_recommendation_answer_train_QA_PASSED.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "tuning_data" / "hyperclova_answer_train_457.jsonl"

MAX_EXAMPLE_CHARS = 8_000
TARGET_EXAMPLE_CHARS = 7_900
TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣().%~-]*")


def load_json_array(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"JSON 객체 배열이 아닙니다: {path}")
    return value


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def example_chars(row: dict[str, Any]) -> int:
    return sum(len(str(row.get(field, ""))) for field in ("System_Prompt", "Text", "Completion"))


def serialized_line_chars(
    *, system_prompt: str, conversation_id: int, text: str, completion: str
) -> int:
    """JSON 이스케이프까지 반영한 실제 JSONL 한 줄의 길이를 반환한다."""
    return len(
        compact_json(
            {
                "System_Prompt": system_prompt,
                "C_ID": conversation_id,
                "T_ID": 0,
                "Text": text,
                "Completion": completion,
            }
        )
    )


def parse_analysis(text: str) -> tuple[int, dict[str, Any], int]:
    start = text.index('{"intent"')
    analysis, consumed = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(analysis, dict):
        raise ValueError("질문 분석 블록이 JSON 객체가 아닙니다.")
    return start, analysis, start + consumed


def evidence_score(block: str, answer: str, referenced_product_ids: set[str]) -> int:
    lowered = block.lower()
    terms = {token.lower() for token in TOKEN_PATTERN.findall(answer) if len(token) >= 2}
    lexical_score = sum(min(len(term), 12) for term in terms if term in lowered)
    product_bonus = 10_000 if any(
        block.startswith(f"[PRODUCT_{product_id} ") for product_id in referenced_product_ids
    ) else 0
    return product_bonus + lexical_score


def fit_recommendation_text(
    *, system_prompt: str, conversation_id: int, text: str, completion: str, answer: str
) -> str:
    """근거 블록 단위로 선별해 튜닝 서비스의 레코드 길이 제한을 맞춘다."""
    analysis_start, analysis, analysis_end = parse_analysis(text)
    suffix = text[analysis_end:]
    evidence_header_end = suffix.find("\n", 2) + 1
    if evidence_header_end <= 0:
        raise ValueError("검색 근거 헤더를 찾을 수 없습니다.")

    evidence = suffix[evidence_header_end:]
    evidence_blocks = re.split(r"\n\n(?=\[)", evidence)
    candidates = analysis.get("candidate_products", [])
    referenced_product_ids = {
        str(candidate.get("product_id"))
        for candidate in candidates
        if candidate.get("product_name", "") in answer
        or (
            candidate.get("class_name")
            and f"[{candidate['class_name']}]" in answer
        )
    }

    base_text = (
        text[:analysis_start]
        + compact_json(analysis)
        + suffix[:evidence_header_end]
    )
    if serialized_line_chars(
        system_prompt=system_prompt,
        conversation_id=conversation_id,
        text=base_text,
        completion=completion,
    ) > TARGET_EXAMPLE_CHARS:
        raise ValueError("후보 JSON만으로 튜닝 레코드 길이 제한을 초과합니다.")

    ranked_blocks = sorted(
        enumerate(evidence_blocks),
        key=lambda item: (evidence_score(item[1], answer, referenced_product_ids), -item[0]),
        reverse=True,
    )
    selected_indexes: list[int] = []
    for index, block in ranked_blocks:
        candidate_indexes = sorted([*selected_indexes, index])
        candidate_text = base_text + "\n\n".join(
            evidence_blocks[candidate_index] for candidate_index in candidate_indexes
        )
        if serialized_line_chars(
            system_prompt=system_prompt,
            conversation_id=conversation_id,
            text=candidate_text,
            completion=completion,
        ) <= TARGET_EXAMPLE_CHARS:
            selected_indexes = candidate_indexes

    selected_indexes.sort()
    selected_blocks = [evidence_blocks[index] for index in selected_indexes]
    for product_id in referenced_product_ids:
        if not any(block.startswith(f"[PRODUCT_{product_id} ") for block in selected_blocks):
            raise ValueError(f"답변에 사용된 상품 근거를 보존하지 못했습니다: {product_id}")

    return base_text + "\n\n".join(selected_blocks)


def normalize_row(row: dict[str, Any], conversation_id: int) -> tuple[dict[str, Any], bool]:
    required = {"System_Prompt", "C_ID", "T_ID", "Text", "Completion"}
    missing = required.difference(row)
    if missing:
        raise ValueError(f"필수 필드가 없습니다: {sorted(missing)}")

    completion = (
        row["Completion"]
        if isinstance(row["Completion"], str)
        else compact_json(row["Completion"])
    )
    completion_value = json.loads(completion)
    if not isinstance(completion_value, dict) or not completion_value.get("answer"):
        raise ValueError(f"유효하지 않은 Completion입니다: 원본 C_ID={row['C_ID']}")

    normalized = {
        "System_Prompt": str(row["System_Prompt"]),
        "C_ID": conversation_id,
        "T_ID": 0,
        "Text": str(row["Text"]),
        "Completion": completion,
    }
    shortened = False
    if (
        example_chars(normalized) > MAX_EXAMPLE_CHARS
        or serialized_line_chars(
            system_prompt=normalized["System_Prompt"],
            conversation_id=conversation_id,
            text=normalized["Text"],
            completion=completion,
        ) > MAX_EXAMPLE_CHARS
    ):
        normalized["Text"] = fit_recommendation_text(
            system_prompt=normalized["System_Prompt"],
            conversation_id=conversation_id,
            text=normalized["Text"],
            completion=completion,
            answer=str(completion_value["answer"]),
        )
        shortened = True

    if example_chars(normalized) > MAX_EXAMPLE_CHARS:
        raise ValueError(f"8,000자 제한을 초과합니다: 원본 C_ID={row['C_ID']}")
    if serialized_line_chars(
        system_prompt=normalized["System_Prompt"],
        conversation_id=conversation_id,
        text=normalized["Text"],
        completion=completion,
    ) > MAX_EXAMPLE_CHARS:
        raise ValueError(f"JSONL 한 줄 8,000자 제한을 초과합니다: 원본 C_ID={row['C_ID']}")
    return normalized, shortened


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--information", type=Path, default=DEFAULT_INFORMATION)
    parser.add_argument("--recommendation", type=Path, default=DEFAULT_RECOMMENDATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    information_rows = load_json_array(args.information)
    recommendation_rows = load_json_array(args.recommendation)
    source_rows = information_rows + recommendation_rows

    normalized_rows: list[dict[str, Any]] = []
    shortened_count = 0
    for conversation_id, source_row in enumerate(source_rows):
        normalized, shortened = normalize_row(source_row, conversation_id)
        normalized_rows.append(normalized)
        shortened_count += int(shortened)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(compact_json(row) + "\n" for row in normalized_rows),
        encoding="utf-8",
    )
    print(f"정보형: {len(information_rows)}건")
    print(f"추천형: {len(recommendation_rows)}건")
    print(f"전체: {len(normalized_rows)}건")
    print(f"길이 조정: {shortened_count}건")
    print(f"출력: {args.output}")


if __name__ == "__main__":
    main()
