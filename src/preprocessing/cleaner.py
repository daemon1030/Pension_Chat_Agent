"""Conservative text cleanup that preserves source line structure."""

import re
import unicodedata


_INTERNAL_SPACES = re.compile(r"(?<=\S) {2,}(?=\S)")
_EXCESS_BLANK_LINES = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")


def _remove_control_characters(text: str) -> str:
    """Remove control characters except tabs and line endings."""

    return "".join(
        character
        for character in text
        if character in {"\n", "\r", "\t"}
        or unicodedata.category(character) != "Cc"
    )


def clean_text(raw_text: str) -> str:
    """Apply only safe, non-semantic cleanup to extracted text.

    Newlines and tabs are preserved. Leading indentation is retained except at
    the very beginning/end of the whole page, and no content is summarized,
    merged, or rewritten.
    """

    cleaned = _remove_control_characters(raw_text)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _INTERNAL_SPACES.sub(" ", cleaned)
    cleaned = _EXCESS_BLANK_LINES.sub("\n\n", cleaned)
    return cleaned.strip()
