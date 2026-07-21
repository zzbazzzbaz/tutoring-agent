"""每个会话的后台 agent 任务注册表（进程级）。

sse 层在启动流式任务时 register，任务结束（正常或异常）时由 streaming
的 finally 调 unregister；并发请求通过 get 检测同一 session 是否已有任务在跑，
从而返回 409 而不是重复启动。
"""
import asyncio
import uuid

_running_tasks: dict[uuid.UUID, asyncio.Task] = {}


def register(session_id: uuid.UUID, task: asyncio.Task) -> None:
    """登记一个正在运行的后台任务。"""
    _running_tasks[session_id] = task


def unregister(session_id: uuid.UUID) -> None:
    """移除登记（任务结束时的 finally 调用）。"""
    _running_tasks.pop(session_id, None)


def get(session_id: uuid.UUID) -> asyncio.Task | None:
    """返回正在运行的任务；已完成则清理并返回 None。"""
    task = _running_tasks.get(session_id)
    if task and not task.done():
        return task
    _running_tasks.pop(session_id, None)
    return None
