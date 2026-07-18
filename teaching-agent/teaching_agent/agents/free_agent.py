"""自由学习 Agent。"""
from langchain.agents import create_agent
from sqlmodel import select

from teaching_agent.agents.llm import get_llm
from teaching_agent.agents.prompts import GUIDANCE_PROMPT
from teaching_agent.agents.tools import (
    make_search_tool, make_quiz_tool, make_end_session_tool,
)
from teaching_agent.config import settings
from teaching_agent.db import async_session_factory
from teaching_agent.models import StudentProfile


async def create_free_agent(checkpointer, session_id: str):
    """创建自由学习 Agent。

    Args:
        checkpointer: AsyncPostgresSaver 实例
        session_id: 会话 ID（用于工具内数据库操作）

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

    system_prompt = GUIDANCE_PROMPT.format(
        course_name=settings.COURSE_NAME,
        student_profile=profile_text,
        session_context="学生正在进行自由学习，围绕课程知识自由探索。",
    )

    tools = [
        make_search_tool("free", {}),
        make_quiz_tool("free", {}, session_id),
        make_end_session_tool("free", {}, session_id),
    ]

    return create_agent(
        model=get_llm(),
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        name="free_agent",
    )
