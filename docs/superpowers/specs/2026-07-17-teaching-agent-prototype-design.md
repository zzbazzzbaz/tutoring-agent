# 教学 Agent 原型设计

| 项 | 内容 |
|---|---|
| 版本 | v2.1 |
| 日期 | 2026-07-17 |
| 状态 | 设计定稿 |
| 目标 | 从 0 到 1 搭建教学 Agent 原型，用 Jupyter Notebook 调试，验证教学效果 |

---

## 1. 概述

### 1.1 定位

教学 Agent 原型，核心验证四位一体教学法的效果：

1. **苏格拉底式追问引导** -- 不直接给答案，通过追问引导学生推导
2. **实时出题检验** -- 对话中 Agent 判断时机生成题目，学生作答后继续追问
3. **错题自动沉淀** -- 会话结束后 Agent 整理错题进入个人错题本
4. **跨会话画像** -- 学生画像跨会话记忆，实现个性化引导

### 1.2 关键约束

- **无前端**：Notebook 是唯一交互界面（ipywidgets 聊天 + 逐 cell 透明调试）
- **完整生产栈**：LangGraph + PostgreSQL/pgvector + AsyncPostgresSaver
- **uv 工程**，**LangChain/LangGraph 1.x**（严禁 0.3.x API）
- **首个实例**：《计算机网络》，先用示例知识库内容

### 1.3 已验证的技术栈

| 组件 | 版本 | 关键配置 |
|---|---|---|
| Python | 3.14 | |
| langchain | 1.3.14 | `create_agent` API（非旧版 `create_react_agent`） |
| langgraph | 1.2.9 | interrupt/resume + AsyncPostgresSaver |
| langchain-openai | 1.3.5 | OpenAI 兼容模式接入 DashScope |
| langgraph-checkpoint-postgres | 3.1.0 | AsyncPostgresSaver |
| SQLAlchemy | 2.0.51 | async ORM |
| pgvector | 0.5.0 | vector(1024) + HNSW |
| DashScope LLM | qwen3.5-flash | `extra_body={"enable_thinking": False}` |
| DashScope Embedding | text-embedding-v4 | `check_embedding_ctx_length=False`，维度 1024 |
| PostgreSQL | 17.10 + pgvector | 线上 101.35.223.219:15433 |

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    Jupyter Notebooks                  │
│  01_setup_and_rag   02_agent_sandbox  03_demo(widgets)│
└──────────────┬──────────────────────────────────────┘
               │ import
┌──────────────▼──────────────────────────────────────┐
│              teaching_agent/ (Python 包)              │
│                                                       │
│  config.py     pydantic-settings (.env 驱动)          │
│  models.py     SQLAlchemy async ORM + pgvector        │
│  db.py         async engine + session factory         │
│                                                       │
│  rag/                                                │
│    chunker.py     md 按标题层级切分                    │
│    embedder.py    text-embedding-v4 向量化            │
│    retriever.py   pgvector 检索 + 图遍历 (GraphRAG)    │
│    pipeline.py    入库流水线 (含LLM知识图谱分析)       │
│    graph.py       知识图谱操作 (节点/边/遍历)          │
│                                                       │
│  agents/                                             │
│    llm.py         ChatOpenAI/embedder 工厂             │
│    schemas.py     Pydantic 结构化输出 schema           │
│    prompts.py     所有 prompt (引导/出题/评估/整理/图谱)│
│    tools.py       共享工具实现 (search/quiz_flow/end)  │
│    free_agent.py  自由学习 Agent                      │
│    project_agent.py 项目学习 Agent                    │
│    review_agent.py 错题重练 Agent                     │
│                                                       │
│  knowledge/                                          │
│    sample_data.py 示例知识库内容                       │
│                                                       │
└──────────────┬──────────────────────────────────────┘
               │ asyncpg
