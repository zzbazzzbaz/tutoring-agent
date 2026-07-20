# Frontend Rebuild Design

> Date: 2026-07-20
> Status: Approved

## 1. Overview

全新重写教学 Agent 前端，放在 `frontend/` 目录。参考 LightRAG webui 的视觉风格和技术栈，但只实现当前后端已支持的 API（无知识库/图谱模块）。

### Scope

| 模块 | 学生 | 教师 |
|------|------|------|
| 登录 | ✅ | ✅ |
| 聊天（SSE + 答题中断） | ✅ | ✅ |
| 学生管理（列表/导入/重置/删除） | ❌ | ✅ |
| 项目（只读列表） | ✅ | ✅ CRUD |

### Out of Scope (YAGNI)

- 知识库管理（文档上传）-- 后端无 API，后期再加
- 知识图谱可视化 -- 后端无 API，后期再加
- 移动端适配
- Mermaid 图表渲染
- 11 种语言（只做中英双语）
- 前端单元测试（靠 lint + build + E2E 验证）

## 2. Tech Stack

复用 LightRAG webui 的技术栈和模式：

| 类别 | 选型 | 说明 |
|------|------|------|
| 框架 | React 19 + TypeScript ~6.0 | 严格模式 |
| 构建 | Vite 8 | dev proxy -> localhost:8000 |
| 包管理 | **Bun** | 兼容 npm |
| 路由 | react-router-dom 7 (HashRouter) | 仅用于 login vs app guard |
| 状态管理 | Zustand 5 + persist + createSelectors | 复用 LightRAG webui 的 selector 模式 |
| HTTP | axios + fetch(SSE) | Bearer token 拦截器 |
| UI | shadcn/ui (new-york, zinc) + Radix UI | CSS 变量驱动主题 |
| CSS | Tailwind CSS v4 | @tailwindcss/vite 插件 + typography + animate |
| i18n | i18next + react-i18next | zh（默认） + en |
| Markdown | react-markdown + remark-gfm + remark-math + rehype-katex | GFM + KaTeX 数学公式 |
| 图标 | lucide-react | |
| 通知 | sonner | |
| 滚动条 | tailwind-scrollbar | |
| Lint | ESLint + @stylistic + typescript-eslint + Prettier | 2 空格缩进，单引号 |

### 不引入的依赖

