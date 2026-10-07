from functools import lru_cache
from pathlib import Path

from teaching_agent.auth.schemas import AgentContextV1

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=None)
def _load(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def render_system_prompt(context: AgentContextV1) -> str:
    if context.mode == "case_design":
        return _load("case_design_template.md").format(tools=_load("tools_case_design.md"))
    core_principles = _load("core_principles.md")
    tools = _load("tools_project.md" if context.mode == "project" else "tools_free.md")

    if context.mode == "project":
        return _load("project_template.md").format(
            core_principles=core_principles,
            tools=tools,
            project_name=context.project_name,
            project_background_md=context.project_background_md,
            project_mainline=context.project_mainline,
        )
    return _load("free_template.md").format(
        core_principles=core_principles,
        tools=tools,
    )