┌──────────────▼──────────────────────────────────────┐
│  PostgreSQL + pgvector  (一个实例搞定全部)            │
│  业务表 + 向量索引 + 知识图谱 + LangGraph checkpoint  │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│  DashScope (OpenAI 兼容端点)                          │
│  qwen3.5-flash (对话) + text-embedding-v4 (向量化)   │
└─────────────────────────────────────────────────────┘
```

### 核心设计决策

1. **引导 Agent 为主智能体**（`create_agent`），出题/评估/错题整理封装为工具内部实现
2. **三种会话类型 = 三个显式 Agent 文件**，不用工厂模式
3. **interrupt 在工具内部**：`quiz_flow` 工具内调 `interrupt()` 等待学生答题
4. **GraphRAG**：pgvector 向量检索 + PostgreSQL 递归 CTE 图遍历，不需要图数据库
5. **知识图谱由 LLM 逐 chunk 分析构建**，不依赖 heading 自动生成
6. **对话历史双写**：Message 表管业务查询（历史查看/统计），checkpointer 管编排状态（interrupt/resume）

---

## 3. 数据模型

### 3.1 表清单

原型阶段 hardcode `user_id = "demo-student"`，不建 User 表。对话历史同时写 Message 表（业务查询）和 checkpointer（编排状态），两者职责不同。

| 实体 | 关键字段 | 说明 |
|---|---|---|
| Session | id, user_id, type, project_id?, mistake_id?, title, summary, status, last_active_at, started_at, ended_at | type: free/project/review; status: active/ended |
| Message | id, session_id, role, content, question_id?, created_at | role: user/agent; 索引 (session_id, created_at); 业务查询用，checkpointer 管编排 |
| Question | id, session_id, kp_id, q_type, stem, options, answer, analysis, source_chunk_ids | q_type: single/multi/short; session_id 非空 |
| AnswerRecord | id, question_id, user_id, session_id, user_answer, verdict, diagnosis | verdict: correct/partial/wrong; (question_id, user_id, session_id) 唯一 |
| MistakeItem | id, user_id, question_id?, kp_id, title, wrong_answer, correct_answer, diagnosis, source_chunk_ids, mastery_status, source_session_id | mastery_status: unmastered/reviewing/mastered |
| StudentProfile | id, user_id(unique), summary, weak_points(json), learning_style | weak_points: `[{kp_id, score, misconception}]` |
| Project | id, name, background_md, status | status: draft/published/archived |
| KBDocument | id, scope, project_id?, filename, status, chunk_count | scope: course/project; status: processing/ready/failed |
| Chunk | id, document_id, content, heading_path, chunk_index, embedding, scope, project_id? | embedding: vector(1024); HNSW 索引 |
| KnowledgePoint | id, name(unique), description | 图节点；LLM 逐 chunk 识别，非 heading 自动生成 |
| KnowledgeEdge | id, source_id, target_id, relation_type | relation_type: part_of/prerequisite/related/contrast; 图边 |
| ChunkKnowledgePoint | chunk_id, kp_id | N:N 关联表；一个 chunk 可关联多个知识点 |

通用约定：时间字段 timestamptz；LangGraph checkpoint 表由 AsyncPostgresSaver.setup() 自建。

### 3.2 知识图谱结构

```
KnowledgePoint (节点)              Chunk (内容 + embedding)
  "TCP三次握手"                     "客户端发送SYN..."
  "TCP四次挥手"                     "主动方发送FIN..."
       │                                  │
       │         N:N (ChunkKnowledgePoint)│
       └──────────────────────────────────┘
       
KnowledgeEdge (边)
  "TCP协议基础" --prerequisite--> "TCP三次握手"
  "TCP三次握手" --related--> "TCP四次挥手"
  "TCP三次握手" --contrast--> "UDP通信"
  "三次握手" --part_of--> "TCP连接管理"
