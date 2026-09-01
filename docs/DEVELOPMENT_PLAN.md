# 开发计划：教师端产出物可见性（第一层：过程性查看）

## 项目目的

学生端已完成产出物（deliverable）的产出与落库（`session_progress.progress[stage_id].deliverable`），但教师端缺乏完整的产出物查看能力。本计划实现**第一层——过程性查看**：让教师能完整、清晰地查看学生产出物内容，而不只是截断文本。

## 背景与现状

### 数据现状（后端无需改动）
- 产出物已落库：`session_progress` 表，`progress[stage_id] = {status, deliverable, deliverable_done}`
- 已有接口：`GET /progress/sessions/{session_id}` → `{session_id, progress, updated_at}`（`frontend/src/lib/api/progress.ts` 的 `progressApi.get`）
- 已有项目接口：`projectsApi.get(projectId)` → 含 `mainline`（阶段标题、产出物标题）

### 前端现状（需要改动的点）
| 位置 | 现状 | 问题 |
|---|---|---|
| `StudentMainlineProgress.tsx`（学生分析页） | 产出物仅显示**截断 120 字**的纯文本 | 无法看完整内容 |
| `ReadOnlyChatView.tsx`（教师会话回看页） | 只渲染 human/ai 消息，**完全不展示产出物** | 教师回看对话时看不到产出物 |

### 已确认的产品决策
- 第一层只做"过程性查看"，**不做评审/评语/批量聚合**（第二层再做）
- 产出物展示采用**可展开卡片**（参照现有 `KnowledgeSearchCard` / `AnsweredQuizCard` 的卡片范式）
- 会话回看页采用**右侧面板**（与学生端学习主线面板的布局一致）
- 本层**不改后端、不改数据模型**（提交时间等评审元数据留到第二层）

## 开发任务

### Phase 1：可复用 `DeliverableCard` 组件

- [x] 新建 `frontend/src/components/projects/DeliverableCard.tsx`
  - [x] Props：`stageTitle`（阶段名）、`deliverableTitle`（产出物标题）、`content`（产出物文本）、`done`（boolean 是否达标）、可选 `projectName`
  - [x] 折叠态：产出物图标 + 标题 + 状态徽章（已达标=绿 / 待完成=琥珀）+ 摘要一行
  - [x] 展开态：用 `MarkdownText`（`@/components/chat/thread/markdown-text`）渲染完整内容，`framer-motion` 展开动画
  - [x] 样式对齐现有卡片（`border-ink/10 bg-paper-card rounded-lg` 等 design token）
- [x] 自检：组件独立渲染无依赖错误

### Phase 2：学生分析页接入 `DeliverableCard`

- [x] 修改 `frontend/src/components/projects/StudentMainlineProgress.tsx`
  - [x] 删除现有"产出物详情"区（`sp.deliverable.slice(0, 120)` 截断逻辑，约 line 202-225）
  - [x] 改为遍历有产出物且 `deliverable` 非空的阶段，渲染 `DeliverableCard` 列表（阶段名 + 产出物标题 + 完整内容 + 达标状态）
  - [x] 空态处理：有阶段配置产出物但学生未产出时，显示"未提交"占位（不渲染卡片）
- [x] 自检：学生分析页在"有产出物/无产出物"两种数据下均正常

### Phase 3：教师会话回看页接入产出物面板

- [x] 修改 `frontend/src/components/chat/ReadOnlyChatView.tsx`
  - [x] 在现有 `loadData` 中额外获取：`sessionsApi.get` 已有 → 新增 `progressApi.get(sessionId)` 与（project 会话时）`projectsApi.get(project_id)`
  - [x] 布局改为左右两栏：左侧为现有消息流，右侧新增"产出物"面板（宽度约 320px，仅 project 会话且有产出物阶段时显示）
  - [x] 右侧面板：面板头"产出物" + 每个产出物渲染 `DeliverableCard`；无产出物时显示空态文案
  - [x] 沿用学生端学习主线面板的样式语言（`bg-paper-card/60 backdrop-blur-sm border-l`）
- [x] 自检：自由会话不显示右侧面板；项目会话显示产出物卡片

### Phase 4：验证与回归

- [x] 前端 `npx tsc --noEmit` 通过
- [x] `npx next lint` 无新增 error（既有 warning 可接受）
- [x] 浏览器实测（agent-browser）：
  - [x] 学生分析页：有产出物的学生能看到完整卡片、可展开阅读全文
  - [x] 会话回看页：project 会话右侧出现产出物面板，自由会话不出现
  - [x] 折叠/展开交互正常，状态徽章颜色正确
- [x] 自检完成，等待人工评审 # 除非用户要求一次性完成整个实现

## 重要注意事项

- [ ] 不要过度设计：本层不做评审、不做批量聚合、不改后端
- [ ] 不要新增 TODO 占位代码
- [ ] 复用现有组件与样式范式（`KnowledgeSearchCard`、`LearningMainlinePanel`），不引入新 UI 库
- [ ] `progressApi` / `projectsApi` 已存在，禁止重复定义
- [ ] 产出物内容为长 Markdown 文本，注意展开区高度与滚动边界
- [ ] `ReadOnlyChatView` 布局改动需保持"返回按钮 + 只读标题"头部不变

## 技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 产出物展示形式 | 可展开卡片（`DeliverableCard`） | 与现有知识检索/答题卡片范式一致，长文本不挤压布局 |
| 会话回看页布局 | 左右两栏 + 右侧产出物面板 | 与学生端主线面板一致；"在对话旁"查看产出物 |
| 产出物时间戳 | 本层不展示 | `delivered_at` 数据尚不存在，属第二层评审元数据 |
| 后端改动 | 无 | 数据与接口已就绪，本层纯前端 |

## 测试策略

- 前端类型检查：`npx tsc --noEmit`
- 前端 lint：`npx next lint`
- 手动/浏览器验证两条主链路（学生分析页、会话回看页），覆盖有/无产出物两种数据态
- 不引入新测试框架；本项目前端无单测体系，以类型检查 + lint + 浏览器实测为准

## 调试协议

- 类型错误：修复根因（组件 props/类型对齐），不做 workaround
- 布局异常：检查 `ReadOnlyChatView` 外层 `h-full overflow-y-auto` 容器与两栏 flex 的嵌套关系
- 数据为空：确认 `progressApi.get` 返回结构（`{progress}` 可能为空对象）与 `mainline.stages` 的 `deliverable` 可能为 `null`

## QA 检查清单

- [ ] 需求全部实现（可展开完整产出物 + 会话回看页侧边产出物）
- [ ] 无类型错误、无新增 lint error
- [ ] 代码符合项目约定（组件位置、设计 token、中文文案）
- [ ] 复用而非重复造轮子（卡片范式、API 客户端）
- [ ] 空态与边界（无产出物、自由会话）处理正确
- [ ] 文档准确反映实现（本计划完成后按实际更新）
