from teaching_agent.config import Settings


def test_settings_loads_the_local_env_file():
    assert Settings.model_config["env_file"] == ".env"