```

### 3.3 向量索引

- Chunk.embedding: `vector(1024)`，HNSW 索引
- 距离函数：cosine（`<=>`，0=完全相同）
- 索引列：(scope, project_id) 用于作用域过滤

---

## 4. RAG 流水线

### 4.1 入库流程

```
md 文件 -> 校验(.md/UTF-8/≤5MB) 
-> 按标题层级切分 Chunk (保留 heading_path)
-> text-embedding-v4 向量化 -> 写入 pgvector
-> 逐 chunk LLM 分析:
   ├─ 识别知识点 (新/已有，复用已有避免重名)
   ├─ 建立 chunk-KP 关联 (ChunkKnowledgePoint)
   └─ 建议知识点间边 (KnowledgeEdge，去重合并)
```

### 4.2 切分策略

- md 按标题层级切分，每个 chunk 保留完整标题路径（heading_path）
- 单 chunk 超 ~500 tokens 时二次切分，重叠 ~50 tokens
- heading_path 仍存在 chunk 上作为元数据，但不用于自动生成 KnowledgePoint

### 4.3 知识图谱 LLM 分析（逐 chunk）

每个 chunk 独立做一次 LLM 调用，输入 chunk 内容 + 当前已有 KP 列表，输出知识点 + 边建议：

```python
class ChunkAnalysis(BaseModel):
    knowledge_points: list[KPSuggestion]
    edges: list[EdgeSuggestion]

class KPSuggestion(BaseModel):
    name: str           # 知识点名称
    is_new: bool        # True=新知识点, False=已有(复用)
    description: str    # 简短描述

class EdgeSuggestion(BaseModel):
    source: str         # 源知识点名称
    target: str         # 目标知识点名称
    relation_type: str  # part_of / prerequisite / related / contrast
```

边类型业务含义：

| 边类型 | 业务含义 | 教学用途 |
|---|---|---|
| part_of | A 是 B 的子主题 | 知识层级组织 |
| prerequisite | 学 A 之前必须先学 B | 学生卡住时回溯查前置 |
| related | A 和 B 概念相关 | 扩展检索上下文 |
| contrast | A 和 B 容易混淆 | 答错时主动出对比题 |

### 4.4 GraphRAG 检索策略

**五步检索流程**：

```
Step 1: 向量检索
  -> query 向量 -> top-5 chunk（按 cosine 距离）
  -> 距离 > 0.5 的过滤掉

Step 2: 提取入口知识点
  -> 从 top-5 chunk 的 ChunkKnowledgePoint (N:N) 拿到 KP 列表

Step 3: 图遍历（1 跳，不做多跳避免噪声）
  -> 从入口 KP 出发，沿 KnowledgeEdge 找相邻 KP
  -> 边类型优先级：prerequisite > contrast > related > part_of
  -> 取相邻 KP 关联的 chunk

Step 4: 合并排序
  -> 向量结果：按距离排序
  -> 图扩展结果：按边优先级 + 距离排序
  -> 去重，总计最多 10 个 chunk
  -> 每个 chunk 标注来源："vector" 或 "graph:{edge_type}:{kp_name}"

Step 5: 返回给 Agent
  -> 格式化：content + heading_path + source + distance
