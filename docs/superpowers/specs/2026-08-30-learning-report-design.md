# 学习报告模块设计

日期：2026-08-30
状态：已确认

## 背景

领导演示后反馈：对话结束后**没有产出物**，教师看不到学生的过程。改进方向为：会话结束时自动生成学习报告，包含**答题记录与错题、对话过程时间线、薄弱点诊断与下一步建议**，教师端可查看。UI 视觉不做改动。

约束：现场真机演示、无期限、无需考虑安全性问题。

## 架构

报告生成放在 Agent Server（它是唯一能直接读 LangGraph 对话历史的地方）：

```
学生端点"结束会话" ──▶ API Server POST /sessions/{id}/end
                            │ 1. 会话标记 ended_at
                            │ 2. 回调 Agent Server /internal/report/generate
                            ▼
                       Agent Server reports 模块
                            │ 1. LangGraph SDK 读完整对话历史
                            │ 2. 通义千问 LLM 分析 → 结构化 JSON 报告
                            ▼
                       API Server 存 report 表
                            ▼
                   教师端/学生端查看报告
```

### 触发链路

1. 学生端会话侧栏新增"结束会话"按钮（语义：标记结束 + 生成报告，**不删除**会话）
2. `POST /sessions/{id}/end` → 置 `ended_at` → 回调 Agent Server 生成报告
3. 报告生成后状态回传，前端提示"报告已生成"，展示报告

## 报告内容（结构化 JSON）

LLM 分析完整对话历史后输出：

| 区块 | 内容 |
| --- | --- |
| **答题记录与错题** | 每次 `present_question` 出题 → 学生作答 → 对错判定 → 错题归纳 |
| **对话过程时间线** | 按时间顺序：学生提问 → Agent 引导追问 → 出题 → 作答 → 评估反馈 |
| **薄弱点诊断** | 学生在追问中暴露的理解误区/不完整知识点 |
| **下一步建议** | 针对薄弱点的具体学习建议 |

## 数据库变更

新表 `report`：

```
report
├── id            UUID PK
├── session_id    UUID FK → session.id（唯一，索引）
├── content       JSON（报告四区块内容）
├── created_at    timestamp
└── updated_at    timestamp
```

`session` 表新增字段：

- `ended_at` timestamp NULL：会话结束时间（未结束为 NULL）

## Agent Server 新增 `reports` 模块

| 端点 | 说明 |
| --- | --- |
| `POST /internal/report/generate` | body `{session_id, mode}` → 读 thread 历史 → LLM 生成 JSON 报告 → 返回 |

要点：
- 用 LangGraph SDK 按 thread_id（= session_id）读取完整消息历史
- 复用现有 LLM 配置（DashScope 通义千问）与系统 Prompt 风格
- 输出强约束为 JSON（答题记录、时间线、薄弱点、建议四区块），字段缺失时按空数组降级，不中断
- 若会话消息不足（如仅 1-2 轮），仍生成基础报告，标注"对话较短，评估有限"

## API Server 新增报告端点

| 端点 | 说明 |
| --- | --- |
| `POST /sessions/{id}/end` | 置 `ended_at` → 回调 Agent Server 生成报告 → 存库 → 返回报告摘要 |
| `GET /sessions/{id}/report` | 返回会话报告（含未生成时的状态） |
| `GET /students/{userId}/reports` | 教师端学生详情页：最近报告列表 |

## 前端改动

**学生端（`/student/chat`）**
- 会话侧栏操作新增"结束会话"按钮
- 结束后展示报告（弹窗或独立视图），可随时在会话列表查看历史报告

**教师端（`/teacher/manage/classes/[classId]/sessions/[sid]`）**
- 会话详情页新增"学习报告"区块：渲染时间线、答题记录与错题、薄弱点诊断、下一步建议

**教师端学生分析页（`/teacher/manage/analytics/students/[userId]`，可选）**
- 展示学生最近会话的学习报告列表

## 测试方案

| 层 | 测试 |
| --- | --- |
| Agent Server | `reports` 模块单测：mock LangGraph history + LLM，验证报告 JSON 四区块结构完整；短会话降级；LLM 失败降级 |
| API Server | `/end` 端点单测：置 ended_at + 触发回调 + 存库；`/report` 查询链路 |
| 端到端 | 本地全栈手动验证：对话几轮（含出题作答）→ 结束会话 → 报告生成 → 教师端查看 |

## 实施顺序

1. 数据库迁移（`report` 表 + `session.ended_at`）
2. Agent Server `reports` 模块（读历史 + LLM 生成 + 内部端点）
3. API Server 报告端点（end/report/reports）
4. 前端：学生端结束会话 + 报告展示，教师端报告查看
5. 测试与演示验证