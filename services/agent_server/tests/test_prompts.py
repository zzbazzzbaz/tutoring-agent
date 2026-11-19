from teaching_agent.agent.prompts import render_system_prompt
from teaching_agent.auth.schemas import AgentContextV1


def test_free_prompt_uses_server_course_configuration():
    prompt = render_system_prompt(AgentContextV1(mode="free"))

    assert "《普通心理学》" in prompt
    assert "自由学习" in prompt
    assert "当前项目" not in prompt


def test_project_prompt_uses_authorized_project_context():
    prompt = render_system_prompt(
        AgentContextV1(
            mode="project",
            project_name="园区网络设计",
            project_background_md="为教学楼规划可靠网络。",
        )
    )

    assert "园区网络设计" in prompt
    assert "为教学楼规划可靠网络。" in prompt
    assert "项目背景" in prompt


def test_project_prompt_requires_case_background_in_first_turn():
    prompt = render_system_prompt(
        AgentContextV1(
            mode="project",
            project_name="园区网络设计",
            project_background_md="为教学楼规划可靠网络。",
        )
    )

    assert "开场：交代案例背景" in prompt
    assert "首轮对话" in prompt
    assert "介绍案例背景" in prompt


def test_project_prompt_lists_report_stage_progress_tool():
    prompt = render_system_prompt(
        AgentContextV1(
            mode="project",
            project_name="园区网络设计",
            project_mainline="1. 需求分析",
        )
    )

    assert "report_stage_progress" in prompt
    assert "进度管理" in prompt


def test_free_prompt_does_not_list_project_tool():
    prompt = render_system_prompt(AgentContextV1(mode="free"))

    assert "report_stage_progress" not in prompt
    assert "进度管理" not in prompt


def test_case_design_prompt_contains_rules_and_tool():
    prompt = render_system_prompt(AgentContextV1(mode="case_design"))

    assert "案例设计助手" in prompt
    assert "save_case_draft" in prompt
    assert "确认" in prompt
    assert "report_stage_progress" not in prompt

