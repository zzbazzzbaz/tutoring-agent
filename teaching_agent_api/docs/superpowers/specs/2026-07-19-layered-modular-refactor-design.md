# 分层模块化重构设计（特性模块 + 共享数据层）

日期：2026-07-19
状态：已确认（用户逐节批准）
类型：纯内部重构 —— 对外 API 契约零变更

## 1. 背景与目标

当前后端按技术分层（`api/` `db/` `schemas/`）组织，同一领域（会话）的逻辑散落在多个包中，导致：

| 问题 | 证据（重构前） |
|------|------|
| 校验逻辑重复 | `api/chat.py::_validate_session_for_chat` 与 `api/sessions.py::_validate_session_ownership` 近乎相同的 404/403 代码 |
| 错误响应构造散落 | `{"error": {"code", "message"}}` 在路由中手写 15+ 次 |
| 路由承载业务规则 | "project 必须 published 才能开会话"在 `api/sessions.py`；`api/chat.py` 路由做 AgentContext 组装、interrupt 检查、消息落库编排 |
| 代理端点复制粘贴 | `api/documents.py` + `api/graph.py` 共 13 处相同的 `try/except → 502` |
| 隐藏全局耦合 | `agent/tools.py` 模块级 `_state` 字典做依赖注入 |
| 命名遮蔽 | `from teaching_agent_api import db` 包名与 `db` session 变量互相遮蔽 |

**目标**：高内聚（领域逻辑聚进模块）、低耦合（依赖方向单向），并为后续迭代铺路：

- 教师端/学生端是**同一领域、不同视角**（围绕同一批领域对象：project/session/question/知识库）
- **近期会做真正的认证**（JWT + role 字段），架构需预留 auth 位置
- 推进方式：**一次性迁移到位**，暂停新功能 1-2 天

## 2. 方案选型

| 方案 | 结论 |
|------|------|
| **A. 特性模块 + 共享数据层** | ✅ 采纳。按领域拆模块（projects/chat/knowledge/agent），models+repos 集中。4 张表被 agent 与 chat 双向使用，拆开会引入循环依赖 |
| B. 完整模块化（每模块拥有自己的表和 repo） | 否决。agent⇄chat 双向依赖需 Protocol 端口注入解环，收益抵不过复杂度 |
| C. 完整 DDD 战术架构（四层 + 实体/ORM 分离 + Repository 接口 + UoW） | 否决。当前无复杂聚合与领域事件，YAGNI |

## 3. 目标目录结构

```
src/teaching_agent_api/
├── main.py                # 只做组装：lifespan 建单例 + include_router + 注册异常处理
│
├── core/                  # 共享内核（被所有模块依赖，自身不依赖任何业务模块）
│   ├── config.py          # Settings（原 config.py 平移）
│   ├── errors.py          # AppError 异常 + register_exception_handlers()
│   ├── database.py        # engine / session factory / init_db（原 db/engine.py）
│   └── deps.py            # get_db, get_current_user, get_agent, get_lightrag
│
├── db/                    # 共享数据层：唯一数据真相，无业务规则
│   ├── models.py          # project/session/message/question 四张表
│   └── repos.py           # 纯数据访问函数（参数名 db → session，消除遮蔽）
│
├── projects/              # 课程项目域（未来教师端管理的主战场）
│   ├── router.py          # /projects REST
│   ├── service.py         # 重名冲突、published 校验等业务规则
│   └── schemas.py
│
├── chat/                  # 会话域（学生端核心）：sessions REST + chat SSE 一体
│   ├── router.py          # /sessions CRUD + messages/questions 查询
│   ├── sse.py             # /chat/sessions/{id}/messages、/quiz/resume 流式端点
│   ├── service.py         # 会话校验（全项目唯一一份）、AgentContext 组装、interrupt 检查
│   └── schemas.py
│
├── knowledge/             # LightRAG 代理域（原 lightrag/ + documents/graph 两路由合并）
│   ├── client.py          # LightRAGClient + 其 schemas
│   └── router.py          # /documents/* + /graph*，13 个端点全部瘦身为单行
│
├── agent/                 # AI 核心，零 FastAPI 依赖（可被 worker/CLI 复用）
│   ├── factory.py / llm.py / prompts.py
│   ├── runtime.py         # astream_events → SSE 帧
│   └── tools.py           # 删全局 _state，改显式注入（工具工厂）
│
└── auth/                  # 预留占位：当前为空模块（仅 __init__.py）
                           # 未来 JWT 校验、用户/角色模型放这里
```

命名说明：`chat/` 模块同时拥有 `/sessions` REST 和 `/chat` SSE 两组端点——它们共享同一个 Session 聚合和同一份校验逻辑，合并后重复代码自然消除。

## 4. 依赖规则（单向 DAG）

