"""LangGraph Server 的 httpx 客户端（网关侧）。

透传流式用 httpx（不依赖 Python langgraph-sdk 消费）；state 查询也用 httpx。
"""
import asyncio
import json as _json
from typing import AsyncIterator

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


_HEARTBEAT_INTERVAL = 15.0


async def proxy_run_stream(thread_id: str, body: dict) -> AsyncIterator[bytes]:
    """透传 Server 的 /threads/{id}/runs/stream SSE 字节，叠加 15s 心跳。

    用 httpx 流式 POST；与一个心跳协程通过 asyncio.Queue 合并 yield。
    Server 路由形态以 Task 1 Step 8 确认结果为准（/threads/{id}/runs/stream）。
    """
    url = f"{_base()}/threads/{thread_id}/runs/stream"
    out: asyncio.Queue = asyncio.Queue()

    async def pump_upstream():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=body) as resp:
                    if resp.status_code >= 400:
                        text = await resp.aread()
                        await out.put(("error", resp.status_code, text))
                        return
                    async for chunk in resp.aiter_bytes():
                        if chunk:
                            await out.put(("data", chunk))
        except Exception as e:  # noqa: BLE001
            await out.put(("exc", e))
        finally:
            await out.put(("done", None))

    async def heartbeat():
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                await out.put(("data", b": heartbeat\n\n"))
        except asyncio.CancelledError:
            return

    pump_task = asyncio.create_task(pump_upstream())
    hb_task = asyncio.create_task(heartbeat())
    try:
        while True:
            kind, *rest = await out.get()
            if kind == "data":
                yield rest[0]
            elif kind == "error":
                status, text = rest
                yield _sse_error(status, text)
                break
            elif kind == "exc":
                yield _sse_error(502, str(rest[0]).encode())
                break
            elif kind == "done":
                break
    finally:
        hb_task.cancel()
        pump_task.cancel()
        await asyncio.gather(hb_task, pump_task, return_exceptions=True)


def _sse_error(status: int, text: bytes) -> bytes:
    """把 Server 的非 2xx 透传为前端可识别的 SSE error 事件（保持网关错误体风格）。"""
    msg = text.decode("utf-8", "replace")
    data = _json.dumps({"message": msg, "code": f"SERVER_{status}"}, ensure_ascii=False)
    return f"event: error\ndata: {data}\n\n".encode("utf-8")
