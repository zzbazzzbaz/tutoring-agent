"""项目学习 Agent。"""
from langchain.agents import create_agent
from sqlmodel import select

from teaching_agent.agents.llm import get_llm
from teaching_agent.agents.prompts import GUIDANCE_PROMPT
from teaching_agent.agents.tools import (
    make_search_tool, make_quiz_tool, make_end_session_tool,
)
from teaching_agent.config import settings
from teaching_agent.db import async_session_factory
from teaching_agent.models import StudentProfile, Project


async def create_project_agent(project: Project, checkpointer, session_id: str):
    """创建项目学习 Agent。

    Args:
        project: 项目实体（含 name 和 background_md）
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
        f"学生正在学习项目：{project.name}。\n"
        f"项目背景：{project.background_md}\n"
        f"以项目背景为情境展开追问。"
    )

    system_prompt = GUIDANCE_PROMPT.format(
        course_name=settings.COURSE_NAME,
        student_profile=profile_text,
        session_context=session_context_str,
    )

    session_context = {"project_id": project.id}
    tools = [
        make_search_tool("project", session_context),
        make_quiz_tool("project", session_context, session_id),
        make_end_session_tool("project", session_context, session_id),
    ]

    return create_agent(
        model=get_llm(),
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        name="project_agent",
    )
