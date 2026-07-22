from types import SimpleNamespace

from teaching_agent.graph import _INTROSPECTION_CONTEXT, _trusted_context


def test_trusted_context_uses_backend_authorized_user_context():
    runtime = SimpleNamespace(
        ensure_user=lambda: SimpleNamespace(
            agent_context={"version": 1, "mode": "free"}
        )
    )

    context = _trusted_context(runtime)

    assert context.mode == "free"


def test_trusted_context_uses_safe_introspection_default_without_session():
    runtime = SimpleNamespace(ensure_user=lambda: SimpleNamespace())

    assert _trusted_context(runtime) == _INTROSPECTION_CONTEXT
