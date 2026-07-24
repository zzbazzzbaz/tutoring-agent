# 前端测试服务器 API 联调指南

本文面向优化本项目 `frontend/` 的开发者，说明如何让本地或新页面直接调用已部署的测试环境服务。

## 测试环境

- 页面地址：`https://tutoring.chatgqt.top`
- 业务 API 基地址：`https://tutoring.chatgqt.top/api`
- Agent API 基地址：`https://tutoring.chatgqt.top/agent`
- Agent ID：`tutor`

生产部署时，前端使用同源相对路径：`/api` 与 `/agent`。Nginx 会将它们分别转发到业务 API 和 Agent 服务。因此，在已部署页面中应优先继续使用相对路径，不要改为公开调试端口。

## 本地前端直连测试环境

在 `frontend/.env.local` 中写入以下配置后启动前端：

```dotenv
NEXT_PUBLIC_API_URL=https://tutoring.chatgqt.top/api
NEXT_PUBLIC_AGENT_URL=https://tutoring.chatgqt.top/agent
NEXT_PUBLIC_ASSISTANT_ID=tutor
```

```bash
cd frontend
npm run dev
```

`NEXT_PUBLIC_*` 会在 Next.js 浏览器构建中公开。只能放 API 地址、Agent 地址等可公开配置，绝不能放数据库、Redis、Neo4j、LLM 或服务器 SSH 凭据。

## 测试账号

以下是测试环境账号，凭据按当前测试环境要求明文记录。不要将这些账号用于正式生产环境。

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 教师 | `teacher1` | `teacher123` |
| 学生 | `student1` | `student123` |
| 学生 | `student2` | `student123` |

## 认证与业务 API

先调用登录接口获取访问令牌：

```ts
const response = await fetch(
  "https://tutoring.chatgqt.top/api/auth/login",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "teacher1", password: "teacher123" }),
  },
);

const { access_token } = await response.json();
```

后续需要登录态的 REST 请求带上 `Authorization: Bearer <access_token>`：

```ts
const response = await fetch(
  "https://tutoring.chatgqt.top/api/sessions",
  {
    headers: { Authorization: `Bearer ${access_token}` },
  },
);
const sessions = await response.json();
```

项目现有封装在 `src/lib/api/client.ts`：它从 `localStorage` 的 `tutoring_token` 自动读取令牌，并为 JSON 请求添加 Bearer Token。新页面优先复用 `api`、`authApi`、`sessionsApi`、`projectsApi` 等封装，而不是重复实现请求逻辑。

常用业务接口如下：

| 功能 | 方法与路径 |
| --- | --- |
| 登录 | `POST /api/auth/login` |
| 当前用户 | `GET /api/auth/me` |
| 会话列表/创建 | `GET` / `POST /api/sessions` |
| 单个会话 | `GET` / `PATCH` / `DELETE /api/sessions/{sessionId}` |
| 已发布项目 | `GET /api/projects?status=published` |
| 教师学生列表 | `GET /api/users/students`，仅教师可用 |

## Agent 与流式聊天

Agent 需要相同的 Bearer Token。先创建业务会话，再使用同一个 UUID 创建 Agent thread；当前 UI 的 `SessionProvider` 已实现这一步。

```ts
import { Client } from "@langchain/langgraph-sdk";

const agentUrl = "https://tutoring.chatgqt.top/agent";
const client = new Client({
  apiUrl: agentUrl,
  defaultHeaders: { Authorization: `Bearer ${accessToken}` },
});

await client.threads.create({ threadId: sessionId });
```

浏览器中若 `NEXT_PUBLIC_AGENT_URL=/agent`，不要把这个相对路径直接传给 `@langchain/langgraph-sdk`。SDK 需要绝对 URL。复用 `src/components/chat/client.ts` 的 `getAgentApiUrl()` 和 `createClient()`，它们会把 `/agent` 解析成当前页面域名下的绝对地址。

流式运行由 `StreamProvider` 调用 SDK 的 stream API，实际请求形如：

```text
POST /agent/threads/{sessionId}/runs/stream
Authorization: Bearer <access_token>
```

创建或加载线程时也会使用：

```text
POST /agent/threads
POST /agent/threads/{sessionId}/history
GET  /agent/info
```

在测试环境中，上述 `/agent` 请求已验证可用于创建线程、获取历史记录和流式运行。

## LightRAG 知识库

前端不直接调用 LightRAG 的公开端口，而是通过业务 API 的 `/api/lightrag/...` 路由访问。已有封装在 `src/lib/api/lightrag.ts`。

| 功能 | 方法与路径 |
| --- | --- |
| 上传文档 | `POST /api/lightrag/documents/upload`，使用 `FormData` |
| 文档分页列表 | `POST /api/lightrag/documents/paginated` |
| 文档状态统计 | `GET /api/lightrag/documents/status_counts` |
| 处理管线状态 | `GET /api/lightrag/documents/pipeline_status` |
| 删除文档 | `DELETE /api/lightrag/documents/delete_document` |
| 图标签 | `GET /api/lightrag/graph/label/popular` |
| 知识图谱 | `GET /api/lightrag/graphs` |

上传时使用 `api.postForm()` 或原生 `fetch` 携带 `FormData`，不要手动设置 `Content-Type`，浏览器会补充 multipart boundary。

## 公开调试端口

云服务器 `82.157.111.219` 已开放 `10000-10050`。当前服务使用其中的端口如下：

| 端口 | 服务 | 用途 |
| --- | --- | --- |
| `10000` | PostgreSQL | 数据库调试 |
| `10001` | Neo4j HTTP | 图数据库调试 |
| `10002` | Neo4j Bolt | 图数据库驱动连接 |
| `10003` | Redis | 缓存与队列调试 |
| `10004` | LightRAG | 知识库服务调试 |
| `10005` | API Server | 业务 API 调试 |
| `10006` | Agent Server | LangGraph Agent 调试 |
| `10007` | Frontend | 前端服务调试 |

浏览器功能默认使用 `https://tutoring.chatgqt.top/api` 和 `https://tutoring.chatgqt.top/agent`。直接使用 `http://82.157.111.219:10005` 或 `:10006` 可能引入跨域、HTTPS mixed-content 或路径前缀差异，只应在调试时使用。

## 部署路由与排查

服务器 Nginx 当前路由为：

```text
https://tutoring.chatgqt.top/       -> frontend :10007
https://tutoring.chatgqt.top/api/   -> api_server :10005
https://tutoring.chatgqt.top/agent/ -> agent_server :10006
```

HTTP `80` 会重定向到 HTTPS `443`。遇到接口问题时，按以下顺序检查：

1. 确认浏览器请求使用 HTTPS 域名，且路径以 `/api` 或 `/agent` 开头。
2. 确认登录成功，并在请求中发送 Bearer Token。
3. 确认 Agent SDK 使用绝对 `apiUrl`，尤其是在相对 `/agent` 配置下。
4. 检查 `GET /api/health` 和 `GET /agent/ok` 是否返回 `200`。
5. 对流式聊天，检查浏览器 Network 中的 `POST /agent/threads/{sessionId}/runs/stream`；它应返回 `200`。
