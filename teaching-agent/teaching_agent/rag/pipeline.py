"""知识库入库流水线：切分 -> 向量化 -> 写入 pgvector -> LLM 知识图谱分析。"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent.agents.llm import get_llm, structured_call, get_embedder
from teaching_agent.agents.schemas import ChunkAnalysis
from teaching_agent.agents.prompts import CHUNK_ANALYSIS_PROMPT
from teaching_agent.models import KBDocument, Chunk
from teaching_agent.rag.chunker import chunk_markdown
from teaching_agent.rag.graph import upsert_kp, upsert_edge, link_chunk_kp, get_all_kp_names


async def ingest_document(
    session: AsyncSession,
    filename: str,
    content: str,
    scope: str,
    project_id: str | None = None,
) -> str:
    """入库单个文档：切分 -> 向量化 -> 写入 -> 知识图谱分析。

    session 由调用方传入（notebook 手动创建，FastAPI 用 Depends 注入），
    commit 也由调用方控制。

    Args:
        session: 数据库会话
        filename: 文件名
        content: markdown 原文
        scope: course / project
        project_id: 项目级文档关联的项目 ID

    Returns:
        文档 ID
    """
    # 1. 创建 KBDocument 记录
    doc_id = str(uuid.uuid4())
    doc = KBDocument(
        id=doc_id,
        scope=scope,
        project_id=project_id,
        filename=filename,
        status="processing",
        chunk_count=0,
    )
    session.add(doc)
    await session.flush()

    # 2. 切分
    chunk_results = chunk_markdown(content)

    # 3. 向量化
    embedder = get_embedder()
    texts = [c.content for c in chunk_results]
    vectors = await embedder.aembed_documents(texts)

    # 4. 写入 Chunk
    chunk_ids = []
    for cr, vec in zip(chunk_results, vectors):
        chunk_id = str(uuid.uuid4())
        chunk_ids.append(chunk_id)
        session.add(Chunk(
            id=chunk_id,
            document_id=doc_id,
            content=cr.content,
            heading_path=cr.heading_path,
            chunk_index=cr.chunk_index,
            scope=scope,
            project_id=project_id,
            embedding=vec,
        ))
    await session.flush()

    # 5. 逐 chunk LLM 知识图谱分析
    llm = get_llm()
    for chunk_id, cr in zip(chunk_ids, chunk_results):
        existing_kps = await get_all_kp_names(session)
        prompt = CHUNK_ANALYSIS_PROMPT.format(
            chunk_content=cr.content,
            heading_path=cr.heading_path,
            existing_kps=", ".join(existing_kps) if existing_kps else "（暂无）",
        )

        try:
            analysis: ChunkAnalysis = await structured_call(llm, ChunkAnalysis, prompt)
        except Exception as e:
            print(f"  [警告] chunk {chunk_id} 图谱分析失败: {e}")
            continue

        # 6. 写入知识点和边
        kp_name_to_id = {}
        for kp_sugg in analysis.knowledge_points:
            kp = await upsert_kp(session, kp_sugg.name, kp_sugg.description)
            kp_name_to_id[kp_sugg.name] = kp.id
            await link_chunk_kp(session, chunk_id, kp.id)

        for edge_sugg in analysis.edges:
            src_id = kp_name_to_id.get(edge_sugg.source)
            tgt_id = kp_name_to_id.get(edge_sugg.target)
            if src_id and tgt_id:
                await upsert_edge(session, src_id, tgt_id, edge_sugg.relation_type)

    # 7. 更新文档状态
    doc.status = "ready"
    doc.chunk_count = len(chunk_results)

    print(f"✓ 入库完成: {filename} ({len(chunk_results)} chunks)")
    return doc_id
