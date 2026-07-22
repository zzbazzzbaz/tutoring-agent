from pydantic import BaseModel


class HistoryItemOut(BaseModel):
    type: str
    content: str | None = None
    tool_name: str | None = None
    tool_input: dict | None = None
    quiz_id: str | None = None
    topic: str | None = None
    q_type: str | None = None
    stem: str | None = None
    options: list[str] | None = None
    status: str | None = None
    user_answer: str | None = None


class HistoryOut(BaseModel):
    items: list[HistoryItemOut]
    pending_quiz: dict | None = None
    processing: bool = False
