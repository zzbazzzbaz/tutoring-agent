"""LangGraph Server 的 httpx 客户端（网关侧）。

透传流式用 httpx（不依赖 Python langgraph-sdk 消费）；state 查询也用 httpx。
"""
import httpx

from tutoring.core.config import settings


def _base() -> str:
    return settings.langgraph_server_url.rstrip("/")


def state_is_interrupted(state: dict) -> bool:
    """纯函数：state 的 next 非空表示停在 interrupt。"""
    return bool(state.get("next"))


async def get_state(thread_id: str) -> dict:
    """GET /threads/{thread_id}/state，返回 state JSON。"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{_base()}/threads/{thread_id}/state")
        resp.raise_for_status()
        return resp.json()


async def is_interrupted(thread_id: str) -> bool:
    """会话是否停在 interrupt（有未答 quiz）。"""
    try:
        return state_is_interrupted(await get_state(thread_id))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return False  # thread 尚未创建（首次发消息），视为未中断
        raise


async def has_active_run(thread_id: str) -> bool:
    """是否有正在运行的 run（用于 history 的 processing 标志）。"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_base()}/threads/{thread_id}/runs", params={"status": "running"}
        )
        resp.raise_for_status()
        return bool(resp.json())