```

**review 会话特殊处理**：
- Step 0: 错题的 source_chunk_ids 直接并入候选
- Step 3: 图遍历起点额外包含错题的 kp_id

**SQL 实现**（1 跳图遍历 + 向量检索合并）：

```sql
WITH vector_results AS (
    SELECT c.id, c.content, c.heading_path, c.embedding <=> $1 AS dist
    FROM chunk c
    WHERE c.scope = $2
    ORDER BY c.embedding <=> $1
    LIMIT 5
),
entry_kps AS (
    SELECT DISTINCT ck.kp_id
    FROM chunk_kp ck
    WHERE ck.chunk_id IN (SELECT id FROM vector_results)
),
related_kps AS (
    SELECT target_id AS kp_id, relation_type
    FROM knowledge_edge
    WHERE source_id IN (SELECT kp_id FROM entry_kps)
    UNION
    SELECT source_id AS kp_id, relation_type
    FROM knowledge_edge
    WHERE target_id IN (SELECT kp_id FROM entry_kps)
),
graph_chunks AS (
    SELECT DISTINCT c.id, c.content, c.heading_path,
           c.embedding <=> $1 AS dist, rk.relation_type
    FROM chunk c
    JOIN chunk_kp ck ON c.id = ck.chunk_id
    JOIN related_kps rk ON ck.kp_id = rk.kp_id
    WHERE c.id NOT IN (SELECT id FROM vector_results)
    ORDER BY c.embedding <=> $1
    LIMIT 5
)
SELECT id, content, heading_path, dist, 'vector' AS source, NULL AS edge_type
FROM vector_results
UNION ALL
SELECT id, content, heading_path, dist, 'graph' AS source, edge_type
FROM graph_chunks
ORDER BY dist;
```

| 会话类型 | 检索范围 | 图遍历起点 |
|---|---|---|
| free | 课程级 | 向量检索命中的 KP |
| project | 课程级 + 项目级（项目优先） | 向量检索命中的 KP |
| review | 课程级 + 错题 source_chunk_ids | 向量检索命中的 KP + 错题的 kp_id |

- 距离阈值：可配置（初始值 0.5）
- query 构造：引导 Agent 生成检索词（含指代消解）
- 空检索兜底：返回"该问题超出当前课程知识库范围"

### 4.5 示例知识库内容

- TCP 三次握手与四次挥手
- UDP 协议特点
- HTTP 请求/响应结构
- 拥塞控制机制

---

## 5. Agent 架构

### 5.1 架构模式

引导 Agent 为主智能体（`create_agent`），出题/评估/错题整理封装为工具内部实现。

### 5.2 三个显式 Agent 文件（不用工厂）

```python
# agents/free_agent.py
def create_free_agent(checkpointer):
    """自由学习 Agent"""
    system_prompt = GUIDANCE_PROMPT.format(
        course_name=settings.COURSE_NAME,
        session_context="学生正在进行自由学习，围绕课程知识自由探索。",
        student_profile=await get_profile(),
    )
    tools = [
        make_search_tool("free", {}),
        make_quiz_tool("free", {}),
        make_end_session_tool("free", {}),
    ]
    return create_agent(
        model=get_llm(), tools=tools,
        system_prompt=system_prompt, checkpointer=checkpointer,
        name="free_agent",
    )

# agents/project_agent.py
def create_project_agent(project, checkpointer):
    """项目学习 Agent"""
    system_prompt = GUIDANCE_PROMPT.format(
        course_name=settings.COURSE_NAME,
        session_context=f"学生正在学习项目：{project.name}。\n项目背景：{project.background_md}\n以项目背景为情境展开追问。",
        student_profile=await get_profile(),
    )
    tools = [
        make_search_tool("project", {"project_id": project.id}),
        make_quiz_tool("project", {"project_id": project.id}),
        make_end_session_tool("project", {"project_id": project.id}),
    ]
    return create_agent(..., name="project_agent")

# agents/review_agent.py
def create_review_agent(mistake, checkpointer):
    """错题重练 Agent"""
    system_prompt = GUIDANCE_PROMPT.format(
        course_name=settings.COURSE_NAME,
        session_context=f"学生正在重练错题。\n知识点：{mistake.kp_name}\n原题：{mistake.title}\n错误答案：{mistake.wrong_answer}\n错因：{mistake.diagnosis}\n围绕这个知识点追问，出变式题（同知识点不同考法）。",
        student_profile=await get_profile(),
    )
    tools = [
        make_search_tool("review", {"mistake_data": mistake}),
        make_quiz_tool("review", {"mistake_data": mistake}),
        make_end_session_tool("review", {"mistake_id": mistake.id, "mistake_data": mistake}),
    ]
    return create_agent(..., name="review_agent")
