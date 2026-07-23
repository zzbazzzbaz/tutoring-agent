from langgraph_sdk.runtime import ServerRuntime

from teaching_agent.auth.schemas import AgentContextV1

_INTROSPECTION_CONTEXT = AgentContextV1(mode="free")


def get_trusted_agent_context(runtime: ServerRuntime) -> AgentContextV1:
    user = runtime.ensure_user()
    raw_context = getattr(user, "agent_context", None)
    if raw_context is None:
        return _INTROSPECTION_CONTEXT
    if hasattr(raw_context, "dict"):
        raw_context = raw_context.dict()
    return AgentContextV1.model_validate(raw_context)
