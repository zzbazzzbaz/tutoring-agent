# 教学 Agent 前端设计文档

- 日期：2026-07-19
- 范围：教学 Agent 项目的前端（学生端 + 教师端），与后端 FastAPI + LightRAG + LangChain 1.x 协同
- 后端版本：v0.2.0（API 已完成，参考 `backend/README.md` 与 `backend/AGENTS.md`）

## 1. 背景与目标

后端已完成，提供以下能力：

- `/health` 健康检查
- `/projects` CRUD（教师创建项目，学生 project 模式引用）
- `/sessions` CRUD + `/sessions/{id}/messages` + `/sessions/{id}/questions`（会话历史）
- `/chat/sessions/{id}/messages`（SSE 流式对话）+ `/chat/sessions/{id}/quiz/resume`（SSE 续接答题）
- `/documents/*` LightRAG 代理（文档管理）
- `/graph/*` + `/graphs` LightRAG 代理（知识图谱）

前端需要为两类用户（学生、教师）提供 Web 界面：

- **学生端**：历史会话、查看会话详情、流式对话（含 quiz 中断/续接）
- **教师端**：知识库、知识图谱、项目配置

参考项目：`docs/_chat/LightRAG/lightrag_webui`（React 19 + Vite + Bun + Tailwind v4 + Radix + Zustand + Sigma.js）。

## 2. 关键决策（用户确认）

1. **应用架构**：单应用 + 角色路由（一个 Vite 工程，学生端/教师端路由前缀 `/student/*`、`/teacher/*`，共享代码放 `shared/`）。
2. **技术栈**：完全照搬 LightRAG webui，但去掉 `i18next`（项目仅中文）。即 React 19 + TypeScript + Vite 8 + Bun + Tailwind v4 + Radix UI（shadcn/ui）+ Zustand + axios + react-router 7 + Sigma.js/graphology + react-markdown + remark-gfm + rehype-katex + lucide-react + sonner。
3. **包管理器**：Bun（与 LightRAG webui 一致）。
4. **身份认证**：Mock 登录页。登录页输入用户名 + 密码（任意）+ 选角色（学生/教师），mock 验证后存 Zustand + localStorage。axios 拦截器注入 `X-User-Id` header。后端 `auth/` 模块就绪后升级为 JWT。
5. **学生端会话创建**：支持 free + project 两种模式。project 模式需从已 published 项目下拉中选一个。
6. **Quiz 展示**：对话流内联题目卡片（QuizCard 组件）。`quiz_interrupt` 事件到达时在对话流末尾插入题卡，学生在题卡上作答后锁定并显示 verdict/diagnosis/analysis，对话继续流式输出。
7. **教师端知识库/图谱**：拷贝并适配 LightRAG webui 的 `DocumentManager.tsx` 和 `GraphViewer.tsx`，把 API 调用改为后端代理路由。
8. **项目配置**：完整 CRUD + Markdown 编辑器带实时预览。
9. **会话详情**：messages + questions 按 `created_at` 时间戳合并到同一条对话流。
10. **学生端布局**：两栏（左：历史会话；中：对话区），不展示项目信息面板。
11. **E2E 测试**：使用 `agent-browser` skill 做最终功能验证（除 `bun run lint` + `bun run build` 外）。

## 3. 整体架构

### 3.1 目录结构

```
frontend/
├── package.json              # Bun + Vite
├── vite.config.ts            # dev proxy -> http://localhost:8000
├── tailwind.config.js
├── index.html
├── tsconfig.json
├── eslint.config.js
├── .env.development
└── src/
    ├── main.tsx
    ├── App.tsx               # 根 + Providers（Router/Theme/Toaster）
    ├── AppRouter.tsx         # 路由表 + 角色守卫
    ├── api/                  # axios 实例 + 各域 API 客户端
    │   ├── client.ts         # axios 实例，拦截器注入 X-User-Id
    │   ├── auth.ts           # mock login（未来换 /auth/login）
    │   ├── projects.ts       # /projects CRUD
    │   ├── sessions.ts       # /sessions + /messages + /questions
    │   ├── chat.ts           # SSE: /chat/sessions/{id}/messages + /quiz/resume
    │   ├── documents.ts      # /documents/* (适配自 LightRAG webui)
    │   └── graph.ts          # /graph/* + /graphs (适配自 LightRAG webui)
    ├── stores/
    │   ├── auth.ts           # 登录态 + 角色 + user_id (Zustand + persist)
    │   ├── chat.ts           # 当前会话 + 流式状态 + quiz interrupt 状态
    │   ├── graph.ts          # 拷贝自 LightRAG webui
    │   └── settings.ts       # 主题 + 偏好
    ├── features/
    │   ├── login/            # Mock 登录页
    │   │   └── LoginPage.tsx
    │   ├── student/          # 学生端
    │   │   ├── StudentLayout.tsx       # 两栏布局壳
    │   │   ├── SessionList.tsx         # 历史会话列表（左栏）
    │   │   ├── SessionDetail.tsx       # 会话详情（中栏，messages+questions 合并）
    │   │   ├── ChatStream.tsx          # 流式对话主区
    │   │   ├── ChatInput.tsx           # 输入框 + 发送
    │   │   ├── MessageBubble.tsx       # 消息气泡（含 Markdown 渲染）
    │   │   ├── QuizCard.tsx            # 题目卡片 + verdict 展示
    │   │   ├── NewSessionDialog.tsx    # 新建会话弹窗（free/project）
    │   │   └── SessionHeader.tsx       # 会话标题栏（标题 + 模式 badge + 删除）
    │   ├── teacher/          # 教师端
    │   │   ├── TeacherLayout.tsx       # Dashboard 顶部 Tab 壳
    │   │   ├── KnowledgeBase.tsx       # 知识库（适配 DocumentManager）
    │   │   ├── KnowledgeGraph.tsx      # 知识图谱（适配 GraphViewer）
    │   │   └── projects/
    │   │       ├── ProjectList.tsx    # 项目列表
    │   │       └── ProjectEditor.tsx  # 项目新建/编辑（Markdown 编辑器 + 预览）
    │   └── shared/           # 跨角色复用
    │       ├── MarkdownRenderer.tsx  # react-markdown + remark-gfm + rehype-katex
    │       ├── RoleSwitcher.tsx       # 顶栏角色切换（仅 dev 期显示）
    │       └── RoleBadge.tsx          # 角色徽章
    ├── components/ui/         # shadcn/ui 组件（button/dialog/input/...）
    ├── lib/                   # utils
    │   ├── cn.ts              # class merge
    │   ├── parseSSE.ts        # SSE 解析
    │   ├── useAsync.ts         # 通用数据获取 hook
    │   └── formatDate.ts      # 时间格式化
    ├── types/                 # 全局 TypeScript 类型
    │   ├── session.ts
    │   ├── message.ts
    │   ├── question.ts
    │   ├── project.ts
    │   └── chat.ts            # SSE 事件类型
    └── assets/
```