```

### 5.3 工具设计

#### search_knowledge_base（scope 绑定在闭包中，含 GraphRAG）

```python
def make_search_tool(session_type, session_context):
    @tool
    async def search_knowledge_base(query: str) -> str:
        """检索课程知识库，返回相关知识片段"""
        # 1. 向量检索
        chunks = await vector_retrieve(query, session_type, session_context)
        # 2. GraphRAG: 从 chunk 的 KP 图遍历扩展
        expanded = await graph_expand(chunks)
        all_chunks = merge_and_dedupe(chunks, expanded)
        if not all_chunks:
            return "未检索到相关内容，该问题可能超出当前课程知识库范围"
        return format_chunks(all_chunks)
    return search_knowledge_base
```

#### quiz_flow（出题 + interrupt + 评估三合一）

```python
def make_quiz_tool(session_type, session_context):
    @tool
    async def quiz_flow(topic: str) -> str:
        """出一道题并等待学生作答，返回评估结果"""
        # 1. 出题Agent (with_structured_output)
        quiz = await generate_quiz(topic, session_type, session_context)
        # 2. 写入Question表
        question = await save_question(quiz)
        # 3. interrupt -- agent挂起
        student_answer = interrupt({
            "question_id": question.id, "q_type": quiz.q_type,
            "stem": quiz.stem, "options": quiz.options,
        })
        # 4. 跳过处理
        if student_answer.get("action") == "skip":
            return "学生跳过了本题"
        # 5. 评估Agent (with_structured_output)
        result = await evaluate_answer(question, student_answer["answer"])
        # 6. 写入AnswerRecord
        await save_answer_record(question, student_answer["answer"], result)
        # 7. 返回给引导Agent
        return f"判定: {result.verdict}\n错因: {result.diagnosis}\n正确答案: {result.correct_answer}"
    return quiz_flow
```

#### end_session（错题整理）

```python
def make_end_session_tool(session_type, session_context):
    @tool
    async def end_session() -> str:
        """结束会话，整理错题"""
        result = await consolidate_session()  # with_structured_output
        await save_mistakes(result.mistakes)
        await update_profile(result.profile_summary, result.weak_points)
        if session_type == "review":
            await update_mistake_mastery(session_context["mistake_id"], result)
        await update_session_title_summary(result.title, result.summary)
        return f"会话已结束。{result.summary}"
    return end_session
```

### 5.4 结构化输出 schema

```python
# 出题Agent
class QuizOutput(BaseModel):
    q_type: str; stem: str; options: list[str]
    answer: str; analysis: str
    kp_name: str; source_chunk_ids: list[str]

# 评估Agent
class EvaluationOutput(BaseModel):
    verdict: str; diagnosis: str; correct_answer: str
    analysis: str; follow_up_hint: str

# 错题整理Agent
class ConsolidationOutput(BaseModel):
    title: str; summary: str
    mistakes: list[MistakeExtract]
    profile_summary: str; weak_points: list[str]

class MistakeExtract(BaseModel):
    question_id: str | None; kp_name: str; title: str
    wrong_answer: str; correct_answer: str; diagnosis: str
    source_chunk_ids: list[str]
```

### 5.5 评分规则

- **单选**：完全匹配 = correct，否则 = wrong
- **多选**：全对 = correct，漏选无错选 = partial，有错选 = wrong
- **简答**：按要点命中评分，全部命中 = correct，部分命中 = partial，偏离 = wrong

---

## 6. Prompt 设计

Prompt 是教学效果的核心。所有 prompt 集中在 `agents/prompts.py`。

### 6.1 引导 Agent system prompt

```
你是一位苏格拉底式教学助手，课程是《{course_name}》。

