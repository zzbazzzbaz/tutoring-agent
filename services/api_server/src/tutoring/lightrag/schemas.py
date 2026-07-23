from typing import Literal

from pydantic import BaseModel, Field

DocumentStatus = Literal[
    "pending",
    "parsing",
    "analyzing",
    "processing",
    "preprocessed",
    "processed",
    "failed",
]


class DocumentsRequest(BaseModel):
    status_filter: DocumentStatus | None = None
    status_filters: list[DocumentStatus] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_field: str = "updated_at"
    sort_direction: Literal["asc", "desc"] = "desc"


class DeleteDocumentRequest(BaseModel):
    doc_ids: list[str] = Field(min_length=1)
    delete_file: bool = True
    delete_llm_cache: bool = False
