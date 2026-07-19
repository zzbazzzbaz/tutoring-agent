"""LightRAG API 响应的 Pydantic 模型。

用于类型注解；代理端点透传原始 JSON 以保持与 lightrag_webui 100%
兼容。
"""
from typing import Any

from pydantic import BaseModel, Field


class InsertResponse(BaseModel):
    """/documents/text 与 /documents/texts 的响应。"""

    status: str
    message: str | None = None
    track_id: str | None = None


class DocStatusResponse(BaseModel):
    """来自 LightRAG 的单条文档状态行。"""

    id: str
    content_summary: str | None = None
    content_length: int | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    track_id: str | None = None
    chunks_count: int | None = None
    error_msg: str | None = None
    metadata: dict[str, Any] | None = None
    file_path: str | None = None


class TrackStatusResponse(BaseModel):
    """/documents/track_status/{track_id} 的响应。"""

    track_id: str
    documents: list[DocStatusResponse] = Field(default_factory=list)
    total_count: int = 0
    status_summary: dict[str, int] = Field(default_factory=dict)


class PipelineStatusResponse(BaseModel):
    """/documents/pipeline_status 的响应。"""

    busy: bool
    job_name: str | None = None
    latest_message: str | None = None
    docs: int = 0
    batches: int = 0
    cur_batch: int = 0


class QueryResponse(BaseModel):
    """/query 的响应。references 列表的结构由服务端控制。"""

    response: str
    references: list[dict[str, Any]] | None = None
