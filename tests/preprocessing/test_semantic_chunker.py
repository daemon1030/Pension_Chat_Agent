from src.preprocessing.semantic_chunker import refine_section


class FakeSegmenter:
    def __init__(self, segments: list[str]) -> None:
        self.segments = segments
        self.calls: list[str] = []

    def segment(self, text: str) -> list[str]:
        self.calls.append(text)
        return self.segments


def test_refine_section_merges_exception_with_the_preceding_condition():
    segmenter = FakeSegmenter([
        "가입하려면 계좌 유형과 위험 선호를 확인해야 합니다.",
        "다만, 법정 예외 사유가 있으면 별도 확인이 필요합니다.",
        "수수료는 상품 설명서에서 확인할 수 있습니다.",
    ])

    result = refine_section("원문", segmenter)

    assert result == [
        "가입하려면 계좌 유형과 위험 선호를 확인해야 합니다.\n다만, 법정 예외 사유가 있으면 별도 확인이 필요합니다.",
        "수수료는 상품 설명서에서 확인할 수 있습니다.",
    ]


def test_refine_section_splits_only_long_non_exception_segments():
    segmenter = FakeSegmenter([
        "첫 번째 규정입니다.\n두 번째 규정입니다.",
        "세 번째 규정입니다.",
        "다만, 이 예외는 앞 규정과 반드시 함께 보아야 합니다.",
    ])

    result = refine_section("원문", segmenter, max_chars=12)

    assert result[0] == "첫 번째 규정입니다."
    assert result[1] == "두 번째 규정입니다."
    assert result[2] == "세 번째 규정입니다.\n다만, 이 예외는 앞 규정과 반드시 함께 보아야 합니다."
