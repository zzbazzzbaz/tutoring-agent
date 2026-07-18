"""错题重练 Agent。"""
from langchain.agents import create_agent
from sqlmodel import select

from teaching_agent.agents.llm import get_llm
from teaching_agent.agents.prompts import GUIDANCE_PROMPT
from teaching_agent.agents.tools import (
    make_search_tool, make_quiz_tool, make_end_session_tool,
)
from teaching_agent.config import settings
from teaching_agent.db import async_session_factory
from teaching_agent.models import StudentProfile, MistakeItem


async def create_review_agent(mistake: MistakeItem, checkpointer, session_id: str):
    """创建错题重练 Agent。

    Args:
        mistake: 错题实体（含 title, wrong_answer, correct_answer, diagnosis, kp_id）
        checkpointer: AsyncPostgresSaver 实例
        session_id: 会话 ID

    Returns:
        create_agent 编译后的 Agent
    """
    # 获取学生画像
    async with async_session_factory() as db:
        result = await db.execute(
            select(StudentProfile).where(StudentProfile.user_id == "demo-student")
        )
        profile = result.scalar_one_or_none()
        if profile:
            weak = [wp.get("kp_name", "") for wp in profile.weak_points]
            profile_text = (
                f"摘要: {profile.summary}\n"
                f"薄弱点: {', '.join(weak) if weak else '无'}\n"
                f"学习风格: {profile.learning_style}"
            )
        else:
            profile_text = "新学生，暂无画像"

    session_context_str = (
        f"学生正在重练错题。\n"
        f"知识点：{mistake.title}\n"
        f"原题：{mistake.title}\n"
        f"错误答案：{mistake.wrong_answer}\n"
        f"错因：{mistake.diagnosis}\n"
        f"围绕这个知识点追问，出变式题（同知识点不同考法）。"
    )

    system_prompt = GUIDANCE_PROMPT.format(
        course_name=settings.COURSE_NAME,
        student_profile=profile_text,
        session_context=session_context_str,
    )

    # mistake_data 传 dict 避免序列化问题
    mistake_data = {
        "id": mistake.id,
        "title": mistake.title,
        "wrong_answer": mistake.wrong_answer,
        "correct_answer": mistake.correct_answer,
        "diagnosis": mistake.diagnosis,
        "source_chunk_ids": mistake.source_chunk_ids or [],
        "kp_id": mistake.kp_id,
    }
    session_context = {
        "mistake_data": mistake_data,
        "mistake_id": mistake.id,
    }
    tools = [
        make_search_tool("review", session_context),
        make_quiz_tool("review", session_context, session_id),
        make_end_session_tool("review", session_context, session_id),
    ]

    return create_agent(
        model=get_llm(),
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        name="review_agent",
    )
