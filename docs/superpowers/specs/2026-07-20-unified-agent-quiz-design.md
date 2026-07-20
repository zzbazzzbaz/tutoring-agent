# 简化 Agent 出题/评估流程：主智能体一体化设计

## 背景

当前 `quiz_flow` 工具是一个"子智能体"，内部包含两次独立的 LLM 调用（出题 + 评估），与主智能体的对话上下文完全隔离。主智能体只收到字符串摘要，无法自然延续教学对话。

本设计将出题、评估全部收归主智能体，工具只做薄事：检索、HITL 暂停、DB 持久化。

## 目标

- 主智能体在自己推理中出题 + 评估，共享完整对话上下文
- AI 模块对后端唯一暴露 `build_agent() -> CompiledStateGraph`，内部封装工具构造
- 工具内部零 LLM 调用
- DB schema、SSE 事件、resume API、前端均零改动

## 非目标

- 不改 DB schema（verdict/diagnosis 列保留，仅不再填充）
- 不改 SSE 事件结构（quiz_interrupt / text / done / error）
- 不改 resume API（POST /chat/sessions/{id}/quiz/resume）
- 不改前端（QuizCard 已优雅处理 null verdict/diagnosis）

## 新的对话流

```
用户: 考考我TCP三次握手
-> 主智能体:
   1. [可选] 调用 search_knowledge("TCP三次握手") 检索知识
   2. 在推理中设计题目（考察理解不考死记）
   3. 调用 present_question(topic, q_type, stem, options, answer, analysis)
      ↳ 存 DB (pending) + interrupt(question) ← HITL 暂停
   ← 用户答题 (resume)
      ↳ 更新 DB (user_answer, answered) + 返回 {question_id, student_answer}
   4. 主智能体从 tool_call args 拿 correct_answer，对比 student_answer 自行评估
   5. 在回复中给学生反馈 + 继续苏格拉底式追问
```

## 工具设计

### search_knowledge（不变）

- **入参**：`query: str`
- **内部**：调 LightRAG `query(mode="mix", only_need_context=True)`
- **出参**：`str`（知识片段文本）

### present_question（新，替换 quiz_flow）

- **入参**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `topic` | `str` | 知识点名称，用于幂等键 + DB 索引列 |
| `q_type` | `Literal["single", "multi", "short"]` | 题型 |
| `stem` | `str` | 题干 |
| `options` | `list[str] \| None` | 选项，简答题为 None |
| `answer` | `str` | 正确答案 |
| `analysis` | `str` | 题目解析 |
| `config` | `RunnableConfig` | LangGraph 自动注入，取 thread_id |

- **内部行为**：
  1. 从 `config["configurable"]["thread_id"]` 取 `session_id`
  2. `upsert_pending_question(session_id, topic, q_type, stem, options, answer, analysis)` — 幂等写入，resume 时防重复出题
  3. `interrupt({question_id, topic, q_type, stem, options})` — 暂停，SSE 发 `quiz_interrupt` 事件
  4. [resume] `interrupt()` 返回 `{"action": "answer"|"skip", "answer": str|None}`
  5. 分支：
     - skip：`update_question(status="skipped")`，返回 `{"question_id": str, "action": "skipped"}`
     - answer：`update_question(user_answer, status="answered")`，返回 `{"question_id": str, "student_answer": str}`

- **出参**（ToolMessage 内容，主智能体可见）：

```python
# answer 分支
{"question_id": "uuid-string", "student_answer": "B"}

# skip 分支
{"question_id": "uuid-string", "action": "skipped"}
```

主智能体从自己的 tool_call args 拿 `correct_answer` / `analysis`，不需要工具回传。

## 删除的内容

| 文件 | 删除项 | 原因 |
|------|--------|------|
| `agent/tools.py` | `_search_for_quiz()` | 主智能体直接调 `search_knowledge` |
| `agent/tools.py` | `_generate_quiz()` | 主智能体在推理中出题，不再调独立 LLM |
| `agent/tools.py` | `_evaluate_answer()` | 主智能体在回复中评估，不再调独立 LLM |
| `agent/tools.py` | `quiz_flow` 工具 | 被 `present_question` 替换 |
| `agent/prompts.py` | `QUIZ_GENERATION_PROMPT` | 出题规则融入主 system prompt |
| `agent/prompts.py` | `EVALUATION_PROMPT` | 评估规则融入主 system prompt |
| `agent/schemas.py` | `EvaluationOutput` | 不再有结构化评估输出 |
| `agent/runtime.py` | 整个文件 | SSE 编排迁入 `chat/sse.py` |

## 修改详情

### `agent/prompts.py`

将出题要求 + 评估规则合并进 `_CORE_PRINCIPLES`，新增工具使用指引：

