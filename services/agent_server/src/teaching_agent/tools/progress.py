# 会话学习进度工具：report_stage_progress
import logging
from typing import Literal

import httpx
from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from teaching_agent.config import get_settings

logger = logging.getLogger(__name__)


class ReportStageProgressArgs(BaseModel):
    """汇报学习主线阶段进度。"""

    stage_id: str = Field(description="学习主线中的阶段 id，如 stg_01")
    status: Literal["in_progress", "completed"] = Field(
        description="in_progress=学生开始学习该阶段；completed=学生已掌握该阶段"
    )
    deliverable: str | None = Field(
        default=None,
        description="该阶段的产出物内容。completed 且配置了产出物时必须提交学生产出的文本",
    )


def create_report_stage_progress_tool() -> BaseTool:
    """创建会话级学习主线进度工具（进度绑定当前会话，不跨会话累积）。"""

    @tool(
        "report_stage_progress",
        args_schema=ReportStageProgressArgs,
        description=(
            "汇报学生在项目学习主线中的阶段进度，并同步到服务器。"
            "调用时机：会话开始时若没有进行中的阶段，先把第一个未完成阶段标记为 in_progress；"
            "某阶段标记 completed 后立即把下一个阶段标记为 in_progress；"
            "学生真正掌握当前阶段核心内容（含产出物达标）后标记 completed。"
            "只在状态发生变化时调用一次，不要在每轮对话中重复标记同一状态。"
            "stage_id 必须来自学习主线中已列出的阶段 id。"
        ),
    )
    async def report_stage_progress(
        *,
        runtime: ToolRuntime,
        stage_id: str,
        status: Literal["in_progress", "completed"],
        deliverable: str | None = None,
    ) -> Command:
        session_id = runtime.execution_info.thread_id if runtime.execution_info else None
        if not session_id:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content="无法获取会话 ID，学习进度未更新。",
                            tool_call_id=runtime.tool_call_id or "",
                        )
                    ]
                }
            )

        settings = get_settings()
        headers = {"X-Agent-Server-Secret": settings.agent_server_secret.get_secret_value()}
        base_url = settings.backend_internal_url.rstrip("/")
        progress_url = f"{base_url}/progress/sessions/{session_id}"

        # 1. 拉取当前会话进度，合并本次更新
        current: dict = {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(progress_url, headers=headers)
                if resp.status_code == 200:
                    current = (resp.json() or {}).get("progress") or {}
        except Exception:
            logger.exception("fetch session progress failed")

        deliverable_done = status == "completed" and bool(deliverable)
        current[stage_id] = {
            "status": status,
            "deliverable": deliverable,
            "deliverable_done": deliverable_done,
        }

        # 2. 落库（失败不影响对话，只记日志）
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{base_url}/progress/internal/agent",
                    headers=headers,
                    json={
                        "session_id": session_id,
                        "progress": {stage_id: current[stage_id]},
                    },
                )
        except Exception:
            logger.exception("persist session progress failed")

        # 3. 返回状态更新（流式推送给前端实时刷新）
        return Command(
            update={
                "progress": {stage_id: current[stage_id]},
                "messages": [
                    ToolMessage(
                        content=(
                            f"学习主线进度已更新：阶段「{stage_id}」→ "
                            f"{'已完成' if status == 'completed' else '进行中'}"
                            + (f"，产出物已达标" if deliverable_done else "")
                        ),
                        tool_call_id=runtime.tool_call_id or "",
                    )
                ],
            }
        )

    return report_stage_progress