- Sigma.js / graphology / @react-sigma/* -- 知识图谱后期再加
- Mermaid -- 不需要图表渲染
- @tanstack/react-table -- 用原生 table 足够
- react-dropzone -- 学生导入用原生 file input
- cmdk -- 不需要 command palette

## 3. Architecture: Tab-based SPA

```
HashRouter
├── /login              -> LoginPage (公开)
└── /*                  -> AppShell (需认证)
    ├── Tab: Chat       -> ChatTab (两栏: SessionList + ChatView)
    ├── Tab: Students   -> StudentsTab (教师 only)
    └── Tab: Projects   -> ProjectsTab
```

- 主路由仅用于 login vs app 的 auth guard
- 主应用内部用 Radix Tabs 切换模块，**不用 react-router 子路由**
- Tab 状态持久化到 settings store，刷新页面保持上次 Tab
- **切换 Tab 不卸载组件**（用 `display: none` 而非条件渲染），聊天 SSE 状态不丢失

### 顶部导航

```
┌──────────────────────────────────────────────────────┐
│  [Logo] 教学 Agent    Chat | Students | Projects     │
│                                      [设置 ▾]        │
├──────────────────────────────────────────────────────┤
│                                                       │
│                  当前 Tab 内容                        │
│                                                       │
└──────────────────────────────────────────────────────┘
```

- Tab 列表根据 `user.role` 动态过滤（学生看不到 Students Tab）
- 设置菜单：主题切换 / 语言切换 / 修改密码 / 退出登录

## 4. Project Structure

```
frontend/
├── package.json
├── bun.lock
├── vite.config.ts          # dev proxy -> localhost:8000
├── tsconfig.json           # 严格模式, @/* -> src/*
├── tsconfig.node.json
├── tailwind.config.js       # shadcn/ui 主题 + typography
├── eslint.config.js
├── prettier.config.json
├── components.json         # shadcn/ui 配置 (new-york / zinc)
├── index.html
├── .env.development        # VITE_API_BASE= (空, 走 proxy)
└── src/
    ├── main.tsx            # 入口: render + i18n + katex CSS
    ├── App.tsx             # AppShell: Header + Tabs + SettingsMenu
    ├── AppRouter.tsx       # HashRouter + RequireAuth
    ├── index.css           # Tailwind + shadcn CSS 变量 + 暗色模式
    ├── i18n.ts             # i18next 初始化
    ├── api/
    │   ├── client.ts       # axios 实例 + Bearer token 拦截器 + 401 重定向
    │   ├── auth.ts         # login / logout / me / changePassword
    │   ├── sessions.ts     # CRUD + messages + questions
    │   ├── chat.ts         # SSE: streamMessage + resumeQuiz (async generator)
    │   ├── projects.ts     # CRUD
    │   └── users.ts        # listStudents / listTeachers / import / reset / delete
    ├── stores/
    │   ├── auth.ts         # token + user info (persist)
    │   ├── chat.ts         # SSE 状态机: sessions / currentSession / items / streamStatus
    │   └── settings.ts     # theme + language + activeTab (persist)
    ├── features/
    │   ├── login/
    │   │   └── LoginPage.tsx
    │   ├── chat/
    │   │   ├── ChatTab.tsx         # 两栏布局容器
    │   │   ├── SessionList.tsx     # 左栏会话列表
    │   │   ├── NewSessionDialog.tsx
    │   │   ├── ChatView.tsx       # 消息流 + 输入框
    │   │   ├── MessageBubble.tsx  # Markdown 渲染 + 复制
    │   │   ├── QuizCard.tsx       # 答题卡片 (单选/多选/简答)
    │   │   └── ChatInput.tsx      # 输入框 + 发送
    │   ├── students/
    │   │   └── StudentsTab.tsx   # 列表 + 导入 + 重置 + 删除
    │   ├── projects/
    │   │   ├── ProjectsTab.tsx    # 列表 (学生只读, 教师可 CRUD)
    │   │   └── ProjectEditor.tsx  # Markdown 编辑器 + 实时预览
    │   └── shared/
    │       ├── MarkdownRenderer.tsx
    │       └── SettingsMenu.tsx    # 主题/语言/改密码/退出
    ├── components/
    │   └── ui/              # shadcn/ui 组件 (按需 add)
    ├── hooks/
    │   ├── useTheme.ts      # light/dark/system + OS 偏好监听
    │   └── useDebounce.ts
    ├── lib/
    │   ├── cn.ts            # class merge (clsx + tailwind-merge)
    │   ├── formatDate.ts   # formatRelativeTime + formatDateTime
    │   └── parseSSE.ts      # SSE 流解析 (async generator)
    ├── locales/
    │   ├── zh.json
    │   └── en.json
    └── types/
        ├── session.ts       # SessionOut
        ├── message.ts       # MessageOut
        ├── question.ts      # QuestionOut (含 verdict/diagnosis)
        ├── project.ts       # ProjectOut
        ├── chat.ts          # ChatItem + StreamStatus + SSEEvent
        └── user.ts          # UserOut + LoginResponse
```

## 5. State Management

复用 LightRAG webui 的 Zustand 模式：`createSelectors` 包装器自动生成 selector hooks。

### auth store (persist)

```typescript
interface AuthState {
  token: string | null
  user: { id: string; username: string; role: 'student' | 'teacher'; name: string } | null
  login: (token: string, user: User) => void
  logout: () => void
  isAuthenticated: () => boolean
}
```
- persist key: `tutoring-auth`
- logout 时调 `POST /auth/logout` + 清除本地状态

### chat store (无 persist)

```typescript
interface ChatState {
  sessions: SessionOut[]
  currentSession: SessionOut | null
  items: ChatItem[]              // messages + questions 合并排序
  streamStatus: 'idle' | 'streaming' | 'quiz_interrupted' | 'error'
  streamingContent: string      // 流式 agent 文本
  pendingQuiz: QuestionOut | null
  error: string | null

  loadSessions: () => Promise<void>
  selectSession: (id: string) => Promise<void>
  createSession: (mode, projectId?) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  submitQuiz: (answer: string) => Promise<void>
  skipQuiz: () => Promise<void>
  resetStream: () => void
}
```

SSE 事件处理：
- `text`: 追加到 `streamingContent`
- `quiz_interrupt`: 切到 `quiz_interrupted`，存 `pendingQuiz`
- `done`: 落库 `streamingContent` 为新 message，切回 `idle`
- `error`: 切到 `error`，存 error message

乐观更新 + 失败回滚：发送消息时立即追加 user message 到 items，SSE 失败则回滚。

### settings store (persist)

```typescript
interface SettingsState {
  theme: 'light' | 'dark' | 'system'
  language: 'zh' | 'en'
  activeTab: string
  setTheme: (theme) => void
  setLanguage: (lang) => void
  setActiveTab: (tab) => void
}
```
- persist key: `tutoring-settings`

## 6. Auth Flow

1. `POST /auth/login` -> `{ token, user: { id, username, role, name } }`
2. token + user 存入 auth store (persist to localStorage)
3. axios 请求拦截器注入 `Authorization: Bearer <token>`
4. 401 响应拦截器：清除 token，重定向到 `#/login`
5. SSE 请求手动注入 `Authorization: Bearer <token>` header
6. `POST /auth/logout`：后端删除 token，前端清除状态
7. `GET /auth/me`：页面刷新时验证 token 有效性

### Route Guard

```typescript
function RequireAuth({ children }) {
  const token = useAuthStore.use.token()
  if (!token) return <Navigate to="/login" />
  return children
}
```

## 7. Chat Module

### ChatTab 布局 (两栏)

```
┌──────────────┬──────────────────────────────┐
│ 会话列表      │ 消息流                        │
│              │  [user] 你好                  │
│ - session 1  │  [agent] Hello! ...           │
│ - session 2  │  [quiz] 选择题卡片             │
│ - session 3  │  [agent] 回答正确...           │
│              │                              │
│ [+ 新建会话] │ ┌────────────────────────┐   │
│              │ │ 输入框            [发送] │   │
└──────────────┴──────────────────────────────┘
```

### 新建会话

- free 模式：直接创建
- project 模式：下拉选择已发布项目

### 消息渲染

messages + questions 按 `created_at` 合并排序为 `ChatItem[]`：
```typescript
type ChatItem =
  | { type: 'message'; data: MessageOut }
  | { type: 'quiz'; data: QuestionOut }
  | { type: 'streaming'; data: { content: string } }
```

### Quiz 交互

1. 收到 `quiz_interrupt` SSE 事件 -> 切到 `quiz_interrupted`
2. 渲染 QuizCard（单选/多选/简答），禁用输入框
3. 用户作答 -> `POST /chat/sessions/{id}/quiz/resume` (SSE)
4. resume 流可能再次触发 `quiz_interrupt`（连续出题）
5. answered 的 quiz 锁定，显示答案对比

### 409 SESSION_INTERRUPTED 处理

发消息时收到 409 -> 自动切到 `quiz_interrupted` 状态，重新拉取 questions 列表。

## 8. Student Management Module

### StudentsTab

```
┌─────────────────────────────────────────────────┐
│  [导入 Excel]                                    │
├─────────────────────────────────────────────────┤
│  学号      │ 姓名      │ 创建时间      │ 操作    │
│  2023001   │ 张三      │ 2026-07-20    │ 重置 删除│
│  2023002   │ 李四      │ 2026-07-20    │ 重置 删除│
│  student1  │ 测试学生1  │ 2026-07-20    │ 重置 删除│
└─────────────────────────────────────────────────┘
```

- **列表**：`GET /users/students` -> UserOut[]
- **导入**：上传 .xlsx 文件 -> `POST /users/students/import` -> 弹结果 `{total, created, skipped, errors}`
- **重置密码**：AlertDialog 确认 -> `POST /users/{id}/reset-password` -> toast "密码已重置为 123456"
- **删除**：AlertDialog 确认 -> `DELETE /users/{id}` -> 从列表移除

## 9. Projects Module

### ProjectsTab (列表)

- 学生：只读列表，可查看项目内容
- 教师：CRUD（新建/编辑/发布/删除）

```
┌─────────────────────────────────────────────────┐
│  [新建项目]                  [全部] [草稿] [已发布]│
├─────────────────────────────────────────────────┤
│  项目名称        │ 状态    │ 更新时间      │ 操作  │
│  数据结构入门    │ 已发布   │ 2026-07-20   │ 编辑 删除│
│  算法基础       │ 草稿    │ 2026-07-19   │ 编辑 删除│
└─────────────────────────────────────────────────┘
```

### ProjectEditor

- Markdown 编辑器（左侧编辑 + 右侧实时预览）
- 发布/取消发布按钮
- 保存/返回

## 10. Shared Features

### 暗色模式

- 三种模式：`light` / `dark` / `system`
- `system` 模式监听 `prefers-color-scheme` OS 偏好
- 通过 `.dark` class 切换 CSS 变量
- 设置菜单中切换，持久化到 settings store

### i18n (中英双语)

- 默认中文 (`zh`)
- i18next + react-i18next
- 语言切换即时生效，无需刷新
- 持久化到 settings store
- locale 文件：`locales/zh.json` + `locales/en.json`
- 命名空间：`common` / `login` / `chat` / `students` / `projects` / `settings`

### 修改密码

- SettingsMenu 弹出 Dialog
- 输入旧密码 + 新密码
- `POST /auth/change-password`
- 成功 toast，失败 toast 错误信息

### 退出登录

- SettingsMenu 点击退出
- 调 `POST /auth/logout`
- 清除 auth store + chat store
- 跳转 `/login`

## 11. API Layer

### api/client.ts

```typescript
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
})

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.hash = '#/login'
    }
    const msg = err.response?.data?.detail?.error?.message
    if (msg) toast.error(msg)
    return Promise.reject(err)
  }
)

export default apiClient
```

### SSE 请求 (api/chat.ts)

```typescript
export async function* streamMessage(
  sessionId: string,
  content: string,
  token: string
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  })
  yield* parseSSE(response)
}
```

### vite.config.ts proxy

```typescript
server: {
  proxy: {
    '/health': 'http://localhost:8000',
    '/auth': 'http://localhost:8000',
    '/users': 'http://localhost:8000',
    '/projects': 'http://localhost:8000',
    '/sessions': 'http://localhost:8000',
    '/chat': 'http://localhost:8000',
  }
}
```

## 12. Types

### 后端 API 对应的 TypeScript 类型

```typescript
// types/user.ts
interface UserOut {
  id: string
  username: string
  role: 'student' | 'teacher'
  name: string
  created_at: string
}

// types/session.ts
interface SessionOut {
  id: string
  user_id: string
  mode: 'free' | 'project'
  project_id: string | null
  project_name: string | null
  title: string | null
  status: 'active' | 'ended'
  last_active_at: string
  created_at: string
}

// types/message.ts
interface MessageOut {
  id: string
  session_id: string
  role: 'user' | 'agent'
  content: string
  created_at: string
}

// types/question.ts
interface QuestionOut {
  id: string
  session_id: string
  topic: string
  q_type: 'single' | 'multi' | 'short'
  stem: string
  options: string[] | null
  answer: string
  analysis: string | null
  status: 'pending' | 'answered' | 'skipped'
  user_answer: string | null
  created_at: string
  answered_at: string | null
}

// types/project.ts
interface ProjectOut {
  id: string
  name: string
  background_md: string
  status: 'draft' | 'published'
  created_at: string
  updated_at: string
}

// types/chat.ts
type StreamStatus = 'idle' | 'streaming' | 'quiz_interrupted' | 'error'

type SSEEvent =
  | { event: 'text'; data: { content: string } }
  | { event: 'quiz_interrupt'; data: { question_id: string; topic: string; q_type: string; stem: string; options: string[] | null } }
  | { event: 'done'; data: Record<string, never> }
  | { event: 'error'; data: { message: string; code: string } }

type ChatItem =
  | { type: 'message'; data: MessageOut }
  | { type: 'quiz'; data: QuestionOut }
  | { type: 'streaming'; data: { content: string } }
```

## 13. Error Handling

### 统一错误格式

后端返回：
```json
{ "detail": { "error": { "code": "ERROR_CODE", "message": "人类可读信息" } } }
```

axios 响应拦截器统一处理：提取 `message` -> `toast.error(msg)` -> reject。

### 常见错误码

| 码 | HTTP | 说明 |
|----|------|------|
| MISSING_TOKEN | 401 | 未登录 |
| INVALID_TOKEN | 401 | token 无效 |
| INVALID_CREDENTIALS | 401 | 用户名/密码错误 |
| TEACHER_ONLY | 403 | 需教师权限 |
| FORBIDDEN | 403 | 无权操作 |
| SESSION_NOT_FOUND | 404 | 会话不存在 |
| PROJECT_NOT_FOUND | 404 | 项目不存在 |
| SESSION_ENDED | 409 | 会话已结束 |
| SESSION_INTERRUPTED | 409 | 会话有题待答 |
| SESSION_NOT_INTERRUPTED | 409 | 会话无题待答 |
| VALIDATION_ERROR | 422 | 参数校验失败 |
| INVALID_FILE | 422 | 文件格式不对 |
| AGENT_ERROR | 200 (SSE) | agent 运行异常 |

### SSE 错误

SSE 的 HTTP 状态恒为 200。业务错误通过 `event: error` 下发，前端在 SSE 处理器中单独处理。

## 14. Scripts

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit"
  }
}
```

## 15. Design Decisions

### 为什么不用 react-router 子路由？

Tab 切换时如果用路由卸载组件，聊天 SSE 状态会丢失。用 Radix Tabs + `display: none` 保持所有 Tab 挂载，切换不丢状态。只需一个路由分割：login vs app。

### 为什么用 Bun？

LightRAG webui 用 Bun，速度更快（install + dev server 启动），兼容 npm 生态。

### 为什么不用 @tanstack/react-table？

学生列表和项目列表都很简单（< 100 行），原生 `<table>` 足够，引入 TanStack Table 是冗余依赖。

### 为什么 Tab 用 display:none 而非条件渲染？

用户在 Chat Tab 发消息时 SSE 正在流式输出，切换到 Projects Tab 再回来，如果组件被卸载，SSE 连接和流式状态全丢。用 `display: none` 保持组件挂载，切换回来继续显示。

### 为什么知识图谱模块暂不做？

后端没有 `/graph/*` API。做前端 UI 但没数据没意义。等后端加好图谱 API 再做前端，可以同时移植 LightRAG webui 的 Sigma.js 组件。
