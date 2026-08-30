from typing import Literal
from uuid import uuid4

from langchain_core.tools import tool
from langgraph.types import interrupt

from teaching_agent.tools.schemas import PresentQuestionArgs, QuizResume


@tool(
    description=(
        "向学生展示一道题目并等待作答。出题时必须同时给出正确答案 "
        "(correct_answer):选择题传正确选项的完整文本,多选用 ', ' 连接;"
        "简答题传参考答案要点。拿到答案后基于正确答案评估并反馈。"
    ),
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
