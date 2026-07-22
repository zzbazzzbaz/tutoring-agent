"""会话管理模块：session 实体增删查改 + 权限 + 上下文构造。

router: POST/GET /sessions, GET/DELETE /sessions/{id}
service: load / readable / writable / touch / build_agent_context / to_out_dict
schemas: SessionCreate, SessionOut
"""
