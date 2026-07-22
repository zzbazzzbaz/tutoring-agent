from tutoring.chat.server_client import state_is_interrupted


def test_state_is_interrupted_true_when_next_nonempty():
    assert state_is_interrupted({"next": ["__interrupt__"], "values": {}, "tasks": []}) is True


def test_state_is_interrupted_false_when_next_empty():
    assert state_is_interrupted({"next": [], "values": {}, "tasks": []}) is False


def test_state_is_interrupted_false_when_missing_next():
    assert state_is_interrupted({"values": {}}) is False


import pytest

from tutoring.chat.server_client import proxy_run_stream


@pytest.mark.skipif(
    True,  # 集成测试：需 langgraph dev 在跑；去掉 True 并确保 Server 运行后启用
    reason="需 langgraph dev 在 localhost:2024 运行",
)
async def test_proxy_run_stream_yields_bytes():
    body = {
        "assistant_id": "tutor",
        "input": {"messages": [{"role": "user", "content": "你好"}]},
        "stream_mode": ["messages", "updates"],
        "multitask_strategy": "reject",
        "on_disconnect": "continue",
        "if_not_exists": "create",
        "context": {"mode": "free", "course_name": "计算机网络"},
    }
    seen = []
    async for chunk in proxy_run_stream("__test_thread__", body):
        seen.append(chunk)
        if len(seen) > 3:
            break
    assert seen, "应至少收到一个 SSE 字节块"
    assert isinstance(seen[0], (bytes, bytearray))
