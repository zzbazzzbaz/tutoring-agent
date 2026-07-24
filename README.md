## 项目架构

教学 Agent 是一个基于苏格拉底式教学法的智能辅导系统，采用前后端分离 + 多微服务的架构。前端通过 LangGraph SDK 与 Agent Server 流式对话，Agent Server 经 API Server 鉴权后运行，并调用 LightRAG 检索课程知识库。

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                    │
│  student/chat · teacher/chat · 知识库管理 · 项目管理 · 登录    │
└──────────┬───────────────────────────────┬──────────────────┘
           │ REST (业务 API)                │ LangGraph SDK (流式对话)
           ▼                               ▼
┌─────────────────────┐          ┌────────────────────────────┐
│   API Server        │          │     Agent Server           │
│   (FastAPI)         │          │     (LangGraph)            │
│                     │◄─────────┤  /auth/internal/agent/      │
│  · 用户认证 (token)  │  鉴权回调  │    authorize              │
│  · 会话管理         │ (共享密钥) │                            │
│  · 项目管理         │          │  · Socratic Agent          │
│  · LightRAG 代理    │          │  · tools:                  │
│  · 内部鉴权端点      │          │    - search_knowledge      │
└────────┬────────────┘          │    - present_question      │
         │ httpx 代理              │  (interrupt → 学生作答)     │
         │                       └──────────┬─────────────────┘
         ▼                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      LightRAG (知识检索)                     │
│        RAG (向量检索) + 知识图谱 (Neo4j)                     │
└────────┬───────────────────────────────┬────────────────────┘
         ▼                               ▼