## 核心原则
1. 绝不直接给出答案。通过提问引导学生自己推导出结论。
2. 当学生提问时，先调用 search_knowledge_base 检索相关知识，再基于检索内容设计追问。
3. 如果检索结果为空，告诉学生"这个问题可能超出当前课程知识库范围"，引导回课程内容。
4. 根据学生的回答判断理解程度：
   - 理解有误 -> 针对性追问，暴露矛盾
   - 理解部分 -> 追问未覆盖的部分
   - 理解到位 -> 可以调用 quiz_flow 出题检验
5. 学生说"考考我"/"出题"/"测验"时，调用 quiz_flow 出题。
6. 每次追问保持上下文连贯，不要突兀跳转话题。

## 学生画像
{student_profile}

## 当前会话
{session_context}

## 可用工具
- search_knowledge_base(query): 检索课程知识库，返回相关知识片段
- quiz_flow(topic): 出一道题并等待学生作答，返回评估结果
- end_session(): 结束会话，整理错题本和更新画像
```

### 6.2 出题 Agent prompt

```
你是一位出题专家，课程是《{course_name}》。

## 任务
根据以下信息出一道题：
- 当前话题：{topic}
- 对话上下文：{conversation_context}
- 知识库片段：{retrieved_chunks}
- 学生薄弱点：{weak_points}
{review_context}

## 出题要求
1. 题目考察理解，不考死记硬背
2. 单选题4个选项；多选题4-6个选项；简答题无选项
3. 知识点从以下候选中选择：{available_kps}
4. 简答题的 answer 写为要点列表（用于要点命中评分）
{variant_requirement}
```

review_context（仅错题重练）：`原题：{original_question}\n出变式题：同知识点，不同考法、不同角度。`

### 6.3 评估 Agent prompt

```
你是一位阅卷专家。

## 任务
评判学生的答案：
题目：{question_stem}
题型：{q_type}
正确答案：{correct_answer}
学生答案：{student_answer}
知识点：{kp_name}
知识库片段（评判依据）：{retrieved_chunks}

## 评分规则
- 单选：完全匹配 = correct，否则 = wrong
- 多选：全对 = correct，漏选无错选 = partial，有错选 = wrong
- 简答：按要点命中评分
  全部要点命中 = correct，部分命中 = partial，偏离 = wrong
  必须输出评分依据（命中/缺失了哪些要点）

## 输出
- verdict: correct / partial / wrong
- diagnosis: 错因诊断（答对时为空）
- correct_answer: 正确答案（反馈给学生）
- analysis: 解析说明
- follow_up_hint: 后续追问方向
```

### 6.4 错题整理 Agent prompt

```
你是一位教学分析专家。

## 任务
回顾本次学习会话的全部对话和作答记录，完成以下工作：

## 会话记录
{full_conversation}
{answer_records}

## 当前学生画像（旧值）
{old_profile_summary}
{old_weak_points}

## 需要输出
1. title: 会话标题（简洁，如"TCP三次握手学习"）
2. summary: 会话摘要（学习内容、学生表现、薄弱点）
3. mistakes: 所有答错和部分对的题目，提炼为错题
   - 关联 question_id（如有）
   - 知识点、题干摘要、错误答案、正确答案、错因
4. profile_summary: 更新后的画像文本（增量更新，保留旧信息）
5. weak_points: 更新后的薄弱知识点列表
```

### 6.5 知识图谱分析 prompt（入库时逐 chunk）

```
你是一位知识图谱构建专家。

## 任务
分析以下知识片段，提取知识点和知识点之间的关系。

## 知识片段
内容：{chunk_content}
标题路径：{heading_path}

## 已有知识点列表（优先复用，避免重名）
{existing_kps}

## 需要输出
1. knowledge_points: 这个片段涉及的知识点
   - 优先复用已有知识点（is_new=false）
   - 确需新增才创建（is_new=true）
   - 每个知识点给简短描述
2. edges: 这些知识点之间的关系
   - part_of: A是B的子主题
   - prerequisite: 学A之前必须先学B（方向：source是target的前置）
   - related: A和B概念相关
   - contrast: A和B容易混淆