### 3.2 设计原则

1. **单向依赖**（镜像后端 DAG）：`api/` 只调 axios；`stores/` 调 `api/`；`features/` 调 `stores/` + `api/`；`components/ui/` 纯展示。
2. **角色隔离**：`features/student/` 和 `features/teacher/` 互不依赖，共享代码在 `features/shared/` 与 `components/ui/`。路由级 code-splitting 保证学生端不加载教师端代码。
3. **API 客户端按域分文件**：每个后端域一个文件，导出类型安全的函数。手写 TypeScript 类型（后端 schemas 不复杂，比 OpenAPI codegen 更可控）。
4. **YAGNI**：不引入 TanStack Query（约 20 个端点，手写 `useAsync` 足够）、不引入 i18next、不写前端单元测试。

## 4. 路由 + 角色守卫

### 4.1 路由表

```
/login                              LoginPage          公开
/                                   -> 重定向到角色首页
/student                            StudentLayout      需登录
  /student/sessions                 SessionList        默认首页（历史会话）
  /student/sessions/:id             SessionDetail      会话详情 + 流式对话
/teacher                            TeacherLayout     需 role=teacher
  /teacher/knowledge-base           KnowledgeBase     知识库
  /teacher/knowledge-graph          KnowledgeGraph    知识图谱
  /teacher/projects                 ProjectList       项目列表
  /teacher/projects/new             ProjectEditor     新建项目
  /teacher/projects/:id/edit        ProjectEditor     编辑项目
*                                   NotFound          404
```

### 4.2 Mock 登录流程

```
LoginPage
├── 用户名输入框（任意）
├── 密码输入框（任意，预设 123456 或留空均可）
├── 角色选择：单选 [学生 / 教师]
└── 登录按钮
    ↓
    authStore.login({ username, role: 'student' | 'teacher' })
    ├── 存 localStorage: { username, role, mockToken: 'mock-' + username }
    └── 跳转：role=student -> /student/sessions
              role=teacher -> /teacher/knowledge-base
```

### 4.3 axios 拦截器（`api/client.ts`）

```typescript
apiClient.interceptors.request.use(config => {
  config.headers['X-User-Id'] = authStore.getState().username ?? 'demo-student';
  return config;
});
// 未来 JWT：config.headers.Authorization = `Bearer ${token}`;
```

### 4.4 角色守卫（`AppRouter.tsx`）

```
<RequireAuth>          // 未登录 -> /login
  <RoleRoute role="student">
    <StudentLayout />   // /student/*
  </RoleRoute>
  <RoleRoute role="teacher">
    <TeacherLayout />   // /teacher/*
  </RoleRoute>
</RequireAuth>
```

- `RequireAuth`：读 `authStore.isAuthenticated`，false 则 `<Navigate to="/login" />`。
- `RoleRoute`：读 `authStore.role`，不匹配则重定向到本人角色首页。
- `RoleSwitcher`（仅 `import.meta.env.DEV` 时显示）：切换角色时清空会话状态并跳转，便于联调。

### 4.5 状态持久化

- `authStore`：Zustand + `persist` 中间件，key `tutoring-auth`，存 `{ isAuthenticated, username, role, mockToken }`。
- 其他 store（chat/graph/settings）：不持久化，刷新即重置。

### 4.6 取舍

- **不引入 react-router loader/data API**：纯客户端渲染，数据在组件 `useEffect` 获取。
- **不引入 TanStack Query**：手写 `useEffect + useState + AbortController` 足够。

## 5. 学生端布局 + 组件

### 5.1 两栏布局

