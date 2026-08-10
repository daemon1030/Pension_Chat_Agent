from src.preprocessing.cleaner import clean_text
from src.preprocessing.schemas import PageText


def test_raw_text_is_not_modified_by_cleaning() -> None:
    raw_text = "  가입   조건\n\n\n\n  표  항목\t금액  "

    page = PageText(page=1, raw_text=raw_text, cleaned_text=clean_text(raw_text))

    assert page.raw_text == "  가입   조건\n\n\n\n  표  항목\t금액  "
    assert page.cleaned_text != page.raw_text


def test_consecutive_internal_spaces_are_safely_normalized() -> None:
    assert clean_text("가입   조건\n  들여쓰기   유지") == (
        "가입 조건\n  들여쓰기 유지"
    )


def test_excessive_blank_lines_are_collapsed_without_removing_paragraph_break() -> None:
    assert clean_text("첫 문단\n\n\n\n둘째 문단") == "첫 문단\n\n둘째 문단"
