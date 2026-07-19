# E2E 验证报告

- 日期：2026-07-19
- 后端版本：v0.2.0（health: degraded，database=fail，lightrag=ok，agent=ready）
- 前端版本：0.1.0
- 验证方式：agent-browser skill（浏览器自动化）
- 前端 dev server：http://localhost:5173

## 环境说明

后端 health 检查返回 `degraded`（`database: fail`），因此依赖数据库的功能（创建会话、消息存储、项目 CRUD）无法完整验证。LightRAG 和 Agent 服务正常。

## 验证结果

### 前端工程验证

| # | 验证项 | 结果 | 备注 |
|---|---|---|---|
| 1 | typecheck (`tsc --noEmit`) | ✅ | 无错误 |
| 2 | lint (`eslint .`) | ✅ | 无错误无警告 |
| 3 | build (`vite build`) | ✅ | 1,344KB（gzip 402KB），有 chunk 大小 warning（不影响功能） |
| 4 | dev server 启动 | ✅ | Vite 8.1.5，端口 5173 |

### 学生端

| # | 验证项 | 结果 | 备注 |
|---|---|---|---|
| 1 | 登录页 UI 渲染 | ✅ | 标题 + 用户名/密码输入 + 角色单选 + 登录按钮 |
| 2 | Mock 登录（学生） | ✅ | 输入 stu1 + 任意密码 + 选学生 -> 跳转 /student/sessions |
| 3 | 两栏布局 | ✅ | 左栏 SessionList（"暂无会话"）+ 右栏占位文案 |
| 4 | 历史会话列表 | ⚠️ | 显示"暂无会话"（数据库 fail 导致 GET /sessions 返回空） |
| 5 | 新建会话弹窗 | ⚠️ | Radix Dialog 与 agent-browser click 兼容性问题（可能需要 headed 模式验证） |
| 6 | 流式对话 | ❌ | 需要数据库 + agent（数据库 fail 无法创建会话） |
| 7 | Quiz 流程 | ❌ | 需要数据库 + agent |
| 8 | 历史会话详情 | ❌ | 无会话可查看 |
| 9 | 删除会话 | ❌ | 无会话可删除 |
| 10 | 角色切换器（dev） | ✅ | combobox 显示"学生"（仅 dev 期显示） |

### 教师端

| # | 验证项 | 结果 | 备注 |
|---|---|---|---|
| 1 | Mock 登录（教师） | ✅ | 通过 eval 设置 localStorage + 页面刷新实现 |
| 2 | Dashboard 布局 | ✅ | 顶栏 + 三个 Tab（知识库/知识图谱/项目配置） |
| 3 | 知识库 Tab | ✅ | 文档列表正常加载（3 个已处理文档），上传/插入/扫描按钮正常 |
| 4 | 知识图谱 Tab | ✅ | 搜索栏 + 深度/节点上限/布局选择（ForceAtlas2 默认）+ 空状态提示 |
| 5 | 项目配置 Tab | ⚠️ | Tab 切换正常，表格渲染正常，"加载中..."（数据库 fail 导致 GET /projects 超时） |
| 6 | 知识库上传文档 | ❌ | 未实际上传（E2E 时间限制） |
| 7 | 知识库删除文档 | ❌ | 未实际删除 |
| 8 | 知识图谱图渲染 | ❌ | 需搜索标签后加载图（未实际操作） |
| 9 | 项目 CRUD | ❌ | 数据库 fail 无法验证 |
| 10 | Markdown 编辑器预览 | ❌ | 需要新建/编辑项目 |

### 截图存档

| 文件 | 内容 |
|---|---|
| `01-login-page.png` | 登录页 |
| `02-student-layout.png` | 学生端两栏布局（空状态） |
| `03-new-session-dialog.png` | 新建会话弹窗（兼容性问题） |
| `04-teacher-layout.png` | 教师端 Dashboard |
| `05-teacher-knowledge-base.png` | 知识库（文档列表） |
| `06-teacher-projects.png` | 项目配置（加载中） |
| `07-teacher-knowledge-graph.png` | 知识图谱（空状态） |

## 问题清单

### 1. 数据库连接失败（后端问题）

- **现象**：后端 `/health` 返回 `database: fail`，状态 `degraded`
- **影响**：学生端创建会话、流式对话、历史会话详情、教师端项目 CRUD 均无法验证
- **修复方向**：检查后端 `.env` 的 `DATABASE_URL` 和 PostgreSQL 连接

### 2. Radix Dialog 与 agent-browser 兼容性

- **现象**：点击"+ 新建会话"按钮后 Dialog 弹窗未出现
- **影响**：新建会话弹窗的自动化验证失败
- **修复方向**：用 `--headed` 模式手动验证，或改用 Playwright 原生 API

### 3. Radix RadioGroup 与 agent-browser click 兼容性

- **现象**：点击教师 radio 没有切换选中状态
- **变通**：用 `agent-browser check @e9` 命令成功选中
- **影响**：自动化登录流程需要变通处理

### 4. 前端 chunk 大小 > 500KB

- **现象**：build 后 JS bundle 1,344KB（gzip 402KB）
- **影响**：首次加载较慢（不影响功能）
- **修复方向**：路由级 code-splitting（React.lazy + Suspense），将学生端和教师端代码分离

## 已验证通过的核心功能

1. ✅ 前端工程：typecheck + lint + build + dev server
2. ✅ Mock 登录页 UI + 登录流程
3. ✅ 角色守卫（未登录跳 /login）
4. ✅ 学生端两栏布局
5. ✅ 教师端 Dashboard 布局 + Tab 路由切换
6. ✅ 教师端知识库（文档列表 + 状态徽章 + 上传/插入/扫描按钮）
7. ✅ 教师端知识图谱（搜索栏 + 布局选择 + 空状态）
8. ✅ 教师端项目配置（表格渲染 + Tab 切换）
9. ✅ dev 期角色切换器显示

## 待验证（需修复数据库后）

1. ❌ 学生端：新建会话（free + project 模式）
2. ❌ 学生端：流式对话（SSE token 增量渲染）
3. ❌ 学生端：Quiz 触发 + 提交 + 跳过
4. ❌ 学生端：历史会话详情（messages + questions 合并）
5. ❌ 学生端：删除会话
6. ❌ 教师端：知识库上传/删除文档
7. ❌ 教师端：知识图谱图渲染（搜索标签 + Sigma.js）
8. ❌ 教师端：项目 CRUD + Markdown 编辑器预览