```
┌──────────────────────────────────────────────────────────────────────┐
│ 顶栏: [教学Agent] [角色切换器(dev)]          [用户菜单]                │
├───────────────┬──────────────────────────────────────────────────────┤
│ 历史会话 (左栏) │  对话区 (中栏)                                        │
│               │                                                      │
│ [+ 新建会话]   │  ┌─ 会话标题栏 ──────────────────────────────────┐  │
│               │  │ TCP 三次握手  [自由学习]  [删除会话]            │  │
│ • TCP 三次握手 │  │ (project 模式: TCP 拥塞实验 [项目] badge)       │  │
│   2 分钟前     │  └────────────────────────────────────────────────┘  │
│               │  ┌─ 消息流 ───────────────────────────────────────┐  │
│ • 拥塞控制     │  │ agent / student 消息气泡（Markdown 渲染）       │  │
│   1 小时前     │  │ QuizCard 嵌入                                  │  │
│               │  └────────────────────────────────────────────────┘  │
│               │  ┌─ 输入框 ───────────────────────────────────────┐  │
│               │  │ [输入消息...]                          [发送]  │  │
│               │  └────────────────────────────────────────────────┘  │
└───────────────┴──────────────────────────────────────────────────────┘
```

- **左栏** `SessionList`：固定 280px 宽，列表项显示 `title || 上一条消息摘要` + `last_active_at` 相对时间。点击切换会话，跳 `/student/sessions/:id`。
- **中栏** `ChatStream`：自适应宽度，最小 400px。顶部 `SessionHeader`，底部 `ChatInput`。
- **移动端**：< 768px 左栏变抽屉（汉堡菜单触发）。

### 5.2 流式状态机

```
状态：idle | streaming | quiz_interrupted | error

idle
  └─ 用户点发送 ─────────────┐
                             ▼
streaming                    调 POST /chat/sessions/{id}/messages
  ├─ 收到 text 事件 ────────► 追加到当前 agent 气泡的 content
  ├─ 收到 quiz_interrupt ──► 状态切 quiz_interrupted，渲染题卡
  ├─ 收到 done 事件 ────────► 状态切 idle，agent 气泡落地为 MessageItem
  └─ 收到 error 事件 ───────► 状态切 error，toast 报错

quiz_interrupted
  ├─ 用户点"提交" ─────────► 调 POST /chat/sessions/{id}/quiz/resume
  │                          {action: "answer", answer: ...}
  │                          └─ 状态切 streaming，题卡锁定
  └─ 用户点"跳过" ─────────► 调 POST /chat/sessions/{id}/quiz/resume
                             {action: "skip"}
                             └─ 状态切 streaming，题卡锁定

error
  └─ 用户点"重试" ─────────► 重新发送上一条消息
```

**关键约束**：

- `streaming` 状态下输入框禁用，发送按钮变"停止"（仅 UI，后端不支持中断流，按钮禁用并提示"生成中..."）。
- `quiz_interrupted` 状态下输入框禁用，必须先答题或跳过。
- 同时只能有一个流式请求在飞（用 `AbortController` 防重复）。

### 5.3 消息合并渲染（`SessionDetail.loadSession`）

```
1. 并行拉取
   GET /sessions/{id}             -> SessionOut
   GET /sessions/{id}/messages     -> MessageOut[]
   GET /sessions/{id}/questions    -> QuestionOut[]
2. 合并
   items = [...messages.map(m => ({type:'message', ...m})),
            ...questions.map(q => ({type:'question', question: q}))]
   items.sort((a,b) => +new Date(a.created_at) - +new Date(b.created_at))
3. 渲染
   - type='message' -> MessageBubble（role=user/agent）
   - type='question' -> QuizCard（status=answered/skipped，锁定展示 stem/options/user_answer/verdict/diagnosis/analysis）
4. 滚动到底部
```

**注意**：question 的 `created_at` 是出题时间，`answered_at` 是答题时间。合并排序用 `created_at`（出题时刻插入对话流，符合实际交互顺序）。

### 5.4 QuizCard 组件

```
┌── 题卡 ──────────────────────────────────────────────┐
│ 📝 [单选题] TCP 三次握手                  状态: 作答中 │
│                                                       │
│ TCP 三次握手中，第二步发送的报文标志位是？              │
│                                                       │
│ ○ SYN                                                 │
│ ○ SYN + ACK                                           │
│ ○ ACK                                                 │
│ ○ FIN                                                 │
│                                                       │
│ [跳过]                              [提交]            │
└───────────────────────────────────────────────────────┘

提交后（answered/skipped 锁定）：
┌── 题卡 ──────────────────────────────────────────────┐
│ 📝 [单选题] TCP 三次握手                  ✅ 答对       │
│                                                       │
│ ... (题干 + 选项，用户选项高亮)                        │
│                                                       │
│ 你的答案: SYN + ACK   ✓                               │
│ 正确答案: SYN + ACK                                   │
│ 错因诊断: (答对时为空)                                 │
│ 解析: 第二步是服务端确认客户端的 SYN 并发送自己的 SYN   │
└───────────────────────────────────────────────────────┘
```

- `q_type=single`：单选 radio；`multi`：多选 checkbox；`short`：textarea。
- 提交前可改选项；提交后锁定，显示 `verdict` 徽章（correct 绿 / partial 黄 / wrong 红）+ `diagnosis` + `analysis`。
- `skipped` 状态显示"已跳过"徽章，不显示答案。

### 5.5 MessageBubble 组件

- `role=user`：右对齐，浅色气泡。
- `role=agent`：左对齐，深色气泡，内容用 `MarkdownRenderer` 渲染（支持代码块、表格、KaTeX 数学公式）。
- 顶部小字：角色名 + 相对时间。
- 复制按钮（hover 显示）。

### 5.6 ChatInput 组件

- 多行 textarea，Enter 发送，Shift+Enter 换行。
- 字符数计数（>2000 提示）。
- 发送中禁用。
- 拖拽文件时不响应（学生端不支持上传文档）。

### 5.7 NewSessionDialog 组件

