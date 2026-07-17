"""文本向量化，使用 DashScope text-embedding-v4（1024 维）。"""
from teaching_agent.agents.llm import get_embedder


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化文本。

    Args:
        texts: 待向量化的文本列表

    Returns:
        向量列表，每个向量 1024 维
    """
    embedder = get_embedder()
    return await embedder.aembed_documents(texts)


async def embed_query(text: str) -> list[float]:
    """向量化单条查询文本。"""
    embedder = get_embedder()
    return await embedder.aembed_query(text)