```
## 出题与评估流程
1. 判断时机：当学生说"考考我"/需要检验理解时，选择一个知识点出题
2. [可选] 先调 search_knowledge 检索相关知识作为出题素材
3. 在推理中设计题目：
   - 考察理解，不考死记硬背
   - 单选题 4 个选项；多选题 4-6 个选项；简答题无选项
   - 答案要明确：single 填选项完整文本；multi 填 "A,C,D"；short 填要点
   - analysis 说明考点和答案依据
4. 调用 present_question(topic, q_type, stem, options, answer, analysis)
5. 工具会暂停等待学生答题，学生提交后返回学生答案
6. 拿到学生答案后，对比你传入的正确答案，自行评估：
   - 单选：完全匹配 = correct，否则 = wrong
   - 多选：全对 = correct，漏选无错选 = partial，有错选 = wrong
   - 简答：按要点命中评分，全部命中 = correct，部分 = partial，偏离 = wrong
7. 在回复中给学生反馈（对错 + 错因 + 正确答案 + 解析），继续苏格拉底式追问
```

### `agent/factory.py`

`build_agent()` 吸收 `make_tools()` 调用：

```python
def build_agent(
    checkpointer: BaseCheckpointSaver,
    lightrag_client: LightRAGClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> CompiledStateGraph:
    tools = make_tools(
        lightrag_client=lightrag_client,
        db_session_factory=db_session_factory,
    )
    return create_agent(
        model=get_llm(),
        tools=tools,
        middleware=[main_agent_system_prompt],
        context_schema=AgentContext,
        checkpointer=checkpointer,
    )
```

### `agent/runtime.py` -> `chat/sse.py`

`stream_chat()` / `resume_quiz()` / `_save_final_agent_message()` / `_extract_text()` / `_sse()` 全部迁入 `chat/sse.py`。这些是后端传输 + DB 持久化关注点，不属于 AI 模块。

`chat/sse.py` 的 `send_message` / `resume_quiz_endpoint` 端点直接内联流式逻辑（或调用同文件的 helper 函数）。

### `main.py`

简化 lifespan 中的 agent 构造：

```python
# 原来
tools = make_tools(lightrag_client=lightrag_client, db_session_factory=db_session_factory)
app.state.agent = build_agent(checkpointer, tools)

# 现在
app.state.agent = build_agent(
    checkpointer=checkpointer,
    lightrag_client=lightrag_client,
    db_session_factory=db_session_factory,
)
```

### `agent/schemas.py`

- 保留 `QuizOutput`（作为 `present_question` 的 args schema）
- 删除 `EvaluationOutput`

### `agent/tools.py`

重写为 2 个薄工具：`search_knowledge`（不变）+ `present_question`（新）。删除所有 LLM 调用 helper。

## 不变的部分

- **DB schema**：Question 表结构不变。`verdict` / `diagnosis` 列保留但不再填充（前端已优雅处理 null）
- **SSE 事件**：`quiz_interrupt` / `text` / `done` / `error` 事件结构不变
- **Resume API**：`POST /chat/sessions/{id}/quiz/resume` 不变
- **前端**：`QuizCard.tsx`、`chat store`、`QuizInterruptData` 类型均不变（verdict/diagnosis 为 null 时条件渲染跳过）
- **`agent/llm.py`**：不变
- **`agent/prompts.py` 的 `AgentContext` + `main_agent_system_prompt` 中间件**：结构不变，prompt 内容更新

## 模块边界（改后）

```
agent/ (AI 模块，对后端只暴露 build_agent + AgentContext)
├── factory.py    # build_agent() — 唯一公开 API
├── tools.py      # make_tools() — 内部，build_agent 调用
├── prompts.py     # system prompt + AgentContext
├── schemas.py     # QuizOutput（tool args schema）
└── llm.py         # get_llm()

chat/ (后端模块，直接用 agent 对象)
├── sse.py         # 端点 + 流式编排 + DB 消息持久化（吸收 runtime.py）
├── service.py     # 会话校验 + build_agent_context
├── router.py      # Session/Message/Question REST 端点
└── schemas.py     # 请求/响应 schema
```

## 验证清单

- [ ] `present_question` 工具能正确 interrupt 并在 resume 时返回学生答案
- [ ] 主智能体在 resume 后的回复中包含评估（对错 + 错因）
- [ ] 幂等性：resume 时不重复出题
- [ ] skip 分支正确更新 status
- [ ] `search_knowledge` 仍正常工作
- [ ] SSE 事件结构不变（前端无需改）
- [ ] `GET /questions` 端点正常返回（verdict/diagnosis 为 null）
- [ ] `agent/runtime.py` 删除后，`chat/sse.py` 功能等价