```

### 6.6 统一结构化调用

```python
async def structured_call(llm, schema, prompt, max_retries=2):
    """with_structured_output + 校验 + 修复重试（指数退避）"""
    structured = llm.with_structured_output(schema, method="function_calling")
    for i in range(max_retries + 1):
        try:
            return await structured.ainvoke(prompt)
        except Exception:
            if i == max_retries: raise
            await asyncio.sleep(2 ** i)
```

降级行为：
- 出题Agent失败 -> quiz_flow 返回"出题失败，继续对话"
- 评估Agent失败 -> 返回"评判异常，请重新提交"
- 错题整理Agent失败 -> 记录日志，提示"本次未整理错题"

### 6.7 LLM 配置

```python
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="qwen3.5-flash",
        api_key=settings.DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0.7,
        extra_body={"enable_thinking": False},
    )

def get_embedder() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model="text-embedding-v4",
        api_key=settings.DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        check_embedding_ctx_length=False,
    )
```

---

## 7. 对话流转与 interrupt 机制

### 落库边界

- **Message 表**：每次 `ainvoke` 前后写入用户消息和 Agent 回复（业务查询用）
- **Question / AnswerRecord**：在 quiz_flow 工具内即时落库
- **MistakeItem / StudentProfile**：在 end_session 工具内落库
- **checkpointer**：管 interrupt/resume 编排状态，不依赖它做业务查询

### 对话流转

```
学生发消息
  -> 写入 Message 表（user 消息）
  -> agent.ainvoke({"messages": [user_msg]}, config={"thread_id": session_id})
  -> Agent自主决策：search_knowledge_base / 直接追问 / quiz_flow / end_session
  -> 写入 Message 表（agent 回复）
  -> 如果quiz_flow触发interrupt -> 返回quiz事件
  -> 否则返回文本回复

学生提交答案
  -> agent.ainvoke(Command(resume=answer), config={"thread_id": session_id})
  -> quiz_flow恢复：评估Agent判分 -> 返回结果给Agent
  -> 写入 Message 表（agent 回复）
  -> Agent生成后续追问

学生结束会话
  -> Agent调用end_session -> 错题整理 -> 返回摘要
  -> 写入 Message 表（结束消息）
```

事件提取：
```python
state = await agent.aget_state(config)
if state.next:  # 被 interrupt 了
    quiz_data = state.tasks[0].interrupt.value
    events = [{"type": "quiz", "payload": quiz_data}]
else:
    reply = result["messages"][-1].content
    events = [{"type": "text", "payload": {"content": reply}}]
