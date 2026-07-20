"""LightRAG SDK 工厂：LLM/Embedding 函数 + create_rag()。"""
import logging

import numpy as np
from lightrag import LightRAG
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import wrap_embedding_func_with_attrs

from tutoring.core.config import settings

logger = logging.getLogger(__name__)


async def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
    return await openai_complete_if_cache(
        settings.llm_model,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        **kwargs,
    )


@wrap_embedding_func_with_attrs(
    embedding_dim=settings.embedding_dim,
    max_token_size=8192,
    model_name=settings.embedding_model,
)
async def embedding_func(texts: list[str]) -> np.ndarray:
    return await openai_embed.func(
        texts,
        model=settings.embedding_model,
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


def create_rag() -> LightRAG:

    rag = LightRAG(
        workspace="default",
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        kv_storage="PGKVStorage",
        vector_storage="PGVectorStorage",
        graph_storage="Neo4JStorage",
        doc_status_storage="PGDocStatusStorage",
    )
    logger.info("LightRAG instance created (workspace=default)")
    return rag