```
┌── 新建会话 ─────────────────────────┐
│                                     │
│ 模式:  ○ 自由学习 (free)            │
│        ○ 项目学习 (project)          │
│                                     │
│ [项目下拉]  ← project 模式时显示    │
│   选择一个已发布项目...              │
│   • TCP 拥塞控制实验                │
│   • DNS 解析实践                     │
│   ...                               │
│                                     │
│              [取消]  [开始会话]     │
└─────────────────────────────────────┘
```

- 选 free：直接 `POST /sessions {mode: "free"}`，跳转新会话。
- 选 project：先 `GET /projects?status_filter=published` 填下拉，选项目后 `POST /sessions {mode: "project", project_id}`，跳转新会话。

## 6. 教师端布局 + 组件

### 6.1 顶部 Tab Dashboard 布局

```
┌──────────────────────────────────────────────────────────────────────┐
│ 顶栏: [教学Agent] [角色切换器(dev)]          [用户菜单]                │
├──────────────────────────────────────────────────────────────────────┤
│ [知识库] [知识图谱] [项目配置]                                          │
├──────────────────────────────────────────────────────────────────────┤
│                       Tab 内容区                                       │
└──────────────────────────────────────────────────────────────────────┘
```

- `TeacherLayout`：顶部 Tab 切换，内容区绝对定位铺满。默认进 `/teacher/knowledge-base`。
- 三个 Tab 独立加载，切换用 `display:none`（不卸载，避免重新拉数据）。路由级 code-splitting 仍生效。
- 顶部 Tab 高亮当前路由，点击切换路由。

### 6.2 知识库 `KnowledgeBase`（适配自 LightRAG webui DocumentManager）

```
┌──────────────────────────────────────────────────────────────────────┐
│ [上传文件] [插入文本] [扫描]   状态: ● idle     [刷新]                │
├──────────────────────────────────────────────────────────────────────┤
│ 文档列表                                                              │
│ ┌────────────────────────────────────────────────────────────────┐    │
│ │ 文件名              大小    状态      处理时间       操作      │    │
│ │ chapter1.pdf       2.3MB   ✅ processed  2024-07-19    [删除] │    │
│ │ notes.txt          12KB    ⏳ processing ...            [删除] │    │
│ │ failed.docx        1.1MB   ❌ failed  [查看错误]        [删除] │    │
│ └────────────────────────────────────────────────────────────────┘    │
│ 分页  < 1 2 3 >                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

**实现策略**：

- 从 `docs/_chat/LightRAG/lightrag_webui/src/features/DocumentManager.tsx` 拷贝，**裁剪掉** LightRAG 特有的 `documentRecoveryWarnings`、`status_filters` 高级筛选、批量操作等。
- API 调用改为后端代理路由：
  - 上传：`POST /documents/upload` (multipart)
  - 插入文本：`POST /documents/text` | `POST /documents/texts`
  - 扫描：`POST /documents/scan`
  - 分页列表：`POST /documents/paginated`
  - 删除：`DELETE /documents/delete_document`
  - 状态：`GET /documents/pipeline_status` | `GET /documents/status_counts` | `GET /documents/track_status/{id}`
- 顶部状态指示器轮询 `pipeline_status`（busy 时显示"处理中"，禁用上传）。
- **不做** LightRAG 的多语言、API key 提示、文档恢复警告等专有功能。

### 6.3 知识图谱 `KnowledgeGraph`（适配自 LightRAG webui GraphViewer）

```
┌──────────────────────────────────────────────────────────────────────┐
│ [搜索标签...]  [热门标签 ▼]   深度: [3] 节点上限: [1000]  [加载]      │
├────────────────────────────────┬─────────────────────────────────────┤
│                                │  节点详情                            │
│        Sigma.js 图渲染区        │  ┌───────────────────────────────┐  │
│      (节点 + 边 + minimap)      │  │ label: TCP                   │  │
│                                │  │ type: entity                  │  │
│        ○──────○                 │  │ degree: 12                    │  │
│       / \      \                │  │ properties: ...               │  │
│      ○   ○──────○               │  │ 关联实体:                      │  │
│       \  /                      │  │ • 三次握手                    │  │
│        ○                        │  │ • 四次挥手                    │  │
│                                │  └───────────────────────────────┘  │
│ [布局: ForceAtlas2 ▼] [重置]    │  (点击节点时显示)                   │
└────────────────────────────────┴─────────────────────────────────────┘
```

**实现策略**：

- 直接拷贝 LightRAG webui 的：
  - `src/features/GraphViewer.tsx`
  - `src/components/graph/*`（节点详情面板、布局控制、minimap 等）
  - `src/stores/graph.ts`
  - 依赖：`sigma` + `graphology` + `@react-sigma/*` + `@sigma/*`
- API 调用改为后端代理路由：
  - 标签列表：`GET /graph/label/list` | `GET /graph/label/popular` | `GET /graph/label/search?query=...`
  - 图数据：`GET /graphs?label=...&max_depth=...&max_nodes=...`
- 节点点击交互：右侧面板显示节点详情（label/type/degree/properties/关联实体）。
- 布局算法下拉：ForceAtlas2 / Circular / CirclePack / Noverlap / Random / Force。
- Minimap 默认开启。

### 6.4 项目配置

#### 列表页 `/teacher/projects`

```
┌──────────────────────────────────────────────────────────────────────┐
│ [+ 新建项目]                                                          │
├──────────────────────────────────────────────────────────────────────┤
│ 名称                状态         更新时间            操作              │
│ TCP 拥塞控制实验    [已发布]     2024-07-19 10:30   [编辑] [删除]    │
│ DNS 解析实践        [草稿]       2024-07-18 15:20   [编辑] [发布]    │
└──────────────────────────────────────────────────────────────────────┘
```

- `useEffect` 调 `GET /projects`，`@tanstack/react-table`（已在 LightRAG 依赖里）渲染表格。
- `[发布]` / `[取消发布]` 快捷按钮（`PATCH /projects/{id} {status: ...}`）。
- `[删除]` 用 `AlertDialog` 二次确认。

#### 编辑页 `/teacher/projects/new | /teacher/projects/:id/edit`

```
┌──────────────────────────────────────────────────────────────────────┐
│ [返回列表]                                                            │
├──────────────────────────────────────────────────────────────────────┤
│ 名称: [TCP 拥塞控制实验                                  ]           │
│ 状态: [草稿 ▼] (draft / published)                                    │
│                                                                       │
│ 项目背景 (Markdown):                          │ 实时预览:               │
│ ┌──────────────────────────────────────────┐ │ ┌────────────────────┐ │
│ │ ## 实验目标                              │ │ │ ## 实验目标         │ │
│ │ 理解 TCP 拥塞控制的...                   │ │ │ 理解 TCP 拥塞...    │ │
│ │                                          │ │ │                    │ │
│ │ ## 实验步骤                              │ │ │ ## 实验步骤         │ │
│ │ 1. ...                                   │ │ │ 1. ...              │ │
│ └──────────────────────────────────────────┘ │ └────────────────────┘ │
│ (textarea，支持 Markdown 语法)                │ (MarkdownRenderer 渲染) │
│                                                                       │
│                                          [取消]  [保存]              │
└──────────────────────────────────────────────────────────────────────┘
```

- 左右分栏，左侧 `textarea` + 字符计数，右侧 `MarkdownRenderer` 实时预览（debounce 300ms）。
- 表单校验：name 非空且 ≤200 字符，background_md 非空。
- 保存：新建 `POST /projects`，编辑 `PATCH /projects/{id}`。

## 7. 数据流 + 状态管理 + SSE 实现

### 7.1 数据获取模式（不用 TanStack Query）

```typescript
// lib/useAsync.ts
function useAsync<T>(fn: () => Promise<T>, deps: any[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    fn().then(d => setData(d)).catch(e => setError(e)).finally(() => setLoading(false));
    return () => ac.abort();
  }, deps);

  return { data, error, loading, refetch: () => {/* ... */} };
}
```

### 7.2 authStore（持久化）

```typescript
interface AuthState {
  isAuthenticated: boolean;
  username: string | null;
  role: 'student' | 'teacher' | null;
  mockToken: string | null;
  login: (username, role) => void;
  logout: () => void;
}
// persist to localStorage, key: 'tutoring-auth'
```

### 7.3 chatStore（不持久化）

```typescript
interface ChatState {
  currentSession: SessionOut | null;
  items: ChatItem[];  // ChatItem = MessageItem | QuestionItem
  streamStatus: 'idle' | 'streaming' | 'quiz_interrupted' | 'error';
  pendingQuiz: QuestionOut | null;
  streamingAgentContent: string;
  lastError: { message: string; code: string } | null;

