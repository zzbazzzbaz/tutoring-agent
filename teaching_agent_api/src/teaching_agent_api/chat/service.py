"""会话领域服务：404/403/409 校验全项目唯一一份。"""
import uuid

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent_api.agent.prompts import AgentContext
from teaching_agent_api.core.config import settings
from teaching_agent_api.core.errors import AppError
from teaching_agent_api.db import repos
from teaching_agent_api.db.models import Project, Session


async def get_owned_session(db: AsyncSession, session_id: uuid.UUID, user_id: str) -> Session:
    """存在且归属该用户，否则抛 404/403。"""
    sess = await repos.get_session(db, session_id)
    if not sess:
        raise AppError(404, "SESSION_NOT_FOUND", f"Session {session_id} not found")
    if sess.user_id != user_id:
        raise AppError(403, "FORBIDDEN", "Session does not belong to user")
    return sess


async def get_active_session(db: AsyncSession, session_id: uuid.UUID, user_id: str) -> Session:
    """get_owned_session + 状态 active（chat 流式端点用）。"""
    sess = await get_owned_session(db, session_id, user_id)
    if sess.status != "active":
        raise AppError(409, "SESSION_ENDED", "Session is ended")
    return sess


async def build_agent_context(db: AsyncSession, sess: Session) -> AgentContext:
    """根据 session 模式构建 AgentContext；project 模式查项目信息。"""
    if sess.mode == "project" and sess.project_id:
        proj = await repos.get_project(db, sess.project_id)
        return AgentContext(
            mode="project",
            course_name=settings.course_name,
            project_name=proj.name if proj else "",
            project_background_md=proj.background_md if proj else "",
        )
    return AgentContext(mode="free", course_name=settings.course_name)


async def is_interrupted(agent: CompiledStateGraph, session_id: uuid.UUID) -> bool:
    """检查 LangGraph state 是否处于 interrupt 待恢复状态。"""
    config = {"configurable": {"thread_id": str(session_id)}}
    state = await agent.aget_state(config)
    return bool(state.next)


def session_to_out_dict(sess: Session, project: Project | None = None) -> dict:
    """从 Session ORM 实例构建 SessionOut dict，在可用时添加 `project_name`。

    有两条路径会填充 `project_name`：
      1. 显式传入 `project` 参数（由 create_session 使用，因为它刚刚
         为校验而 fetch 了 project）。
      2. 通过 eager loading（selectinload）在 get_session / list_sessions
         中访问 `sess.project`。

    此处避免 `sess.model_dump()`，因为它会递归遍历 `project.sessions`
    及其它关系属性，开销较大且可能让调用方意外。手动字段选择显式且安全。
    """
    data = {
        "id": sess.id,
        "user_id": sess.user_id,
        "mode": sess.mode,
        "project_id": sess.project_id,
        "title": sess.title,
        "status": sess.status,
        "last_active_at": sess.last_active_at,
        "created_at": sess.created_at,
    }
    proj = project
    if proj is None:
        # `sess.project` 仅在查询使用 selectinload 时才加载；
        # 在未 eager loading 的情况下访问会触发 greenlet 错误
        # （在 async 上下文中），此处防御性吞掉。
        try:
            proj = sess.project
        except Exception:
            proj = None
    if proj is not None:
        data["project_name"] = proj.name
    return data
