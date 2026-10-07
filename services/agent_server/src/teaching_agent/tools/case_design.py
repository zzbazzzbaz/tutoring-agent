# 案例设计工具：save_case_draft（把教师确认后的结构化案例保存为草稿）
import json
import logging

import httpx
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field, model_validator

from teaching_agent.config import get_settings

logger = logging.getLogger(__name__)


class CaseDraftStage(BaseModel):
    """案例学习主线的一个阶段。"""

    title: str = Field(min_length=1, max_length=100, description="阶段名称，如「情绪与分离焦虑」")
    guide: str = Field(default="", description="给教学 agent 的引导提示（学生不可见），可空")
    student_desc: str = Field(default="", description="学生可见的阶段说明，可空")
    deliverable_title: str = Field(default="", description="该阶段产出物名称；无需产出物则留空")
    deliverable_instructions: str = Field(
        default="", description="产出物要求；产出物名称不为空时必须填写"
    )

    @model_validator(mode="after")
    def check_deliverable(self):
        if self.deliverable_title and not self.deliverable_instructions:
            raise ValueError("产出物名称与产出物要求必须同时提供")
        return self


class SaveCaseDraftArgs(BaseModel):
    project_id: str = Field(
        default="", description="已生成草稿的 id；修改同一草稿时传入，首次创建留空"
    )
    name: str = Field(min_length=1, max_length=200, description="案例名称，需与现有案例不重名")
    background_md: str = Field(min_length=1, description="案例背景 Markdown")
    objective: str = Field(min_length=1, description="总体学习目标（一句话）")
    stages: list[CaseDraftStage] = Field(
        min_length=1, max_length=8, description="学习主线阶段，按教学顺序 3~6 个"
    )


def _stage_payload(stages) -> list[dict]:
    result = []
    for stage in stages or []:
        if isinstance(stage, dict):
            result.append(stage)
        else:
            result.append(stage.model_dump())
    return result


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json()["detail"]["error"]["message"])
    except Exception:
        return f"保存失败（HTTP {response.status_code}）"


def create_save_case_draft_tool() -> BaseTool:
    """创建案例设计工具（仅 case_design 模式挂载）。"""

    @tool(
        "save_case_draft",
        args_schema=SaveCaseDraftArgs,
        description=(
            "把教师确认后的结构化案例保存为草稿（status=draft），返回案例 id 与编辑页地址。"
            "调用时机：教师明确确认案例内容后才可调用；教师只是补充信息或提出修改意见时禁止调用。"
            "同一对话中第二次及以后保存，必须传入首次返回的 project_id，"
            "更新同一草稿，不得重复创建。"
            "若返回名称冲突，请与教师协商修改名称后重试。"
        ),
    )
    async def save_case_draft(
        project_id: str = "",
        name: str = "",
        background_md: str = "",
        objective: str = "",
        stages: list[dict] | None = None,
    ) -> str:
        settings = get_settings()
        payload = {
            "project_id": project_id or None,
            "name": name,
            "background_md": background_md,
            "objective": objective,
            "stages": _stage_payload(stages),
        }
        headers = {"X-Agent-Server-Secret": settings.agent_server_secret.get_secret_value()}
        url = f"{settings.backend_internal_url.rstrip('/')}/projects/internal/agent"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(url, headers=headers, json=payload)
        except Exception:
            logger.exception("save_case_draft request failed")
            return json.dumps(
                {"ok": False, "error": "保存服务暂时不可用，请稍后重试"}, ensure_ascii=False
            )
        if response.status_code >= 400:
            return json.dumps(
                {"ok": False, "error": _error_message(response)}, ensure_ascii=False
            )
        data = response.json()
        return json.dumps(
            {
                "ok": True,
                "project_id": data["project_id"],
                "project_name": data["project_name"],
                "stage_count": data["stage_count"],
                "created": data["created"],
                "url": f"/teacher/manage/projects/{data['project_id']}/edit",
            },
            ensure_ascii=False,
        )

    return save_case_draft
