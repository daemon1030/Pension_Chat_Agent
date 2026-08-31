"""상품 전처리 JSON을 적재 가능 여부에 따라 복사 분류한다."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.products.preprocessing_validation import validate_product_directory


def destination_for(result: dict[str, object], valid_directory: Path, review_directory: Path) -> Path:
    """ERROR가 없으면 적재 폴더, 하나라도 있으면 검토 폴더로 보낸다."""
    has_error = any(issue["severity"] == "ERROR" for issue in result["issues"])
    return (review_directory if has_error else valid_directory) / Path(str(result["file"])).name


def main() -> None:
    parser = argparse.ArgumentParser(description="상품 전처리 JSON을 적재 가능·검토 필요 폴더로 복사 분류")
    parser.add_argument("--input-dir", type=Path, default=PROJECT_ROOT / "data" / "전처리 json 2")
    parser.add_argument("--valid-dir", type=Path, default=PROJECT_ROOT / "data" / "상품 전처리")
    parser.add_argument("--review-dir", type=Path, default=PROJECT_ROOT / "data" / "상품 전처리_검토필요")
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "reports" / "product_preprocessing_classification.json",
    )
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        parser.error(f"입력 폴더를 찾을 수 없습니다: {args.input_dir}")

    validation = validate_product_directory(args.input_dir)
    args.valid_dir.mkdir(parents=True, exist_ok=True)
    args.review_dir.mkdir(parents=True, exist_ok=True)

    copied_valid: list[str] = []
    copied_review: list[str] = []
    for result in validation["results"]:
        source = Path(result["file"])
        destination = destination_for(result, args.valid_dir, args.review_dir)
        if destination.exists():
            raise FileExistsError(f"대상 파일이 이미 존재합니다: {destination}")
        shutil.copy2(source, destination)
        (copied_review if destination.parent == args.review_dir else copied_valid).append(destination.name)

    report = {
        **validation,
        "valid_destination": str(args.valid_dir),
        "review_destination": str(args.review_dir),
        "copied_valid_files": copied_valid,
        "copied_review_files": copied_review,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"분류 완료: 적재 가능 {len(copied_valid)}개 → {args.valid_dir}\n"
        f"검토 필요 {len(copied_review)}개 → {args.review_dir}\n"
        f"상세 보고서: {args.report}"
    )


if __name__ == "__main__":
    main()
