"""GraphRAG 检索：向量检索 + 知识图谱 1 跳遍历 + 合并排序。

1. 向量检索 top-5 chunk
2. 从 chunk 提取入口知识点
3. 沿 KnowledgeEdge 1 跳遍历找相邻 KP 的 chunk
4. 合并去重，按距离排序，最多 10 个
5. 格式化返回（标注来源）
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent.agents.llm import get_embedder
from teaching_agent.config import settings


async def graphrag_search(
    session: AsyncSession,
    query: str,
    session_type: str = "free",
    session_context: dict | None = None,
) -> list[dict]:
    """GraphRAG 检索：向量检索 + 图遍历扩展。

    Args:
        session: 数据库会话
        query: 检索词（应已消除指代）
        session_type: free / project / review
        session_context: 会话上下文（project_id / mistake_data 等）

    Returns:
        chunk 列表，每个含 id, content, heading_path, dist, source, edge_type
    """
    session_context = session_context or {}

    # 向量化查询
    embedder = get_embedder()
    query_vec = await embedder.aembed_query(query)

    # 构建 GraphRAG SQL（spec 4.4 节 SQL 实现）
    sql = """
    WITH vector_results AS (
        SELECT c.id, c.content, c.heading_path, c.embedding <=> :vec AS dist
        FROM chunk c
        WHERE c.scope = 'course'
        ORDER BY c.embedding <=> :vec
        LIMIT :top_k
    ),
    entry_kps AS (
        SELECT DISTINCT ck.kp_id
        FROM chunkknowledgepoint ck
        WHERE ck.chunk_id IN (SELECT id FROM vector_results)
    ),
    related_kps AS (
        SELECT target_id AS kp_id, relation_type
        FROM knowledgeedge
        WHERE source_id IN (SELECT kp_id FROM entry_kps)
        UNION
        SELECT source_id AS kp_id, relation_type
        FROM knowledgeedge
        WHERE target_id IN (SELECT kp_id FROM entry_kps)
    ),
    graph_chunks AS (
        SELECT DISTINCT ON (c.id) c.id, c.content, c.heading_path,
               c.embedding <=> :vec AS dist, rk.relation_type AS edge_type
        FROM chunk c
        JOIN chunkknowledgepoint ck ON c.id = ck.chunk_id
        JOIN related_kps rk ON ck.kp_id = rk.kp_id
        WHERE c.id NOT IN (SELECT id FROM vector_results)
        ORDER BY c.id,
                 CASE rk.relation_type
                     WHEN 'prerequisite' THEN 1
                     WHEN 'contrast' THEN 2
                     WHEN 'related' THEN 3
                     WHEN 'part_of' THEN 4
                 END
    )
    SELECT id, content, heading_path, dist, 'vector' AS source, NULL AS edge_type
    FROM vector_results
    WHERE dist < :threshold
    UNION ALL
    SELECT id, content, heading_path, dist, 'graph' AS source, edge_type
    FROM graph_chunks
    WHERE dist < :threshold
    ORDER BY dist
    """

    # project 会话额外检索项目级 chunk
    if session_type == "project" and "project_id" in session_context:
        sql = sql.replace(
            "WHERE c.scope = 'course'",
            "WHERE c.scope = 'course' OR (c.scope = 'project' AND c.project_id = :proj_id)",
        )

    params = {
        "vec": str(query_vec),
        "top_k": settings.TOP_K,
        "threshold": settings.DISTANCE_THRESHOLD,
    }
    if session_type == "project" and "project_id" in session_context:
        params["proj_id"] = session_context["project_id"]

    result = await session.execute(text(sql), params)
    rows = result.fetchall()

    # 格式化结果，标注来源
    chunks = []
    for row in rows:
        source_label = "vector"
        if row.source == "graph":
            source_label = f"graph:{row.edge_type}"

        chunks.append(
            {
                "id": row.id,
                "content": row.content,
                "heading_path": row.heading_path,
                "dist": float(row.dist),
                "source": source_label,
            }
        )

    # review 会话特殊处理：错题的 source_chunk_ids 直接并入候选
    if session_type == "review" and "mistake_data" in session_context:
        mistake = session_context["mistake_data"]
        # 兼容 dict 和对象
        if isinstance(mistake, dict):
            extra_ids = mistake.get("source_chunk_ids", [])
        else:
            extra_ids = getattr(mistake, "source_chunk_ids", None) or []

        if extra_ids:
            # 查询错题关联的 chunk
            placeholders = ", ".join(f":id_{i}" for i in range(len(extra_ids)))
            extra_params = {f"id_{i}": cid for i, cid in enumerate(extra_ids)}
            extra_sql = text(
                f"SELECT id, content, heading_path, embedding <=> :vec AS dist "
                f"FROM chunk WHERE id IN ({placeholders})"
            )
            extra_result = await session.execute(
                extra_sql, {"vec": str(query_vec), **extra_params}
            )
            existing_ids = {c["id"] for c in chunks}
            for row in extra_result.fetchall():
                if row.id not in existing_ids:
                    chunks.append(
                        {
                            "id": row.id,
                            "content": row.content,
                            "heading_path": row.heading_path,
                            "dist": float(row.dist),
                            "source": "mistake",
                        }
                    )
            # 重新按距离排序
            chunks.sort(key=lambda c: c["dist"])

    # 限制最多 10 个
    return chunks[:10]


def format_chunks(chunks: list[dict]) -> str:
    """格式化检索结果为 Agent 可读的文本。

    Args:
        chunks: graphrag_search 返回的 chunk 列表

    Returns:
        格式化的文本，空列表时返回兜底提示
    """
    if not chunks:
        return "未检索到相关内容，该问题可能超出当前课程知识库范围"

    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"【片段{i}】(来源: {chunk['source']}, 相似度: {1 - chunk['dist']:.2f})\n"
            f"标题路径: {chunk['heading_path']}\n"
            f"内容: {chunk['content']}"
        )
    return "\n\n".join(parts)