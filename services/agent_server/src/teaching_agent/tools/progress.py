# 学习主线进度工具：report_stage_progress
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


def create_report_stage_progress_tool(*, user_id: str, project_id: str) -> BaseTool:
    """创建学习主线进度工具（按 agent 上下文绑定学生与项目）。"""

    @tool(
        "report_stage_progress",
        args_schema=ReportStageProgressArgs,
        description=(
            "汇报学生在项目学习主线中的阶段进度，并同步到服务器。"
            "当学生开始学习某阶段时标记 in_progress；"
            "确认学生真正掌握该阶段核心内容、且产出物（若有）达标后标记 completed。"
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
        settings = get_settings()
        headers = {"X-Agent-Server-Secret": settings.agent_server_secret.get_secret_value()}
        base_url = settings.backend_internal_url.rstrip("/")
        progress_url = f"{base_url}/progress/projects/{project_id}/users/{user_id}"

        # 1. 拉取当前进度（跨会话累积），合并本次更新
        current: dict = {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(progress_url, headers=headers)
                if resp.status_code == 200:
                    current = (resp.json() or {}).get("progress") or {}
        except Exception:
            logger.exception("fetch project progress failed")

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
                        "user_id": user_id,
                        "project_id": project_id,
                        "progress": {stage_id: current[stage_id]},
                    },
                )
        except Exception:
            logger.exception("persist project progress failed")

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