```
core      ← 所有模块
db        ← projects, chat, agent
knowledge ← agent, knowledge/router
agent     ← chat          # agent 不知道 chat 存在
```

- router/sse 层**只允许**调 service；service 调 `db.repos` / `agent.runtime` / `knowledge.client`
- 不引入 import-linter 等强制工具（项目已移除 ruff/pre-commit），依赖方向靠约定 + code review 守护
- 教师端上线落点：`projects/` 加教师管理接口、`chat/` 加学情查询接口、`auth/` 填实现——学生端路由不动

## 5. 核心机制

### 5.1 统一错误处理

```python
# core/errors.py
class AppError(Exception):
    def __init__(self, status: int, code: str, message: str): ...
```

- `main.py` 注册一次：`AppError → {"error": {"code", "message"}}`；`LightRAGError → 502`；未捕获异常 `→ 500 + 日志`
- 路由/service 只写 `raise AppError(404, "SESSION_NOT_FOUND", ...)`
- 删除所有手写 `HTTPException(detail={...})`，**对外错误格式保持不变**

### 5.2 service 层边界

- `chat/service.py`：唯一的 `get_active_session(session_id, user_id)`（404/403/409 三态校验）；`build_agent_context()`；`is_interrupted()`；消息落库与 `touch_session`
- `projects/service.py`：重名冲突转 409、published 校验（"project 必须已发布"是项目域规则，从 sessions 路由收回）
- `knowledge/` 无 service 层（纯透传，YAGNI）

### 5.3 代理端点瘦身

`LightRAGClient` 内部抛 `LightRAGError`，由全局 handler 转 502。13 个端点全部变单行：

```python
@router.post("/scan")
async def scan(lightrag: LightRAGClient = Depends(get_lightrag_client)) -> dict:
    return await lightrag.scan()
```

### 5.4 agent/tools.py 去全局状态

- 删除模块级 `_state` 字典与 `set_dependencies()`
- 改为工具工厂：`make_tools(lightrag, db_session_factory) -> list[BaseTool]`，闭包捕获依赖
- `build_agent()` 接收工具列表；测试可独立构造工具，无需碰全局态

### 5.5 auth 占位

- `CurrentUser(id=str, role="student")` 简单对象与 `get_current_user`（读 X-User-Id 构造）都定义在 `core/deps.py`——core 不依赖业务模块，因此 CurrentUser 不能放 `auth/`
- 所有路由把 `Depends(get_user_id)` 换成 `Depends(get_current_user)`
- 未来接 JWT 时：`auth/` 提供令牌校验器，`core/deps.py` 的 `get_current_user` 改为委托调用；路由签名不变

### 5.6 明确不动的部分

- LangGraph 双轨状态设计（checkpoint 表 + 业务表）维持现状
- SSE 事件格式（`text/quiz_interrupt/done/error`）不变
- 所有 URL 路径、请求/响应 schema 不变 —— **纯内部重构，前端零感知**
- `quiz_flow` 幂等出题逻辑、prompt 内容不动
- `pyproject.toml` 依赖不动、不碰前端

## 6. 迁移步骤（每步可独立提交，全程测试保持绿）

1. **core/ 落地**：`config.py`、`engine.py → core/database.py` 平移；新增 `errors.py`；`deps.py` 移入并加 `get_current_user`
2. **db/ 平移**：models/repos 不动逻辑，仅 repos 参数 `db → session` 改名
3. **knowledge/ 合并**：`lightrag/client.py` 移入；documents + graph 两路由合并为一个，13 处 try/except 删除（错误格式不变）
4. **agent/ 重构**：tools.py 改工具工厂 + `build_agent` 签名调整；runtime/prompts/llm/factory 平移
5. **领域模块落地**：`projects/`、`chat/` 建 service，路由改薄；统一校验合并进 `chat/service.py`
6. **main.py 重组装**：注册异常 handler、路由全量挂载、`auth/` 占位
7. **收尾**：测试 import 更新、README Layout 与 AGENTS.md 重写

## 7. 测试策略与验收

- **契约不变是硬约束**：现有 6 个测试文件（`test_projects` `test_sessions` `test_documents_proxy` `test_health` `test_chat_streaming`）应原样通过，只许改 import 路径，不许改断言
- **新增 `test_errors.py`**：验证统一错误格式（404/403/409/502 的 `{"error": {...}}` 结构）
- **新增 tools 工厂测试**：验证 `make_tools()` 注入后工具可用，替代原全局态的隐式依赖
- **验收标准**：`uv run pytest` 全绿（项目已移除 ruff，无 lint 门槛）

## 8. 影响面备忘

- 所有内部 import 路径变更（`api.*` → 各模块；`db.engine` → `core.database`；`lightrag.*` → `knowledge.*`）
- `docs/` 为本次新建目录；README 的 Layout 一节与（当前为空的）AGENTS.md 需同步重写
