from teaching_agent.auth.schemas import AgentContextV1
from teaching_agent.config import get_settings


def render_system_prompt(context: AgentContextV1) -> str:
    settings = get_settings()
    core_principles = settings.prompt_core_principles
    free_template = settings.prompt_free_template
    project_template = settings.prompt_project_template

    if context.mode == "project":
        return project_template.format(
            core_principles=core_principles,
            course_name=settings.course_name,
            project_name=context.project_name,
            project_background_md=context.project_background_md,
            project_mainline=context.project_mainline,
        )
    return free_template.format(
        core_principles=core_principles,
        course_name=settings.course_name,
    )