  loadSession: (id: UUID) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  submitQuiz: (action: 'answer' | 'skip', answer?: string) => Promise<void>;
  resetStream: () => void;
}
```

### 7.4 SSE 解析（`lib/parseSSE.ts`，自写，不引库）

```typescript
// 后端帧格式：event: text\ndata: {...}\n\n
interface SSEEvent { event: string; data: any; }

async function* parseSSE(response: Response): AsyncGenerator<SSEEvent> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      const lines = frame.split('\n');
      const event = lines.find(l => l.startsWith('event: '))?.slice(7) || 'message';
      const dataLine = lines.find(l => l.startsWith('data: '))?.slice(6) || '{}';
      yield { event, data: JSON.parse(dataLine) };
    }
  }
}
```

### 7.5 流式请求实现（`api/chat.ts`）

```typescript
async function* streamMessage(
  sessionId: UUID, content: string, signal?: AbortSignal
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-User-Id': getUsername() },
    body: JSON.stringify({ content }),
    signal,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  yield* parseSSE(res);
}

// quiz/resume 同理
async function* resumeQuiz(
  sessionId: UUID, action: 'answer' | 'skip', answer: string | null, signal?: AbortSignal
): AsyncGenerator<SSEEvent> { /* ... */ }
```

**注意**：用 `fetch` 而非 `axios`，因为 axios 不原生支持 stream 读取。但 `X-User-Id` header 要手动加（与 axios 拦截器一致）。

### 7.6 sendMessage 完整流程

```typescript
async sendMessage(content: string) {
  // 乐观更新：立即把 user 消息塞进 items，记下引用以便失败回滚
  const userMsg: MessageItem = {
    type: 'message', role: 'user', content,
    created_at: new Date().toISOString()
  };
  set(state => ({
    items: [...state.items, userMsg],
    streamStatus: 'streaming',
    streamingAgentContent: '',
  }));

  const ac = new AbortController();
  set({ currentAbort: ac });

  try {
    for await (const ev of streamMessage(sessionId, content, ac.signal)) {
      switch (ev.event) {
        case 'text':
          set(state => ({ streamingAgentContent: state.streamingAgentContent + ev.data.content }));
          break;
        case 'quiz_interrupt':
          // 后端 quiz_interrupt 后会立即发 done 且不存 agent 消息到 DB
          // -> 丢弃累积的 streamingAgentContent，不落地为 MessageItem
          set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' });
          break;
        case 'done':
          // 仅当正常 streaming 结束时才落地 agent 消息（后端已存）
          // quiz_interrupted 状态下后端不存 agent 消息，前端也不存
          if (get().streamStatus === 'streaming') {
            const agentMsg: MessageItem = {
              type: 'message', role: 'agent', content: get().streamingAgentContent,
              created_at: new Date().toISOString()
            };
            set(state => ({
              items: [...state.items, agentMsg],
              streamStatus: 'idle',
              streamingAgentContent: '',
            }));
          } else if (get().streamStatus === 'quiz_interrupted') {
            // quiz 暂停，保留 quiz_interrupted 状态，清空累积内容
            set({ streamingAgentContent: '' });
          }
          break;
        case 'error':
          set({ streamStatus: 'error', lastError: ev.data });
          toast.error(ev.data.message);
          break;
      }
    }
    // 流正常结束：检测未收到 done 事件（连接意外断开）
    if (get().streamStatus === 'streaming') {
      set({ streamStatus: 'error', lastError: { message: '连接中断', code: 'STREAM_CLOSED' } });
      toast.error('连接中断');
      // 回滚乐观更新的 user 消息
      set(state => ({ items: state.items.filter(it => it !== userMsg) }));
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      set({ streamStatus: 'error', lastError: { message: String(e), code: 'NETWORK' } });
      toast.error('网络错误');
      // 回滚乐观更新的 user 消息
      set(state => ({ items: state.items.filter(it => it !== userMsg) }));
    }
  } finally {
    set({ currentAbort: null });
  }
}
```

**关键修正点**：

1. **quiz_interrupt 时不落地 agent 消息**：后端 `runtime.py` 在 quiz_interrupt 后 `return` 且不调 `_save_final_agent_message`，即 DB 不存这条 agent 消息。前端若落地会导致下次 `loadSession` 时丢失（items 被后端 messages 替换）。所以 `done` 事件处理要按当前状态分支：`streaming` 才落地，`quiz_interrupted` 不落地。
2. **失败回滚乐观更新**：网络错误或 SSE `error` 事件后，把乐观塞入的 `userMsg` 从 items 移除，避免脏数据。
3. **流意外断开检测**：`for await` 结束后如果 `streamStatus` 仍为 `streaming`（说明没收到 `done` 事件），视为连接中断，按错误处理并回滚。

### 7.7 submitQuiz 流程

```typescript
async submitQuiz(action: 'answer' | 'skip', answer?: string) {
  const quiz = get().pendingQuiz;
  if (!quiz) return;

  // 锁定题卡：UI 立即禁用，避免重复提交
  set({ streamStatus: 'streaming', streamingAgentContent: '' });

  try {
    for await (const ev of resumeQuiz(sessionId, action, answer ?? null)) {
      switch (ev.event) {
        case 'text':
          set(state => ({ streamingAgentContent: state.streamingAgentContent + ev.data.content }));
          break;
        case 'quiz_interrupt':
          // 单题流程理论上不再触发；兼容处理
          set({ pendingQuiz: ev.data, streamStatus: 'quiz_interrupted' });
          break;
        case 'done':
          if (get().streamStatus === 'streaming') {
            // 正常结束：后端 _save_final_agent_message 已存 agent 消息
            const qItem: QuestionItem = {
              type: 'question',
              question: {
                ...quiz,
                status: action === 'skip' ? 'skipped' : 'answered',
                user_answer: action === 'skip' ? null : answer,
              }
            };
            const agentMsg: MessageItem = {
              type: 'message', role: 'agent', content: get().streamingAgentContent,
              created_at: new Date().toISOString()
            };
            set(state => ({
              items: [...state.items, qItem, agentMsg],
              pendingQuiz: null,
              streamStatus: 'idle',
              streamingAgentContent: '',
            }));
          } else if (get().streamStatus === 'quiz_interrupted') {
            // 二次 interrupt：后端不存 agent 消息，前端也不存
            set({ streamingAgentContent: '' });
          }
          break;
        case 'error':
          // 恢复到 quiz_interrupted 让用户能重试
          set({ streamStatus: 'quiz_interrupted', lastError: ev.data });
          toast.error(ev.data.message);
          break;
      }
    }
    // 检测流意外断开
    if (get().streamStatus === 'streaming') {
      set({
        streamStatus: 'quiz_interrupted',
        lastError: { message: '连接中断', code: 'STREAM_CLOSED' }
      });
      toast.error('连接中断，请重新答题');
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      // 恢复到 quiz_interrupted 让用户能重试
      set({
        streamStatus: 'quiz_interrupted',
        lastError: { message: String(e), code: 'NETWORK' }
      });
      toast.error('网络错误，请重新答题');
    }
  }
}
```

**关键修正点**：

1. **失败恢复到 `quiz_interrupted`**：与 `sendMessage` 不同，`submitQuiz` 失败时**不回滚**题卡状态，而是恢复到 `quiz_interrupted` 让用户能重新选/答并重试。因为题目已经在 DB 里（`quiz_flow` 工具调 `upsert_pending_question` 已存），重试不会重复出题。
2. **done 事件按状态分支**：与 `sendMessage` 一致。二次 interrupt 时不落地 agent 消息（后端不存）。
3. **流意外断开检测**：与 `sendMessage` 一致。

### 7.8 loadSession（加载历史会话）

```typescript
async loadSession(id: UUID) {
  const [session, messages, questions] = await Promise.all([
    sessionsApi.get(id),
    sessionsApi.listMessages(id),
    sessionsApi.listQuestions(id),
  ]);
  const items = [
    ...messages.map(m => ({ type: 'message' as const, ...m })),
    ...questions.map(q => ({ type: 'question' as const, question: q })),
  ].sort((a, b) => +new Date(a.created_at) - +new Date(b.created_at));

  set({ currentSession: session, items, streamStatus: 'idle', pendingQuiz: null });
}
```

### 7.9 错误处理策略

| 场景 | 处理 |
|---|---|
| 网络层错误（fetch reject） | `streamStatus='error'`，`toast.error('网络错误')`，输入框恢复可输入，可重试 |
| SSE `error` 事件 | `streamStatus='error'`，`toast.error(data.message)`，记录 `lastError` |
| SSE 流意外断开（reader done 但没收到 done 事件） | 检测：`streamStatus='streaming'` 时流结束 -> 视为错误，toast 提示"连接中断" |
| 409 SESSION_INTERRUPTED | toast 提示"会话已暂停，请先答题"，UI 自动切到 `quiz_interrupted` 状态（重新拉 questions 找 pending） |
| 404 SESSION_NOT_FOUND | toast 提示并跳回 `/student/sessions` |
| 后端 5xx | 全局 axios 响应拦截器统一 toast，SSE 流则按上面错误事件处理 |

### 7.10 后端错误响应格式

```json
{ "detail": { "error": { "code": "...", "message": "..." } } }
```

axios 响应拦截器统一解析：

```typescript
apiClient.interceptors.response.use(
  res => res,
  err => {
    const detail = err.response?.data?.detail?.error;
    if (detail) {
      toast.error(`${detail.code}: ${detail.message}`);
    } else {
      toast.error(err.message);
    }
    return Promise.reject(err);
  }
);
```

## 8. 测试 + 构建 + 工程化

### 8.1 单元测试策略（最小化，YAGNI）

**不写前端单元测试**，聚焦功能交付。理由：

- 后端已有集成测试覆盖业务逻辑
- 前端组件交互复杂度高，单测 ROI 低
- 流式对话、SSE 解析这些核心逻辑用 E2E 验证更可靠

**保留**的验证手段：

1. `bun run lint`（ESLint + TypeScript 检查）作为提交前必跑
2. `bun run build`（Vite 生产构建）确保无类型错误
3. `bun run typecheck`（`tsc --noEmit`）独立类型检查
4. **`agent-browser` skill E2E 功能测试**（见 8.5）

### 8.2 工程配置

#### `package.json` 脚本

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "e2e": "echo '手动跑：调用 agent-browser skill 走验证清单'"
  }
}
```

