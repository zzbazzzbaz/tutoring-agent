from types import SimpleNamespace

from teaching_agent.auth.context import _INTROSPECTION_CONTEXT, get_trusted_agent_context


def test_trusted_context_uses_api_server_authorized_user_context():
    runtime = SimpleNamespace(
        ensure_user=lambda: SimpleNamespace(agent_context={"version": 1, "mode": "free"})
    )

    context = get_trusted_agent_context(runtime)

    assert context.mode == "free"


def test_trusted_context_uses_safe_introspection_default_without_session():
    runtime = SimpleNamespace(ensure_user=lambda: SimpleNamespace())

    assert get_trusted_agent_context(runtime) == _INTROSPECTION_CONTEXT