┌─────────────────────┐          ┌────────────────────────────┐
│   PostgreSQL        │          │        Neo4j               │
│   (pgvector)        │          │     (图数据库)              │
│                     │          │                            │
│  · tutoring_db      │          │  · LightRAG 知识图谱       │
│    (业务数据)        │          │                            │
│  · tutoring_agent_  │          │                            │
│    server_db        │          │                            │
│    (LangGraph 持久化)│          │                            │
└─────────────────────┘          └────────────────────────────┘
```

### 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Next.js 15 · React 19 · TypeScript · Tailwind CSS · LangGraph SDK · Radix UI · Sigma.js (知识图谱可视化) |
| API Server | FastAPI · SQLModel · asyncpg · bcrypt · httpx |
| Agent Server | LangGraph · LangChain · langgraph-sdk · DashScope (通义千问 LLM) |
| 知识库 | LightRAG (向量检索 + 知识图谱 RAG) |
| 数据库 | PostgreSQL 17 (pgvector) · Neo4j 5.26 |
| 部署 | Docker Compose · Nginx |

### 目录结构

```
教学Agent/
├── deploy/                  # Docker Compose 部署配置
│   ├── docker-compose.yml         # 本地开发基础设施 (postgres/neo4j/lightrag)
│   ├── docker-compose-prod.yml    # 生产完整部署 (含 api_server/agent_server/frontend)
│   └── init-db.sql                # 数据库初始化 (pgvector + agent_server_db)
├── docs/                    # 文档
├── frontend/                # Next.js 前端
│   └── src/
│       ├── app/                   # 路由 (student/* · teacher/* · login)
│       ├── components/            # UI 组件 (chat · knowledge · projects · auth)
│       ├── lib/                   # API 客户端与工具函数
│       └── lightrag-webui/        # LightRAG WebUI 源码 (vendor)
├── services/
│   ├── api_server/          # FastAPI 业务后端
│   │   └── src/tutoring/
│   │       ├── app.py             # FastAPI 入口与路由注册
│   │       ├── auth/              # 登录/登出/改密 + 内部 agent 鉴权
│   │       ├── core/              # 配置、数据库、依赖注入、错误处理
│   │       ├── db/                # SQLModel 模型与仓储层
│   │       ├── users/             # 用户管理 (头像等)
│   │       ├── sessions/          # 聊天会话 CRUD
│   │       ├── projects/          # 教学项目 (draft/published)
│   │       └── lightrag/          # LightRAG API 代理 (仅教师)
│   └── agent_server/        # LangGraph Agent 服务
│       └── src/teaching_agent/
│           ├── app.py             # graph 入口 (get_graph)
│           ├── agent/             # Agent 工厂与系统 prompt
│           ├── tools/             # Agent 工具 (knowledge · quiz)
│           ├── auth/              # LangGraph Auth 中间件与上下文
│           ├── infrastructure/    # LLM、LightRAG 客户端、API Server 鉴权
│           └── config.py          # 环境配置
└── README.md
```

### 核心服务说明

#### 1. API Server (`services/api_server`) — 业务后端

FastAPI 应用，负责所有业务逻辑与数据持久化，是系统的信任锚点。

- **认证体系**：用户名/密码登录，bcrypt 存储，token 无过期（登出即删除行）。Token 通过 `Authorization: Bearer <token>` 传递。
- **会话模型**：`Session.id` 复用为 LangGraph `thread_id`，支持 `free`（自由学习）和 `project`（项目学习）两种模式。
- **内部鉴权**：`POST /auth/internal/agent/authorize` 端点供 Agent Server 回调，通过共享密钥 (`X-Agent-Server-Secret`) + 用户 token 双重校验，返回用户身份、会话访问权限 (`identity`/`read`/`run`) 和 Agent 上下文（教学模式 / 项目背景）。
- **LightRAG 代理**：教师通过 API Server 代理操作知识库（上传文档、查看图谱、删除文档），学生无权访问。

#### 2. Agent Server (`services/agent_server`) — 教学智能体

基于 LangGraph 的 Agent 运行时，通过 `langgraph dev` 或 `langgraph api` 启动。

- **Agent 架构**：使用 `langchain.agents.create_agent` 构建，基于通义千问 LLM（DashScope），`enable_thinking: False`。
- **系统 Prompt**：苏格拉底式教学法 — 绝不直接给答案，通过提问引导学生推导；支持自由模式与项目模式两种 prompt 模板。
- **工具集**：
  - `search_knowledge(query)` — 调用 LightRAG `/query`（mix 模式，融合向量 + 图谱检索）获取知识片段。
  - `present_question(topic, q_type, stem, options)` — 通过 LangGraph `interrupt()` 暂停执行，等待学生作答后恢复（Human-in-the-Loop）。
- **鉴权链路**：每个请求经 LangGraph Auth 中间件拦截，从 URL 提取 `thread_id`（= 会话 ID），回调 API Server `/auth/internal/agent/authorize` 校验用户身份与会话归属，并按访问级别授予 `threads:read` / `threads:run` 权限。
- **上下文注入**：鉴权时 API Server 返回 `AgentContextV1`（教学模式 + 项目背景），Agent Server 据此渲染系统 prompt，确保 Agent 行为与教学场景匹配。

#### 3. Frontend (`frontend`) — Web 前端

Next.js App Router 应用，按角色区分路由（`/student/*` · `/teacher/*`）。

- **中间件鉴权**：`middleware.ts` 通过 cookie (`tutoring_auth` + `tutoring_role`) 控制路由访问，未登录跳转 `/login`，角色不匹配重定向。
- **对话交互**：前端通过 `@langchain/langgraph-sdk` 直连 Agent Server，支持流式输出、interrupt（出题 → 学生作答 → 恢复）等 LangGraph 原生能力。
- **知识库可视化**：集成 LightRAG WebUI 源码（`src/lightrag-webui/`），使用 Sigma.js 渲染知识图谱，支持文档管理与图谱浏览。
- **教师功能**：教师可上传知识库文档、查看知识图谱、管理教学项目（draft/published）、只读查看学生会话。

### 数据流：一次对话的完整链路

```
1. 学生登录 → API Server /auth/login → 返回 token (存入 cookie)
2. 创建会话 → API Server POST /sessions → 返回 session_id (= thread_id)
3. 发送消息 → 前端 LangGraph SDK → Agent Server POST /threads/{id}/runs
4. Agent Server Auth 中间件 → 回调 API Server /auth/internal/agent/authorize
   ├─ 校验用户 token + 共享密钥
   ├─ 校验会话归属与访问权限
   └─ 返回 AgentContextV1 (教学模式/项目背景)
5. Agent 运行 → 可能调用 search_knowledge (→ LightRAG) 或 present_question (→ interrupt)
6. 若 interrupt → 前端渲染题目 UI → 学生作答 → POST /threads/{id}/runs 恢复
7. Agent 评估作答 → 继续苏格拉底式追问 → 流式返回
```

### 部署模式

- **本地开发**：`deploy/docker-compose.yml` 仅启动基础设施（PostgreSQL、Neo4j、LightRAG），API Server 与 Agent Server 以 `uv run uvicorn` / `langgraph dev` 热重载运行。
- **生产部署**：`deploy/docker-compose-prod.yml` 一键启动全部 7 个服务（含 Redis 供 LangGraph 队列协调），服务间通过 Compose DNS 通信。

---

## 启动命令

cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/deploy"
docker compose -f docker-compose.yml up -d

cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/services/api_server"
uv run uvicorn tutoring.app:app --host 127.0.0.1 --port 8000 --reload

cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/services/agent_server"
uv run langgraph dev --host 127.0.0.1 --port 2024

cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/frontend"
npm run dev

## TODO

- 知识库图谱界面当前存在编辑入口，但业务后端尚未适配实体/关系编辑 API；需要改为真正只读，或补齐后端代理与权限控制。
- 前端当前直接迁入 LightRAG WebUI 源码，依赖和组件边界偏重；需要整理代码质量，隔离 vendor 代码、清理未用模块并收敛适配层。
