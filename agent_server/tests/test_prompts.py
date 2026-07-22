from teaching_agent.prompts import render_system_prompt
from teaching_agent.schemas import AgentContextV1


def test_free_prompt_uses_authorized_course_context():
    prompt = render_system_prompt(AgentContextV1(mode="free", course_name="计算机网络"))

    assert "《计算机网络》" in prompt
    assert "自由学习" in prompt
    assert "当前项目" not in prompt


def test_project_prompt_uses_authorized_project_context():
    prompt = render_system_prompt(
        AgentContextV1(
            mode="project",
            course_name="计算机网络",
            project_name="园区网络设计",
            project_background_md="为教学楼规划可靠网络。",
        )
    )

    assert "园区网络设计" in prompt
    assert "为教学楼规划可靠网络。" in prompt
    assert "项目背景" in prompt
