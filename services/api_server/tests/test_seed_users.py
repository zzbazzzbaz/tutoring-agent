import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from seed_users import SEED_PROJECTS


def test_seed_projects_include_published_computer_network_scenarios():
    assert [project["name"] for project in SEED_PROJECTS] == [
        "校园网络规划与设计",
        "家庭网络故障诊断与优化",
        "小型企业网络架构搭建",
    ]
    assert all(project["status"] == "published" for project in SEED_PROJECTS)
    assert all(
        project["background_md"].startswith(f"# {project['name']}") for project in SEED_PROJECTS
    )
