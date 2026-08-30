# 知识检索可视化设计(引用卡片 + 知识图谱)

日期:2026-08-31
状态:已确认

## 背景

`search_knowledge` 工具调用 LightRAG 混合检索(知识图谱实体/关系 + 向量 RAG),当前只返回纯文本,前端默认隐藏 tool 消息,学生看不到检索内容。

## 设计

### 后端 `services/agent_server`

1. **`infrastructure/lightrag.py`**:`search()` 返回结构化 dict:
   ```json
   { "query": "...", "response": "上下文文本",
     "chunks": [{content, score, file_path}],
     "entities": [{entity_name, entity_type, description}],
     "relations": [{src_id, tgt_id, description}] }
   ```
   从 `/query` 响应的 `references` 提取并防御性解析(兼容不同结构)。
2. **`tools/knowledge.py`**:`search_knowledge` 返回 `json.dumps(结构化)`,LLM 照常可读;失败返回 `{"query": ..., "error": "..."}` 结构。

### 前端 `frontend`

3. **新组件 `components/chat/thread/messages/knowledge-search-card.tsx`**(与答题卡风格统一):
   - 折叠态:徽章「检索知识库 · 关键词「XX」· N 片段 · M 实体」
   - 展开态:两个 Tab——「引用」chunk 列表(摘要+来源)/「知识图谱」sigma 力导向图(实体节点、关系边,拖拽缩放,点击实体高亮显示描述)
   - 空态:未检索到相关知识;失败:降级徽章
4. **`ai.tsx`**:`message.name === "search_knowledge"` 的 tool 消息渲染该卡片(不受 hideToolCalls 影响)
5. 图谱基于项目已装的 @react-sigma/core + graphology,轻量实现(节点 <50,无完整控件)

## 数据流

学生提问 → LLM 调用 search_knowledge(query) → LightRAG 结构化响应 → tool result(JSON)存消息历史 → 前端解析渲染徽章/引用/图谱 → LLM 基于 response 继续回答

## 测试

- 后端:mock LightRAG 响应验证 JSON 结构;失败路径返回 error 结构
- 前端:tsc/prettier;本地知识库为空验证空态,引用/图谱用 mock 数据验证