#### `vite.config.ts`（dev 代理到后端）

```typescript
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': '/src' } },
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://localhost:8000',
      '/projects': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/documents': 'http://localhost:8000',
      '/graph': 'http://localhost:8000',
      '/graphs': 'http://localhost:8000',
    },
  },
});
```

> **注意**：SSE 流式请求走 `fetch` 直连 `/chat/*`，不走 axios。dev 下 vite proxy 会正确转发 SSE（vite 用 http-proxy 支持 streaming）。

#### `tailwind.config.js`

从 LightRAG webui 拷贝并裁剪：保留基础主题色（light/dark）、shadcn/ui 的 CSS 变量、动画；删除 LightRAG 专有的颜色 token。

#### `.env.development`

```
VITE_API_BASE=           # 空字符串，走 vite proxy
VITE_DEFAULT_ROLE=student
```

### 8.3 ESLint + TypeScript 配置

- ESLint：从 LightRAG webui 的 `eslint.config.js` 拷贝，保留 `@stylistic` + `react-hooks` + `react-refresh` 规则。
- TypeScript：`tsconfig.json` 严格模式，路径别名 `@/* -> src/*`。
- `@typescript-eslint/no-explicit-any` 允许（与 LightRAG 一致，便于适配）。

### 8.4 启动流程

