from typing import Literal
from uuid import uuid4

from langchain_core.tools import tool
from langgraph.types import interrupt

from teaching_agent.tools.schemas import PresentQuestionArgs, QuizResume


@tool(
    description="向学生展示一道题目并等待作答，拿到答案后自行评估并反馈。",
    args_schema=PresentQuestionArgs,
)
async def present_question(
    topic: str,
    q_type: Literal["single", "multi", "short"],
    stem: str,
    options: list[str] | None,
    correct_answer: str,
) -> dict:
    question_id = str(uuid4())
    student_answer = interrupt(
        {
            "question_id": question_id,
            "topic": topic,
            "q_type": q_type,
            "stem": stem,
            "options": options,
        }
    )
    resume = QuizResume.model_validate(student_answer)
    if resume.action == "skip":
        return {"question_id": question_id, "action": "skipped"}
    return {"question_id": question_id, "student_answer": resume.answer}
