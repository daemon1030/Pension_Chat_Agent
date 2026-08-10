"""Validated output models for first-pass PDF extraction."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractionStatus(StrEnum):
    """Text-layer availability for a parsed PDF."""

    SUCCESS = "SUCCESS"
    PARTIAL_TEXT = "PARTIAL_TEXT"
    NO_TEXT_LAYER = "NO_TEXT_LAYER"


class PDFMetadata(BaseModel):
    """Metadata exposed by the source PDF without inferred values."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    creator: str | None = None
    producer: str | None = None
    creation_date: str | None = None
    modification_date: str | None = None
    pdf_format: str | None = None


class PageText(BaseModel):
    """Extracted text tied to a one-based source page number."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    raw_text: str
    cleaned_text: str


class RepeatedTextCandidate(BaseModel):
    """A repeated boundary line retained for later review, not removed."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    pages: list[int]
    occurrence_count: int = Field(ge=2)

    @model_validator(mode="after")
    def validate_occurrences(self) -> "RepeatedTextCandidate":
        if self.pages != sorted(set(self.pages)):
            raise ValueError("candidate pages must be unique and sorted")
        if self.occurrence_count != len(self.pages):
            raise ValueError("occurrence_count must equal the number of pages")
        return self


class ProcessedDocument(BaseModel):
    """Validated, traceable output for one source PDF."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(pattern=r"^DOC_[0-9A-F]{12}$")
    filename: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    file_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_size_bytes: int = Field(ge=0)
    page_count: int = Field(ge=0)
    extraction_status: ExtractionStatus
    pages_without_text: list[int] = Field(default_factory=list)
    duplicate_of_document_id: str | None = Field(
        default=None,
        pattern=r"^DOC_[0-9A-F]{12}$",
    )
    metadata: PDFMetadata
    repeated_header_candidates: list[RepeatedTextCandidate] = Field(
        default_factory=list
    )
    repeated_footer_candidates: list[RepeatedTextCandidate] = Field(
        default_factory=list
    )
    pages: list[PageText]

    @model_validator(mode="after")
    def validate_page_consistency(self) -> "ProcessedDocument":
        expected_pages = list(range(1, self.page_count + 1))
        actual_pages = [page.page for page in self.pages]
        if actual_pages != expected_pages:
            raise ValueError("pages must be complete, ordered, and one-based")

        if self.pages_without_text != sorted(set(self.pages_without_text)):
            raise ValueError("pages_without_text must be unique and sorted")
        if not set(self.pages_without_text).issubset(expected_pages):
            raise ValueError("pages_without_text contains an invalid page number")

        empty_page_count = len(self.pages_without_text)
        if self.page_count > 0 and empty_page_count == self.page_count:
            expected_status = ExtractionStatus.NO_TEXT_LAYER
        elif empty_page_count > 0:
            expected_status = ExtractionStatus.PARTIAL_TEXT
        else:
            expected_status = ExtractionStatus.SUCCESS
        if self.extraction_status != expected_status:
            raise ValueError("extraction_status does not match extracted page text")
        return self