```bash
# 1. 后端
cd backend && uv run uvicorn tutoring.main:app --reload --port 8000

# 2. 前端
cd frontend && bun install && bun run dev
# 打开 http://localhost:5173

# 3. 登录页输入任意用户名 + 任意密码，选学生或教师
```

### 8.5 E2E 功能验证（agent-browser skill）

在功能开发完成后，**使用 `agent-browser` skill** 做端到端功能验证。该 skill 是一个浏览器自动化 CLI，适合驱动运行中的 dev server（`http://localhost:5173`）做真实交互测试。

**执行时机**：所有功能开发完成、`bun run lint` + `bun run build` 通过后。

**执行方式**：调用 `skill` 工具加载 `agent-browser` skill，按下方验证清单驱动浏览器逐项验证，截图存档。

#### 学生端验证清单

1. **登录（学生）**：打开 `http://localhost:5173` -> 登录页 -> 输入用户名 `stu1` + 任意密码 + 选"学生" -> 点登录 -> 跳转 `/student/sessions`，左栏显示空状态或历史会话列表
2. **新建 free 会话**：点 `[+ 新建会话]` -> 选"自由学习" -> 点"开始会话" -> 跳转新会话详情页，会话标题栏显示 `[自由学习]` badge
3. **流式对话**：在输入框输入"什么是 TCP 三次握手？" -> 点发送 -> SSE 流式 token 增量渲染到 agent 气泡，输入框禁用，发送按钮变"生成中..." -> 流结束输入框恢复
4. **触发 quiz**：输入"考考我 TCP 三次握手" -> 发送 -> agent 回复后出现 `quiz_interrupt` -> 对话流末尾渲染题卡（含题干 + 选项 + [跳过] [提交] 按钮）
5. **提交 quiz**：选一个选项 -> 点"提交" -> 题卡锁定，显示 verdict 徽章（correct/partial/wrong）+ 你的答案 + 正确答案 + diagnosis + analysis -> agent 后续回复流式输出
6. **跳过 quiz**：再次触发 quiz -> 点"跳过" -> 题卡标记"已跳过"徽章 -> agent 续接回复
7. **新建 project 会话**：点 `[+ 新建会话]` -> 选"项目学习" -> 项目下拉显示已 published 项目列表 -> 选一个 -> 点"开始会话" -> 跳转新会话，标题栏显示 `[项目]` badge + 项目名
8. **历史会话详情**：点左栏某个历史会话 -> `loadSession` 并行拉取 messages + questions -> 按时间合并渲染 -> 题卡显示 answered/skipped 状态 + verdict 徽章
9. **删除会话**：点会话标题栏 `[删除会话]` -> AlertDialog 二次确认 -> 确认后跳回 `/student/sessions`，列表刷新
10. **流式中断恢复**：发送消息后立即关掉后端 -> 前端 toast 报错"网络错误" -> 输入框恢复可输入 -> 重启后端 -> 点"重试" -> 流式恢复正常
11. **角色切换器（dev）**：顶栏点角色切换器 -> 切到"教师" -> 跳转 `/teacher/knowledge-base`

