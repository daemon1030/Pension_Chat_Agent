"""상품 전처리 JSON의 DB·Product RAG 적재 준비 상태를 검사한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.products.preprocessing_validation import validate_product_directory


def main() -> None:
    parser = argparse.ArgumentParser(description="상품 전처리 JSON 형식·필수값 검사")
    parser.add_argument(
        "--input-dir", type=Path, default=PROJECT_ROOT / "data" / "상품 전처리",
        help="검사할 상품 전처리 JSON 폴더",
    )
    parser.add_argument(
        "--report", type=Path, default=PROJECT_ROOT / "data" / "reports" / "product_preprocessing_validation.json",
        help="상세 검사 결과를 저장할 JSON 파일",
    )
    parser.add_argument("--strict", action="store_true", help="경고도 있으면 종료 코드 1을 반환")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        parser.error(f"입력 폴더를 찾을 수 없습니다: {args.input_dir}")
    report = validate_product_directory(args.input_dir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"검사 완료: 파일 {report['file_count']}개 / "
        f"오류 없는 파일 {report['valid_file_count']}개 / "
        f"오류 {report['error_count']}건 / 경고 {report['warning_count']}건"
    )
    print(f"상세 결과: {args.report}")
    if report["error_count"] or (args.strict and report["warning_count"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
