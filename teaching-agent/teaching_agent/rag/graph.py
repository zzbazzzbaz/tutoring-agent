"""知识图谱 CRUD + 图遍历查询。"""
import uuid

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from teaching_agent.models import KnowledgePoint, KnowledgeEdge, ChunkKnowledgePoint


async def upsert_kp(session: AsyncSession, name: str, description: str = "") -> KnowledgePoint:
    """创建或获取知识点（按 name 去重）。"""
    stmt = select(KnowledgePoint).where(KnowledgePoint.name == name)
    result = await session.execute(stmt)
    kp = result.scalar_one_or_none()
    if kp:
        return kp

    kp = KnowledgePoint(id=str(uuid.uuid4()), name=name, description=description)
    session.add(kp)
    await session.flush()
    return kp


async def upsert_edge(
    session: AsyncSession,
    source_id: str,
    target_id: str,
    relation_type: str,
) -> None:
    """创建知识点间边（去重：同一 source+target+relation_type 只保留一条）。"""
    stmt = select(KnowledgeEdge).where(
        KnowledgeEdge.source_id == source_id,
        KnowledgeEdge.target_id == target_id,
        KnowledgeEdge.relation_type == relation_type,
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return

    session.add(KnowledgeEdge(
        id=str(uuid.uuid4()),
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
    ))
    await session.flush()


async def link_chunk_kp(session: AsyncSession, chunk_id: str, kp_id: str) -> None:
    """关联 chunk 和知识点（去重）。"""
    stmt = select(ChunkKnowledgePoint).where(
        ChunkKnowledgePoint.chunk_id == chunk_id,
        ChunkKnowledgePoint.kp_id == kp_id,
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return

    session.add(ChunkKnowledgePoint(chunk_id=chunk_id, kp_id=kp_id))
    await session.flush()


async def get_all_kp_names(session: AsyncSession) -> list[str]:
    """获取所有知识点名称（供 LLM 分析时复用）。"""
    stmt = select(KnowledgePoint.name).order_by(KnowledgePoint.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_graph_view(session: AsyncSession) -> dict:
    """获取知识图谱全貌（节点 + 边），用于 notebook 可视化。"""
    kp_stmt = select(KnowledgePoint).order_by(KnowledgePoint.name)
    kp_result = await session.execute(kp_stmt)
    kps = kp_result.scalars().all()

    id_to_name = {kp.id: kp.name for kp in kps}

    edge_stmt = select(KnowledgeEdge)
    edge_result = await session.execute(edge_stmt)
    edges = edge_result.scalars().all()

    return {
        "nodes": [{"name": kp.name, "description": kp.description} for kp in kps],
        "edges": [
            {
                "source": id_to_name.get(e.source_id, e.source_id),
                "target": id_to_name.get(e.target_id, e.target_id),
                "relation_type": e.relation_type,
            }
            for e in edges
        ],
    }