#### 教师端验证清单

1. **登录（教师）**：登出 -> 登录页输入 `teacher1` + 任意密码 + 选"教师" -> 跳转 `/teacher/knowledge-base`
2. **上传文档**：点 `[上传文件]` -> 选 PDF/MD/TXT 文件 -> 列表出现新行，状态 `processing` -> 轮询 `pipeline_status` -> 状态变 `processed`
3. **插入文本**：点 `[插入文本]` -> 弹窗输入文本 -> 提交 -> 列表出现新行
4. **扫描**：点 `[扫描]` -> 触发 LightRAG 扫描 -> pipeline_status 更新
5. **删除文档**：点某行 `[删除]` -> 二次确认 -> 列表刷新
6. **知识图谱**：切到 `[知识图谱]` Tab -> 搜索标签（如 "TCP"）-> 点搜索结果 -> Sigma.js 渲染图（节点 + 边 + minimap）-> 点节点 -> 右侧面板显示节点详情 -> 切换布局算法（ForceAtlas2 -> Circular）-> 图重排
7. **项目列表**：切到 `[项目配置]` Tab -> 显示项目列表（名称 + 状态 + 更新时间 + 操作）
8. **新建项目**：点 `[+ 新建项目]` -> 编辑页 -> 输入名称 + Markdown 背景 -> 右侧实时预览 -> 状态选"草稿" -> 点"保存" -> 跳回列表，新项目出现
9. **发布项目**：列表点草稿项目的 `[发布]` -> 状态徽章变"已发布"
10. **编辑项目**：点 `[编辑]` -> 编辑页预填 -> 修改 -> 保存 -> 列表更新
11. **删除项目**：点 `[删除]` -> AlertDialog 确认 -> 列表刷新

**E2E 测试结果记录**：每项验证通过后截图存到 `docs/superpowers/e2e-screenshots/YYYY-MM-DD/`，未通过项记入问题清单。

### 8.6 实现顺序

1. **脚手架**：`bun create vite`、装依赖、配 vite/tailwind/tsconfig/eslint、跑通空页面
2. **共享层**：axios client + `X-User-Id` 拦截器、authStore、路由表、`RequireAuth`/`RoleRoute` 守卫、`LoginPage`（mock）
3. **API 层**：projects/sessions/documents/graph API 客户端 + 类型
4. **学生端骨架**：`StudentLayout` 两栏、`SessionList`、`NewSessionDialog`、`SessionDetail` 空壳
5. **学生端对话**：`ChatStream` + `ChatInput` + `MessageBubble` + `MarkdownRenderer`
6. **学生端 Quiz**：`QuizCard` + `submitQuiz` 流程
7. **学生端历史**：`loadSession` + messages/questions 合并
8. **教师端骨架**：`TeacherLayout` + Tab
9. **教师端知识库**：拷贝适配 `DocumentManager`
10. **教师端知识图谱**：拷贝适配 `GraphViewer`
11. **教师端项目配置**：列表 + 编辑器 + Markdown 预览
12. **联调**：手动跑学生端 + 教师端验证清单
13. **E2E**：调用 `agent-browser` skill 跑 8.5 节验证清单，截图存档，问题修复

## 9. 后端依赖确认

本设计假设后端 API 以下契约不变（已在 `backend/src/tutoring/` 各 router 中确认）：

- `POST /chat/sessions/{id}/messages`：SSE 事件 `text | quiz_interrupt | done | error`，`quiz_interrupt.data` 为 `{question_id, topic, q_type, stem, options}`
- `POST /chat/sessions/{id}/quiz/resume`：请求体 `{action: "answer"|"skip", answer?: string}`，SSE 同上
- `GET /sessions/{id}/messages`：返回 `MessageOut[]`
- `GET /sessions/{id}/questions`：返回 `QuestionOut[]`（含 `status/user_answer/verdict/diagnosis/analysis`）
- `GET /projects?status_filter=published`：返回已发布项目列表
- `/documents/*`、`/graph/*`、`/graphs`：透传 LightRAG API，前端按 LightRAG webui 的 api 层契约调用

如后端契约调整，需同步更新前端类型与 API 客户端。