```

checkpointer：AsyncPostgresSaver，`thread_id = session_id`。checkpoint 保证 interrupt 之前的工具调用不重复执行。

---

## 8. 错题沉淀与去重规则

### 8.1 去重合并

1. question_id 已存在 -> 更新原记录，掌握状态重置 unmastered
2. 无 question_id -> 按 kp_id + 题干相似度（阈值 0.9）判断重复
3. 否则新建 MistakeItem

### 8.2 掌握状态迁移

| 触发 | 迁移 |
|---|---|
| 错题创建 | -> unmastered |
| 发起重练会话 | -> reviewing |
| 重练变式题全部答对 | -> mastered |
| 重练变式题答错 | 保持 reviewing |
| mastered 后同知识点再答错 | 回退 unmastered |

---

## 9. Notebook 结构

### 9.1 `01_setup_and_rag.ipynb` -- 建库 + 知识库入库 + 检索验证

| Cell | 内容 | 调试关注点 |
|---|---|---|
| 1 | 连接 PostgreSQL，create_all() 建表 | 连接成功 |
| 2 | 写入示例知识库（4篇 md） | 内容正确 |
| 3 | 调用切分器，查看切分结果 | heading_path、chunk 内容、token 数 |
| 4 | 调用 embedder 向量化，写入 pgvector | 维度 1024 |
| 5 | 逐 chunk LLM 知识图谱分析，查看 KP 和边 | KP 识别质量、边建议合理性 |
| 6 | 查看知识图谱全貌（节点+边） | 图结构完整 |
| 7 | 向量检索测试 -- 不同 query 的 top-5 | 相似度分数、阈值过滤 |
| 8 | GraphRAG 检索测试 -- 五步流程验证 | 向量+图遍历合并效果、来源标注 |
| 9 | GraphRAG 边类型优先级测试 | prerequisite/contrast/related 扩展效果 |
| 10 | 空检索兜底测试 | 返回兜底提示 |

### 9.2 `02_agent_sandbox.ipynb` -- 逐个工具/Agent 单独调试

| Cell | 内容 | 调试关注点 |
|---|---|---|
| 1 | 初始化 LLM、DB、检索器 | |
| 2 | 测试 search_knowledge_base 工具 | 检索 + 图遍历相关性 |
| 3 | 测试出题Agent（with_structured_output） | 题目质量、知识点标注 |
| 4 | 测试评估Agent | 判分准确性 |
| 5 | 测试错题整理Agent | 错题提炼、画像更新 |
| 6 | 测试 quiz_flow 完整流程 | interrupt/resume 机制 |
| 7 | 测试 create_agent 完整流程 | Agent 工具调用决策过程 |

### 9.3 `03_interactive_demo.ipynb` -- ipywidgets 交互式完整 demo

界面：对话区域 + 答题卡弹层 + "考考我"/"结束会话"按钮 + 消息输入 + 侧边栏（工具调用日志 + 画像状态）

---

## 10. 项目结构

```
教学Agent/
├── pyproject.toml
├── .env / .env.example
├── .gitignore
├── verify_stack.py             # 全链路验证脚本（已完成）
├── docs/superpowers/specs/
│   └── 2026-07-17-teaching-agent-prototype-design.md
├── teaching_agent/
│   ├── __init__.py
│   ├── config.py               # pydantic-settings
│   ├── models.py               # SQLAlchemy async ORM
│   ├── db.py                   # async engine + session factory
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── chunker.py          # md 切分
│   │   ├── embedder.py         # 向量化
│   │   ├── retriever.py        # pgvector 检索 + GraphRAG
│   │   ├── pipeline.py         # 入库流水线（含LLM图谱分析）
│   │   └── graph.py            # 知识图谱操作（节点/边/遍历）
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── llm.py              # LLM/embedder 工厂
│   │   ├── schemas.py          # Pydantic 结构化输出 schema
│   │   ├── prompts.py          # 所有 prompt
│   │   ├── tools.py            # 共享工具实现
│   │   ├── free_agent.py       # 自由学习 Agent
│   │   ├── project_agent.py    # 项目学习 Agent
│   │   └── review_agent.py     # 错题重练 Agent
│   └── knowledge/
│       ├── __init__.py
│       └── sample_data.py      # 示例知识库内容
└── notebooks/
    ├── 01_setup_and_rag.ipynb
    ├── 02_agent_sandbox.ipynb
    └── 03_interactive_demo.ipynb
```

---

## 11. 配置

### .env

```
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.5-flash
EMBEDDING_MODEL=text-embedding-v4
DATABASE_URL=postgresql://root:guoqitong123456@101.35.223.219:15433/root
COURSE_NAME=计算机网络
COURSE_INTRO=本课程涵盖TCP/IP协议族、HTTP协议、网络拥塞控制等核心内容
TEACHING_STYLE=苏格拉底式追问，不直接给答案，引导学生自己推导
```

### 依赖（pyproject.toml）

- langchain >= 1.3
- langgraph >= 1.2
- langgraph-checkpoint-postgres >= 3.1
- langchain-openai >= 1.3
- sqlalchemy >= 2.0
- asyncpg, pgvector, greenlet
- pydantic-settings
- jupyter, ipywidgets
