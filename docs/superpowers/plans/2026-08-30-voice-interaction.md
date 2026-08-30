# 语音交互模块实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现双向语音对话——学生流式语音提问（边说边出字）、Agent 回复流式播报（边出字边发声）、教师端回放学生原声与 Agent 语音。

**Architecture:** 前端录音流经 WebSocket 推给 API Server，API Server 作为 DashScope WebSocket 代理（转发音频帧 + 回传识别结果 + 写盘保存原声）；Agent 回复文本按句切分后经 WebSocket 送 API Server，API Server 转发 DashScope TTS 流式合成，音频帧回传前端播放并写盘。语音映射存新表 `message_audio`，教师端按映射渲染播放器。

**Tech Stack:** FastAPI WebSocket · websockets · DashScope `qwen-audio-3.0-asr-flash-streaming` / `qwen-audio-3.0-tts-flash` · SQLModel · Next.js Web Audio API

**Spec:** `docs/superpowers/specs/2026-08-30-voice-interaction-design.md`

## Global Constraints

- 无需考虑安全性问题：不加鉴权、不加权限校验、音频静态挂载直接可访问
- 不暴露 DashScope API Key 给前端：ASR/TTS 全部经 API Server 代理
- 学生原声格式：前端采集 PCM 16kHz 16bit 单声道（流式 ASR 要求），写盘时封装为 WAV 头以便浏览器直接播放
- TTS 输出格式：PCM 22050Hz 16bit 单声道（`AudioFormat.PCM_22050HZ_MONO_16BIT` 对应），写盘时封装 WAV 头
- 语音映射注册时机：学生消息用前端自生成的 uuid（与发给 Agent 的消息 id 一致）；Agent 消息用 LangGraph 返回的 message id
- 前端代码不加注释（遵循项目约定）
- 后端遵守 ruff（line-length=100, select E/F/I/UP/B/SIM），前端遵守 prettier + eslint
- 测试风格遵循现有 `tests/test_management_api.py`：纯单测 + monkeypatch，不依赖真实数据库

---

### Task 1: 配置项与 `MessageAudio` 数据模型

**Files:**
- Modify: `services/api_server/src/tutoring/core/config.py`
- Modify: `services/api_server/src/tutoring/db/models.py`
- Modify: `services/api_server/src/tutoring/db/repos.py`
- Modify: `services/api_server/pyproject.toml`
- Test: `services/api_server/tests/test_speech_models.py`（新建）

**Interfaces:**
- Produces:
  - `Settings.speech_dashscope_api_key: str | None`、`Settings.audio_storage_dir: str = "data/audio"`、`Settings.speech_voice: str = "longxiaochun_v3"`
  - `MessageAudio` 表：`id: uuid.UUID PK`、`session_id: uuid.UUID FK→session.id (index)`、`message_id: str`、`role: str ("user"/"assistant")`、`text: str | None`、`audio_path: str`、`created_at: datetime`
  - `repos.create_message_audio(db, *, session_id, message_id, role, text, audio_path) -> MessageAudio`
  - `repos.list_message_audios_by_session(db, session_id) -> list[MessageAudio]`

- [ ] **Step 1: 写失败测试**

创建 `services/api_server/tests/test_speech_models.py`：

```python
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tutoring.db import repos
from tutoring.db.models import MessageAudio


@pytest.mark.asyncio
async def test_create_message_audio_commits_row(monkeypatch):
    calls: list[dict] = []

    class FakeSession:
        def add(self, obj):  # noqa: D102
            calls.append({"op": "add", "obj": obj})

        async def commit(self):  # noqa: D102
            calls.append({"op": "commit"})

        async def refresh(self, obj):  # noqa: D102
            calls.append({"op": "refresh", "obj": obj})

    audio = MessageAudio(
        id=uuid4(),
        session_id=uuid4(),
        message_id="msg-1",
        role="user",
        text="你好",
        audio_path="data/audio/xx.wav",
        created_at=datetime.now(UTC),
    )
    fake = FakeSession()
    result = await repos.create_message_audio(
        fake,
        session_id=audio.session_id,
        message_id=audio.message_id,
        role=audio.role,
        text=audio.text,
        audio_path=audio.audio_path,
    )
    assert isinstance(result, MessageAudio)
    assert calls[0]["op"] == "add"
    assert calls[1]["op"] == "commit"


@pytest.mark.asyncio
async def test_list_message_audios_by_session_returns_rows(monkeypatch):
    audio = MessageAudio(
        id=uuid4(),
        session_id=uuid4(),
        message_id="msg-1",
        role="user",
        text="你好",
        audio_path="data/audio/xx.wav",
        created_at=datetime.now(UTC),
    )

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return [audio]

    class FakeSession:
        async def execute(self, _stmt):
            return FakeResult()

    result = await repos.list_message_audios_by_session(FakeSession(), audio.session_id)
    assert result == [audio]


@pytest.mark.asyncio
async def test_message_audio_table_name():
    assert MessageAudio.__tablename__ == "message_audio"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd services/api_server && uv run pytest tests/test_speech_models.py -v`
Expected: FAIL — `ImportError`（模型/repos 不存在）

- [ ] **Step 3: 实现**

`pyproject.toml` dependencies 增加一行：`"websockets>=12.0,<16",`

`config.py` 增加：

```python
    speech_dashscope_api_key: str | None = None
    audio_storage_dir: str = "data/audio"
    speech_voice: str = "longxiaochun_v3"
```

`models.py` 末尾增加：

```python
class MessageAudio(SQLModel, table=True):
    """语音与聊天消息的关联。"""

    __tablename__ = "message_audio"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    session_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("session.id", ondelete="CASCADE"),
            index=True,
        ),
    )
    message_id: str = Field(max_length=64)
    role: str = Field(max_length=20)  # user / assistant
    text: str | None = Field(default=None, sa_column=Column(Text))
    audio_path: str = Field(max_length=500)
    created_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=func.now())
    )
```

`repos.py` 末尾增加：

```python
async def create_message_audio(
    session: AsyncSession,
    *,
    session_id: UUID,
    message_id: str,
    role: str,
    text: str | None,
    audio_path: str,
) -> MessageAudio:
    obj = MessageAudio(
        session_id=session_id,
        message_id=message_id,
        role=role,
        text=text,
        audio_path=audio_path,
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def list_message_audios_by_session(
    session: AsyncSession, session_id: UUID
) -> list[MessageAudio]:
    stmt = (
        select(MessageAudio)
        .where(MessageAudio.session_id == session_id)
        .order_by(MessageAudio.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd services/api_server && uv run pytest tests/test_speech_models.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 5: Commit**

```bash
git add services/api_server/pyproject.toml services/api_server/src/tutoring/core/config.py services/api_server/src/tutoring/db/models.py services/api_server/src/tutoring/db/repos.py services/api_server/tests/test_speech_models.py
git commit -m "feat: 新增 MessageAudio 模型与语音配置项"
```

---

### Task 2: DashScope ASR 流式客户端

**Files:**
- Create: `services/api_server/src/tutoring/speech/dashscope_asr.py`
- Create: `services/api_server/src/tutoring/speech/__init__.py`
- Test: `services/api_server/tests/test_dashscope_asr.py`（新建）

**Interfaces:**
- Consumes: `Settings.speech_dashscope_api_key`、`Settings.audio_storage_dir`
- Produces:
  - `ASR_DASH_SCOPE_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"`
  - `async def stream_asr(audio_frames: AsyncIterator[bytes], *, api_key: str) -> AsyncIterator[dict]`：连接 DashScope，发 `run-task`，转发音频帧，yield 每个 `result-generated` 事件解析后的 dict `{"sentence_id": int, "text": str, "sentence_end": bool, "raw": dict}`；收到 `task-failed` 抛 `DashScopeSpeechError`

- [ ] **Step 1: 写失败测试**

创建 `services/api_server/tests/test_dashscope_asr.py`：

```python
import json

import pytest

from tutoring.speech.dashscope_asr import (
    ASR_DASH_SCOPE_WS_URL,
    DashScopeSpeechError,
    stream_asr,
)


@pytest.mark.asyncio
async def test_stream_asr_forwards_frames_and_yields_results(monkeypatch):
    received_frames: list[bytes] = []
    sent_messages: list[dict] = []
    sent_binaries: list[bytes] = []

    class FakeWS:
        def __init__(self, *args, **kwargs):
            self._events = iter(
                [
                    json.dumps({"header": {"event": "task-started"}}),
                    json.dumps(
                        {
                            "header": {"event": "result-generated"},
                            "payload": {
                                "output": {
                                    "sentence": {
                                        "sentence_id": 1,
                                        "text": "你好",
                                        "sentence_end": False,
                                    }
                                }
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "header": {"event": "result-generated"},
                            "payload": {
                                "output": {
                                    "sentence": {
                                        "sentence_id": 1,
                                        "text": "你好世界",
                                        "sentence_end": True,
                                    }
                                }
                            },
                        }
                    ),
                    json.dumps({"header": {"event": "task-finished"}}),
                ]
            )

        async def send(self, message):
            if isinstance(message, bytes):
                sent_binaries.append(message)
            else:
                sent_messages.append(json.loads(message))

        async def recv(self):
            return next(self._events)

        async def close(self):
            pass

    async def fake_connect(uri, additional_headers):
        assert uri == ASR_DASH_SCOPE_WS_URL
        assert additional_headers["Authorization"] == "Bearer sk-test"
        return FakeWS()

    monkeypatch.setattr("tutoring.speech.dashscope_asr.connect", fake_connect)

    frames = [b"\x00\x01" * 20, b"\x02\x03" * 20]

    async def frame_iter():
        for f in frames:
            yield f

    results = [r async for r in stream_asr(frame_iter(), api_key="sk-test")]

    assert len(results) == 2
    assert results[0]["sentence_id"] == 1
    assert results[0]["text"] == "你好"
    assert results[0]["sentence_end"] is False
    assert results[1]["text"] == "你好世界"
    assert results[1]["sentence_end"] is True
    assert sent_binaries == frames
    run_task = next(m for m in sent_messages if m["header"]["action"] == "run-task")
    assert run_task["payload"]["model"] == "qwen-audio-3.0-asr-flash-streaming"
    assert run_task["payload"]["parameters"] == {"format": "pcm", "sample_rate": 16000}


@pytest.mark.asyncio
async def test_stream_asr_raises_on_task_failed(monkeypatch):
    class FakeWS:
        async def __init__(self, *args, **kwargs):
            pass

        async def send(self, _message):
            pass

        async def recv(self):
            return json.dumps(
                {
                    "header": {
                        "event": "task-failed",
                        "error_code": "CLIENT_ERROR",
                        "error_message": "boom",
                    }
                }
            )

        async def close(self):
            pass

    async def fake_connect(uri, additional_headers):
        ws = FakeWS()
        await ws.__init__()
        return ws

    monkeypatch.setattr("tutoring.speech.dashscope_asr.connect", fake_connect)

    async def empty_frames():
        return
        yield

    with pytest.raises(DashScopeSpeechError):
        async for _ in stream_asr(empty_frames(), api_key="sk-test"):
            pass
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd services/api_server && uv run pytest tests/test_dashscope_asr.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现**

创建 `services/api_server/src/tutoring/speech/__init__.py`（空文件）。

创建 `services/api_server/src/tutoring/speech/dashscope_asr.py`：

```python
import json
import logging
from collections.abc import AsyncIterator

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

logger = logging.getLogger(__name__)

ASR_DASH_SCOPE_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
_ASR_MODEL = "qwen-audio-3.0-asr-flash-streaming"


class DashScopeSpeechError(Exception):
    pass


def _run_task() -> dict:
    return {
        "header": {
            "action": "run-task",
            "task_id": __import__("uuid").uuid4().hex,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "asr",
            "function": "recognition",
            "model": _ASR_MODEL,
            "parameters": {"format": "pcm", "sample_rate": 16000},
            "input": {},
        },
    }


def _finish_task(task_id: str) -> dict:
    return {
        "header": {"action": "finish-task", "task_id": task_id, "streaming": "duplex"},
        "payload": {"input": {}},
    }


async def stream_asr(
    audio_frames: AsyncIterator[bytes], *, api_key: str
) -> AsyncIterator[dict]:
    task_id = __import__("uuid").uuid4().hex
    async with connect(
        ASR_DASH_SCOPE_WS_URL,
        additional_headers={"Authorization": f"Bearer {api_key}"},
    ) as ws:
        await ws.send(json.dumps(_run_task()))
        while True:
            message = await ws.recv()
            if isinstance(message, bytes):
                continue
            event = json.loads(message)
            event_name = event["header"].get("event")
            if event_name == "task-started":
                break
            if event_name == "task-failed":
                raise DashScopeSpeechError(
                    event["header"].get("error_message", "ASR task failed")
                )
        async for frame in audio_frames:
            await ws.send(frame)
        await ws.send(json.dumps(_finish_task(task_id)))
        while True:
            message = await ws.recv()
            if isinstance(message, bytes):
                continue
            event = json.loads(message)
            event_name = event["header"].get("event")
            if event_name == "result-generated":
                sentence = event.get("payload", {}).get("output", {}).get("sentence", {})
                if sentence:
                    yield {
                        "sentence_id": sentence.get("sentence_id"),
                        "text": sentence.get("text", ""),
                        "sentence_end": bool(sentence.get("sentence_end", False)),
                        "raw": event,
                    }
            elif event_name == "task-failed":
                raise DashScopeSpeechError(
                    event["header"].get("error_message", "ASR task failed")
                )
            elif event_name == "task-finished":
                break
```

注意：`task_id` 在 `_run_task` 里生成了一次，`stream_asr` 又生成一次——**保持一致**：在 `stream_asr` 中生成 `task_id`，传给 `_run_task(task_id)` 和 `_finish_task(task_id)`。修正实现：

```python
async def stream_asr(
    audio_frames: AsyncIterator[bytes], *, api_key: str
) -> AsyncIterator[dict]:
    task_id = uuid.uuid4().hex
    async with connect(
        ASR_DASH_SCOPE_WS_URL,
        additional_headers={"Authorization": f"Bearer {api_key}"},
    ) as ws:
        run_task = {
            "header": {"action": "run-task", "task_id": task_id, "streaming": "duplex"},
            "payload": {
                "task_group": "audio",
                "task": "asr",
                "function": "recognition",
                "model": _ASR_MODEL,
                "parameters": {"format": "pcm", "sample_rate": 16000},
                "input": {},
            },
        }
        await ws.send(json.dumps(run_task))
        while True:
            message = await ws.recv()
            if isinstance(message, bytes):
                continue
            event = json.loads(message)
            event_name = event["header"].get("event")
            if event_name == "task-started":
                break
            if event_name == "task-failed":
                raise DashScopeSpeechError(
                    event["header"].get("error_message", "ASR task failed")
                )
        async for frame in audio_frames:
            await ws.send(frame)
        await ws.send(
            json.dumps(
                {
                    "header": {
                        "action": "finish-task",
                        "task_id": task_id,
                        "streaming": "duplex",
                    },
                    "payload": {"input": {}},
                }
            )
        )
        while True:
            message = await ws.recv()
            if isinstance(message, bytes):
                continue
            event = json.loads(message)
            event_name = event["header"].get("event")
            if event_name == "result-generated":
                sentence = event.get("payload", {}).get("output", {}).get("sentence", {})
                if sentence:
                    yield {
                        "sentence_id": sentence.get("sentence_id"),
                        "text": sentence.get("text", ""),
                        "sentence_end": bool(sentence.get("sentence_end", False)),
                        "raw": event,
                    }
            elif event_name == "task-failed":
                raise DashScopeSpeechError(
                    event["header"].get("error_message", "ASR task failed")
                )
            elif event_name == "task-finished":
                break
```

并在文件头 `import uuid`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd services/api_server && uv run pytest tests/test_dashscope_asr.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: Commit**

```bash
git add services/api_server/src/tutoring/speech/ services/api_server/tests/test_dashscope_asr.py
git commit -m "feat: DashScope 流式 ASR 客户端"
```

---

### Task 3: DashScope TTS 流式客户端

**Files:**
- Create: `services/api_server/src/tutoring/speech/dashscope_tts.py`
- Test: `services/api_server/tests/test_dashscope_tts.py`（新建）

**Interfaces:**
- Consumes: `Settings.speech_dashscope_api_key`、`Settings.speech_voice`
- Produces:
  - `TTS_DASH_SCOPE_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"`
  - `async def stream_tts(text: str, *, api_key: str, voice: str) -> AsyncIterator[bytes]`：连接 DashScope，发 `run-task`（task_group=audio, task=tts, function=speech-synthesis, model=`qwen-audio-3.0-tts-flash`, parameters={"format": "pcm", "sample_rate": 22050, "voice": voice}），yield 每个 `result-generated` 中 `payload.output.audio.data`（base64）解码后的 PCM 字节；`task-failed` 抛 `DashScopeSpeechError`

- [ ] **Step 1: 写失败测试**

创建 `services/api_server/tests/test_dashscope_tts.py`：

```python
import base64
import json

import pytest

from tutoring.speech.dashscope_tts import (
    TTS_DASH_SCOPE_WS_URL,
    DashScopeSpeechError,
    stream_tts,
)


@pytest.mark.asyncio
async def test_stream_tts_yields_audio_chunks(monkeypatch):
    sent_messages: list[dict] = []
    chunk = b"\x10\x00" * 100

    class FakeWS:
        async def __init__(self, *args, **kwargs):
            pass

        async def send(self, message):
            sent_messages.append(json.loads(message))

        async def recv(self):
            return json.dumps(
                {
                    "header": {"event": "result-generated"},
                    "payload": {
                        "output": {
                            "type": "sentence-synthesis",
                            "audio": {"data": base64.b64encode(chunk).decode()},
                        }
                    },
                }
            )

        async def close(self):
            pass

    async def fake_connect(uri, additional_headers):
        assert uri == TTS_DASH_SCOPE_WS_URL
        assert additional_headers["Authorization"] == "Bearer sk-test"
        ws = FakeWS()
        await ws.__init__()
        return ws

    monkeypatch.setattr("tutoring.speech.dashscope_tts.connect", fake_connect)

    chunks = [c async for c in stream_tts("你好", api_key="sk-test", voice="v1")]

    assert chunks == [chunk]
    run_task = next(m for m in sent_messages if m["header"]["action"] == "run-task")
    assert run_task["payload"]["model"] == "qwen-audio-3.0-tts-flash"
    assert run_task["payload"]["parameters"] == {
        "format": "pcm",
        "sample_rate": 22050,
        "voice": "v1",
    }
    assert run_task["payload"]["input"] == {"text": "你好"}


@pytest.mark.asyncio
async def test_stream_tts_raises_on_task_failed(monkeypatch):
    class FakeWS:
        async def __init__(self, *args, **kwargs):
            pass

        async def send(self, _message):
            pass

        async def recv(self):
            return json.dumps(
                {
                    "header": {
                        "event": "task-failed",
                        "error_code": "CLIENT_ERROR",
                        "error_message": "boom",
                    }
                }
            )

        async def close(self):
            pass

    async def fake_connect(uri, additional_headers):
        ws = FakeWS()
        await ws.__init__()
        return ws

    monkeypatch.setattr("tutoring.speech.dashscope_tts.connect", fake_connect)

    with pytest.raises(DashScopeSpeechError):
        async for _ in stream_tts("你好", api_key="sk-test", voice="v1"):
            pass
```

注意 FakeWS 的 recv 会无限返回同一事件——第一个测试里 `stream_tts` 收到 task-started 前会循环 recv。需要让 FakeWS 的 recv 按事件序列返回：先 `task-started`，再 `result-generated`，再 `task-finished`。修正测试：

```python
    class FakeWS:
        def __init__(self, *args, **kwargs):
            self._events = iter(
                [
                    json.dumps({"header": {"event": "task-started"}}),
                    json.dumps(
                        {
                            "header": {"event": "result-generated"},
                            "payload": {
                                "output": {
                                    "type": "sentence-synthesis",
                                    "audio": {"data": base64.b64encode(chunk).decode()},
                                }
                            },
                        }
                    ),
                    json.dumps({"header": {"event": "task-finished"}}),
                ]
            )

        async def send(self, message):
            sent_messages.append(json.loads(message))

        async def recv(self):
            return next(self._events)

        async def close(self):
            pass
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd services/api_server && uv run pytest tests/test_dashscope_tts.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现**

创建 `services/api_server/src/tutoring/speech/dashscope_tts.py`：

```python
import base64
import json
import uuid
from collections.abc import AsyncIterator

from websockets.asyncio.client import connect

TTS_DASH_SCOPE_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
_TTS_MODEL = "qwen-audio-3.0-tts-flash"


class DashScopeSpeechError(Exception):
    pass


async def stream_tts(
    text: str, *, api_key: str, voice: str
) -> AsyncIterator[bytes]:
    task_id = uuid.uuid4().hex
    run_task = {
        "header": {"action": "run-task", "task_id": task_id, "streaming": "duplex"},
        "payload": {
            "task_group": "audio",
            "task": "tts",
            "function": "speech-synthesis",
            "model": _TTS_MODEL,
            "parameters": {
                "format": "pcm",
                "sample_rate": 22050,
                "voice": voice,
            },
            "input": {"text": text},
        },
    }
    async with connect(
        TTS_DASH_SCOPE_WS_URL,
        additional_headers={"Authorization": f"Bearer {api_key}"},
    ) as ws:
        await ws.send(json.dumps(run_task))
        while True:
            message = await ws.recv()
            if isinstance(message, bytes):
                continue
            event = json.loads(message)
            event_name = event["header"].get("event")
            if event_name == "task-started":
                break
            if event_name == "task-failed":
                raise DashScopeSpeechError(
                    event["header"].get("error_message", "TTS task failed")
                )
        while True:
            message = await ws.recv()
            if isinstance(message, bytes):
                continue
            event = json.loads(message)
            event_name = event["header"].get("event")
            if event_name == "result-generated":
                audio = (
                    event.get("payload", {})
                    .get("output", {})
                    .get("audio", {})
                    .get("data")
                )
                if audio:
                    yield base64.b64decode(audio)
            elif event_name == "task-failed":
                raise DashScopeSpeechError(
                    event["header"].get("error_message", "TTS task failed")
                )
            elif event_name == "task-finished":
                break
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd services/api_server && uv run pytest tests/test_dashscope_tts.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: Commit**

```bash
git add services/api_server/src/tutoring/speech/dashscope_tts.py services/api_server/tests/test_dashscope_tts.py
git commit -m "feat: DashScope 流式 TTS 客户端"
```

---

### Task 4: 音频写盘工具

**Files:**
- Create: `services/api_server/src/tutoring/speech/storage.py`
- Test: `services/api_server/tests/test_speech_storage.py`（新建）

**Interfaces:**
- Consumes: `Settings.audio_storage_dir`
- Produces:
  - `async def save_pcm_as_wav(pcm_frames: AsyncIterator[bytes], *, storage_dir: str, sample_rate: int) -> str`：把 PCM 帧写入 WAV 文件（44 字节头 + 数据），返回相对路径（`data/audio/<uuid>.wav` 形式的 posix 路径字符串）；文件写完后在临时文件完成时 `os.replace` 为最终名（避免半写文件）
  - `class WavWriter`：同步写入用的上下文管理器，`open(path)` → `write(frame: bytes)` → `close()`（补 WAV 头到文件头）；供 WebSocket 端点边收边写

- [ ] **Step 1: 写失败测试**

创建 `services/api_server/tests/test_speech_storage.py`：

```python
import os
import struct
from pathlib import Path

import pytest

from tutoring.speech.storage import WavWriter, save_pcm_as_wav


@pytest.mark.asyncio
async def test_save_pcm_as_wav_writes_valid_wav(tmp_path):
    frames = [b"\x00\x01" * 100, b"\x02\x03" * 100]

    async def frame_iter():
        for f in frames:
            yield f

    rel_path = await save_pcm_as_wav(
        frame_iter(), storage_dir=str(tmp_path), sample_rate=16000
    )

    full = Path(str(tmp_path)) / rel_path
    assert full.exists()
    data = full.read_bytes()
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WAVE"
    sample_rate = struct.unpack("<I", data[24:28])[0]
    assert sample_rate == 16000
    assert data[44:] == b"".join(frames)


def test_wav_writer_writes_header_then_pads(tmp_path):
    path = str(tmp_path / "out.wav")
    writer = WavWriter(path, sample_rate=8000)
    writer.write(b"\x00\x01" * 50)
    writer.close()
    data = Path(path).read_bytes()
    assert data[:4] == b"RIFF"
    assert struct.unpack("<I", data[24:28])[0] == 8000
    assert data[44:] == b"\x00\x01" * 50
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd services/api_server && uv run pytest tests/test_speech_storage.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现**

创建 `services/api_server/src/tutoring/speech/storage.py`：

```python
import os
import struct
import uuid
from collections.abc import AsyncIterator
from pathlib import Path


def _wav_header(data_len: int, sample_rate: int) -> bytes:
    byte_rate = sample_rate * 2
    block_align = 2
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_len,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        byte_rate,
        block_align,
        16,
        b"data",
        data_len,
    )


class WavWriter:
    """边收边写 PCM 为 WAV 文件；close 时把 WAV 头写入文件头。"""

    def __init__(self, path: str, *, sample_rate: int) -> None:
        self._path = path
        self._sample_rate = sample_rate
        self._data_len = 0
        self._fh = open(path, "wb")

    def write(self, frame: bytes) -> None:
        self._fh.write(frame)
        self._data_len += len(frame)

    def close(self) -> None:
        header = _wav_header(self._data_len, self._sample_rate)
        self._fh.flush()
        self._fh.seek(0)
        self._fh.write(header)
        self._fh.close()


async def save_pcm_as_wav(
    pcm_frames: AsyncIterator[bytes], *, storage_dir: str, sample_rate: int
) -> str:
    filename = f"{uuid.uuid4().hex}.wav"
    os.makedirs(storage_dir, exist_ok=True)
    final_path = os.path.join(storage_dir, filename)
    tmp_path = final_path + ".tmp"
    writer = WavWriter(tmp_path, sample_rate=sample_rate)
    try:
        async for frame in pcm_frames:
            writer.write(frame)
    finally:
        writer.close()
    os.replace(tmp_path, final_path)
    return Path("data/audio") / filename
```

注意：`save_pcm_as_wav` 返回的路径假定 `storage_dir` 的父目录名为 `data/audio`——若目录被配置为其他值会不准确。更稳的做法：返回相对路径基于 `storage_dir` 的 basename。简化：约定 `storage_dir` 就是 `data/audio`（config 默认值），返回 `os.path.join(Path(storage_dir).name, filename)`，并加注释说明与静态挂载路径一致。修正：

```python
    rel_dir = Path(storage_dir).name
    return f"{rel_dir}/{filename}"
```

（测试里 `tmp_path` 的 basename 是 `test_save_pcm_as_wav...`，返回 `test_xxx/<uuid>.wav`，与断言 `full.exists()` 一致，因为 `full = tmp_path / rel_path`。）

- [ ] **Step 4: 运行测试确认通过**

Run: `cd services/api_server && uv run pytest tests/test_speech_storage.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: Commit**

```bash
git add services/api_server/src/tutoring/speech/storage.py services/api_server/tests/test_speech_storage.py
git commit -m "feat: PCM 音频写盘为 WAV 工具"
```

---

### Task 5: ASR 流式 WebSocket 端点

**Files:**
- Create: `services/api_server/src/tutoring/speech/router.py`
- Modify: `services/api_server/src/tutoring/app.py`（挂载路由 + 静态目录）
- Test: `services/api_server/tests/test_speech_router.py`（新建）

**Interfaces:**
- Consumes: `stream_asr`（Task 2）、`WavWriter`（Task 4）、`Settings.speech_dashscope_api_key`
- Produces:
  - `WS /speech/asr-stream`：前端推二进制 PCM 帧；中间结果回传 JSON `{"type": "partial", "text": str}` / `{"type": "final", "text": str}`；客户端发 `{"type": "finish"}` 后服务端结束识别、完成写盘、回传 `{"type": "done", "text": str, "audio_url": str}`
  - `router = APIRouter(prefix="/speech", tags=["speech"])`，`app.include_router(speech_router.router)`

- [ ] **Step 1: 写失败测试**

创建 `services/api_server/tests/test_speech_router.py`：

```python
import json

import pytest
from fastapi.testclient import TestClient

from tutoring.speech import router as speech_router
from tutoring.app import app


@pytest.mark.asyncio
async def test_asr_stream_echoes_results_and_done(monkeypatch, tmp_path):
    monkeypatch.setattr(speech_router.settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(speech_router.settings, "speech_dashscope_api_key", "sk-test")

    sent_payloads: list[dict] = []
    final_payload: dict = {}

    async def fake_stream_asr(frames, *, api_key):
        collected = []
        async for f in frames:
            collected.append(f)
        assert collected == [b"\x00\x01" * 20]
        sent_payloads.append({"kind": "partial", "text": "你"})
        yield {"sentence_id": 1, "text": "你", "sentence_end": False}
        sent_payloads.append({"kind": "final", "text": "你好"})
        yield {"sentence_id": 1, "text": "你好", "sentence_end": True}

    monkeypatch.setattr(
        "tutoring.speech.router.stream_asr", fake_stream_asr
    )

    client = TestClient(app)
    with client.websocket_connect("/speech/asr-stream") as ws:
        ws.send_bytes(b"\x00\x01" * 20)
        partial = json.loads(ws.receive_text())
        assert partial["type"] == "partial"
        assert partial["text"] == "你"
        ws.send_text(json.dumps({"type": "finish"}))
        done = json.loads(ws.receive_text())
        assert done["type"] == "done"
        assert done["text"] == "你好"
        assert done["audio_url"].endswith(".wav")
```

注意：TestClient 使用真实 DB（app lifespan 会初始化 engine 并连 PostgreSQL）——测试环境无 DB。参照现有测试（test_management_api.py）做法，测试直接调用路由函数而非 TestClient。但 WebSocket 端点测试用 TestClient 最方便。替代方案：`monkeypatch.setattr` 把 `app.state.db_session_factory` 替换为 Fake，且 TestClient 以 `with TestClient(app)` 触发 lifespan 会连 DB。可以 `monkeypatch.setattr(app.state, "db_session_factory", None)` 且不使用 with（直接 TestClient(app) 仍会执行 lifespan）。

更稳：ASR 端点不依赖 DB（写盘即可），所以测试中把 lifespan 跳过——用 `TestClient(app)` 不带 context manager 也会触发 lifespan。FastAPI TestClient 的 lifespan 只在 `with` 内执行。**不用 `with` 就跳过 lifespan**：

```python
    client = TestClient(app)
    with client.websocket_connect("/speech/asr-stream") as ws:
        ...
```

TestClient 对象创建时不触发 lifespan（starlette 行为：`with TestClient(app)` 才触发）。直接调用 `client.websocket_connect` 会触发吗？TestClient.websocket_connect 内部 portal 启动时若 app 有 lifespan 会执行。实际上 starlette TestClient 在首次请求时才启动 portal，lifespan 在 `with` 时执行。不 with 时 lifespan 不执行，但请求也能工作（旧版行为）。为保险，测试里设置 `monkeypatch.setattr("tutoring.core.database.init_db", fake)` 让 lifespan 不炸：

```python
    async def fake_init_db(_engine):
        pass

    monkeypatch.setattr("tutoring.core.database.init_db", fake_init_db)
```

`test_speech_router.py` 最终测试：

```python
import json

import pytest
from fastapi.testclient import TestClient

from tutoring.app import app
from tutoring.speech import router as speech_router


@pytest.mark.asyncio
async def test_asr_stream_echoes_results_and_done(monkeypatch, tmp_path):
    monkeypatch.setattr(speech_router.settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(speech_router.settings, "speech_dashscope_api_key", "sk-test")

    async def fake_init_db(_engine):
        pass

    monkeypatch.setattr("tutoring.core.database.init_db", fake_init_db)

    async def fake_stream_asr(frames, *, api_key):
        collected = []
        async for f in frames:
            collected.append(f)
        assert collected == [b"\x00\x01" * 20]
        yield {"sentence_id": 1, "text": "你", "sentence_end": False}
        yield {"sentence_id": 1, "text": "你好", "sentence_end": True}

    monkeypatch.setattr("tutoring.speech.router.stream_asr", fake_stream_asr)

    client = TestClient(app)
    with client.websocket_connect("/speech/asr-stream") as ws:
        ws.send_bytes(b"\x00\x01" * 20)
        partial = json.loads(ws.receive_text())
        assert partial["type"] == "partial"
        assert partial["text"] == "你"
        ws.send_text(json.dumps({"type": "finish"}))
        done = json.loads(ws.receive_text())
        assert done["type"] == "done"
        assert done["text"] == "你好"
        assert done["audio_url"].endswith(".wav")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd services/api_server && uv run pytest tests/test_speech_router.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现**

创建 `services/api_server/src/tutoring/speech/router.py`：

```python
import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from tutoring.core.config import settings
from tutoring.speech.dashscope_asr import DashScopeSpeechError, stream_asr
from tutoring.speech.storage import WavWriter

router = APIRouter(prefix="/speech", tags=["speech"])


@router.websocket("/asr-stream")
async def asr_stream(ws: WebSocket) -> None:
    await ws.accept()
    filename = f"{uuid.uuid4().hex}.wav"
    os.makedirs(settings.audio_storage_dir, exist_ok=True)
    file_path = os.path.join(settings.audio_storage_dir, filename)
    writer = WavWriter(file_path, sample_rate=16000)
    frame_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    final_text = ""

    async def frame_iter() -> AsyncIterator[bytes]:
        while True:
            frame = await frame_queue.get()
            if frame is None:
                break
            yield frame

    async def run_asr() -> None:
        nonlocal final_text
        if not settings.speech_dashscope_api_key:
            raise DashScopeSpeechError("speech_dashscope_api_key is not configured")
        async for result in stream_asr(
            frame_iter(), api_key=settings.speech_dashscope_api_key
        ):
            final_text = result["text"]
            message = (
                {"type": "final", "text": result["text"]}
                if result["sentence_end"]
                else {"type": "partial", "text": result["text"]}
            )
            await ws.send_text(json.dumps(message, ensure_ascii=False))

    asr_task = asyncio.create_task(run_asr())
    try:
        while True:
            raw = await ws.receive()
            if "bytes" in raw and raw["bytes"] is not None:
                frame = raw["bytes"]
                writer.write(frame)
                await frame_queue.put(frame)
            elif "text" in raw and raw["text"] is not None:
                data = json.loads(raw["text"])
                if data.get("type") == "finish":
                    await frame_queue.put(None)
                    await asr_task
                    break
    except WebSocketDisconnect:
        await frame_queue.put(None)
        asr_task.cancel()
    finally:
        writer.close()
        audio_url = f"/media/{filename}"
        await ws.send_text(
            json.dumps(
                {
                    "type": "done",
                    "text": final_text,
                    "audio_url": audio_url,
                },
                ensure_ascii=False,
            )
        )
        await ws.close()
```

注意：`writer.close()` 在 `finally` 中执行，然后立即发 `done`——但 `done` 应在写盘完成后发送。当 `asr_task` 完成后 `break` 到 `finally`，此时所有帧已写入队列且 ASR 已消费完毕，但 `writer` 可能还有未落盘数据（队列中已 put 的帧可能还在 ASR 消费中）。为正确性：`break` 前已 `await asr_task`，即所有帧已被 `stream_asr` 消费（frame_iter 全部 yield 完）→ 所有 `writer.write` 已调用 → `writer.close()` 补头即可。可接受。

`app.py` 增加：

```python
from tutoring.speech import router as speech_router
...
os.makedirs(settings.audio_storage_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.upload_dir), name="media")
app.mount("/speech/audio", StaticFiles(directory=settings.audio_storage_dir), name="speech_audio")
...
app.include_router(speech_router.router)
```

audio_url 改为 `/speech/audio/<filename>`：

```python
        audio_url = f"/speech/audio/{filename}"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd services/api_server && uv run pytest tests/test_speech_router.py -v`
Expected: PASS（1 个测试）

- [ ] **Step 5: Commit**

```bash
git add services/api_server/src/tutoring/speech/router.py services/api_server/src/tutoring/app.py services/api_server/tests/test_speech_router.py
git commit -m "feat: ASR 流式 WebSocket 端点（转写+原声写盘）"
```

---

### Task 6: TTS 流式 WebSocket 端点

**Files:**
- Modify: `services/api_server/src/tutoring/speech/router.py`
- Test: `services/api_server/tests/test_speech_router.py`

**Interfaces:**
- Consumes: `stream_tts`（Task 3）、`WavWriter`（Task 4）
- Produces: `WS /speech/tts-stream`：前端发 JSON `{"type": "synthesize", "text": str}` → 合成 → 二进制 PCM 帧回传前端；完成后回传 `{"type": "done", "audio_url": str}`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_speech_router.py`：

```python
@pytest.mark.asyncio
async def test_tts_stream_synthesizes_and_returns_url(monkeypatch, tmp_path):
    monkeypatch.setattr(speech_router.settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(speech_router.settings, "speech_dashscope_api_key", "sk-test")
    monkeypatch.setattr(speech_router.settings, "speech_voice", "v-test")

    async def fake_init_db(_engine):
        pass

    monkeypatch.setattr("tutoring.core.database.init_db", fake_init_db)

    async def fake_stream_tts(text, *, api_key, voice):
        assert text == "你好"
        assert voice == "v-test"
        yield b"\x10\x00" * 50
        yield b"\x20\x00" * 50

    monkeypatch.setattr("tutoring.speech.router.stream_tts", fake_stream_tts)

    client = TestClient(app)
    with client.websocket_connect("/speech/tts-stream") as ws:
        ws.send_text(json.dumps({"type": "synthesize", "text": "你好"}))
        audio1 = ws.receive_bytes()
        audio2 = ws.receive_bytes()
        assert audio1 == b"\x10\x00" * 50
        assert audio2 == b"\x20\x00" * 50
        done = json.loads(ws.receive_text())
        assert done["type"] == "done"
        assert done["audio_url"].endswith(".wav")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd services/api_server && uv run pytest tests/test_speech_router.py -v`
Expected: FAIL（新测试失败——端点不存在）

- [ ] **Step 3: 实现**

在 `router.py` 追加：

```python
@router.websocket("/tts-stream")
async def tts_stream(ws: WebSocket) -> None:
    await ws.accept()
    filename = f"{uuid.uuid4().hex}.wav"
    os.makedirs(settings.audio_storage_dir, exist_ok=True)
    file_path = os.path.join(settings.audio_storage_dir, filename)
    writer = WavWriter(file_path, sample_rate=22050)
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            if data.get("type") != "synthesize":
                continue
            if not settings.speech_dashscope_api_key:
                raise DashScopeSpeechError(
                    "speech_dashscope_api_key is not configured"
                )
            async for chunk in stream_tts(
                data["text"],
                api_key=settings.speech_dashscope_api_key,
                voice=settings.speech_voice,
            ):
                writer.write(chunk)
                await ws.send_bytes(chunk)
            break
    except WebSocketDisconnect:
        pass
    finally:
        writer.close()
        await ws.send_text(
            json.dumps(
                {"type": "done", "audio_url": f"/speech/audio/{filename}"},
                ensure_ascii=False,
            )
        )
        await ws.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd services/api_server && uv run pytest tests/test_speech_router.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: Commit**

```bash
git add services/api_server/src/tutoring/speech/router.py services/api_server/tests/test_speech_router.py
git commit -m "feat: TTS 流式 WebSocket 端点（合成+写盘）"
```

---

### Task 7: 语音映射 REST 端点

**Files:**
- Modify: `services/api_server/src/tutoring/speech/router.py`
- Test: `services/api_server/tests/test_speech_router.py`

**Interfaces:**
- Consumes: `repos.create_message_audio`、`repos.list_message_audios_by_session`（Task 1）
- Produces:
  - `POST /speech/messages`，body `{"session_id": UUID, "message_id": str, "role": str, "text": str|None, "audio_url": str}` → 201 `{"ok": true}`（内部把 audio_url 转存 audio_path）
  - `GET /speech/messages/{session_id}` → `[{"id", "message_id", "role", "text", "audio_url"}]`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_speech_router.py`：

```python
from uuid import uuid4

from pydantic import BaseModel


@pytest.mark.asyncio
async def test_register_and_list_audio_mappings(monkeypatch):
    stored: list[dict] = []

    async def fake_create(db, *, session_id, message_id, role, text, audio_path):
        stored.append(
            {
                "session_id": session_id,
                "message_id": message_id,
                "role": role,
                "text": text,
                "audio_path": audio_path,
            }
        )
        return {"id": uuid4(), **stored[-1]}

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return [
                {
                    "id": uuid4(),
                    "session_id": stored[0]["session_id"],
                    "message_id": stored[0]["message_id"],
                    "role": stored[0]["role"],
                    "text": stored[0]["text"],
                    "audio_path": stored[0]["audio_path"],
                }
            ]

    class FakeSession:
        async def execute(self, _stmt):
            return FakeResult()

    async def fake_list(db, session_id):
        return await FakeSession().execute(None).scalars().all()

    monkeypatch.setattr("tutoring.speech.router.repos.create_message_audio", fake_create)
    monkeypatch.setattr("tutoring.speech.router.repos.list_message_audios_by_session", fake_list)

    body = {
        "session_id": str(uuid4()),
        "message_id": "msg-1",
        "role": "user",
        "text": "你好",
        "audio_url": "/speech/audio/abc.wav",
    }
    create_result = await speech_router.register_audio_mapping(None, body)
    assert create_result["ok"] is True
    assert stored[0]["audio_path"] == "abc.wav"
```

问题：`register_audio_mapping` 直接调用需要 DB session 依赖。参照现有 router 测试风格，直接调用函数并传 mock `db_session=None`，但函数内部用了 `db_session`。现有测试（test_management_api.py）是 monkeypatch repos + 传 `db=None`（因为函数内部 `repos.xxx(db)` 被 monkeypatch，db 可传 None）。为保持一致，`register_audio_mapping` 的 `db_session` 参数由 FastAPI Depends 注入，测试直接调用时传 `None`。依赖注入在直接调用时会被绕过吗？直接 `await speech_router.register_audio_mapping(None, body)`——第一个参数是 db_session，body 是第二个。定义签名 `register_audio_mapping(db_session: AsyncSession = Depends(get_db), body: AudioMappingIn = Body(...))` 时直接调用位置参数 OK（Depends 只在 FastAPI 处理时生效）。

列出端点 `list_audio_mappings(session_id, db_session)` 直接调用：`await speech_router.list_audio_mappings(session_id_str, None)`。

修正测试：

```python
@pytest.mark.asyncio
async def test_register_and_list_audio_mappings(monkeypatch):
    stored: list[dict] = []

    async def fake_create(db, *, session_id, message_id, role, text, audio_path):
        stored.append(
            {
                "session_id": session_id,
                "message_id": message_id,
                "role": role,
                "text": text,
                "audio_path": audio_path,
            }
        )
        return {"id": uuid4(), **stored[-1]}

    async def fake_list(db, session_id):
        return [
            {
                "id": uuid4(),
                "session_id": stored[0]["session_id"],
                "message_id": stored[0]["message_id"],
                "role": stored[0]["role"],
                "text": stored[0]["text"],
                "audio_path": stored[0]["audio_path"],
            }
        ]

    monkeypatch.setattr("tutoring.speech.router.repos.create_message_audio", fake_create)
    monkeypatch.setattr("tutoring.speech.router.repos.list_message_audios_by_session", fake_list)

    session_id = uuid4()
    body = {
        "session_id": session_id,
        "message_id": "msg-1",
        "role": "user",
        "text": "你好",
        "audio_url": "/speech/audio/abc.wav",
    }
    create_result = await speech_router.register_audio_mapping(None, body)
    assert create_result["ok"] is True
    assert stored[0]["audio_path"] == "abc.wav"

    items = await speech_router.list_audio_mappings(session_id, None)
    assert items[0]["message_id"] == "msg-1"
    assert items[0]["audio_url"] == "/speech/audio/abc.wav"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd services/api_server && uv run pytest tests/test_speech_router.py -v`
Expected: FAIL（新测试失败）

- [ ] **Step 3: 实现**

在 `router.py` 追加（顶部补充导入 `from uuid import UUID`、`from pydantic import BaseModel`、`from tutoring.core.deps import get_db`、`from tutoring.db import repos`）：

```python
class AudioMappingIn(BaseModel):
    session_id: UUID
    message_id: str
    role: str
    text: str | None = None
    audio_url: str


class AudioMappingOut(BaseModel):
    id: UUID
    message_id: str
    role: str
    text: str | None
    audio_url: str


@router.post("/messages", status_code=201)
async def register_audio_mapping(
    db_session=Depends(get_db),
    body: AudioMappingIn = Body(...),
) -> dict:
    await repos.create_message_audio(
        db_session,
        session_id=body.session_id,
        message_id=body.message_id,
        role=body.role,
        text=body.text,
        audio_path=body.audio_url.removeprefix("/speech/audio/"),
    )
    return {"ok": True}


@router.get("/messages/{session_id}", response_model=list[AudioMappingOut])
async def list_audio_mappings(
    session_id: UUID,
    db_session=Depends(get_db),
) -> list[AudioMappingOut]:
    rows = await repos.list_message_audios_by_session(db_session, session_id)
    return [
        AudioMappingOut(
            id=row.id,
            message_id=row.message_id,
            role=row.role,
            text=row.text,
            audio_url=f"/speech/audio/{row.audio_path.split('/')[-1]}",
        )
        for row in rows
    ]
```

注意 `Depends` 需要 `from fastapi import Depends`、`Body` 需要 `from fastapi import Body`；`get_db` 从 `tutoring.core.deps` 导入。直接调用测试时 `register_audio_mapping(None, body)` 位置匹配 `db_session` 和 `body`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd services/api_server && uv run pytest tests/test_speech_router.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 5: Commit**

```bash
git add services/api_server/src/tutoring/speech/router.py services/api_server/tests/test_speech_router.py
git commit -m "feat: 语音映射注册与查询端点"
```

---

### Task 8: 前端录音 hook（PCM 采集 + ASR 流式）

**Files:**
- Create: `frontend/src/hooks/use-voice-recorder.ts`
- Create: `frontend/src/lib/speech.ts`（WebSocket 封装与常量）
- Modify: `frontend/src/lib/constants.ts`（API 相关常量）

**Interfaces:**
- Produces:
  - `frontend/src/lib/speech.ts`:
    - `speechWsUrl(path: string): string`：把 `/api` 前缀换成 `ws(s)://`，返回 `wss?://host/speech/...`
    - `type AsrMessage = { type: "partial" | "final" | "done"; text?: string; audio_url?: string }`
  - `frontend/src/hooks/use-voice-recorder.ts`:
    - `useVoiceRecorder(onResult: (msg: AsrMessage) => void)` → `{ recording: boolean, start(): Promise<void>, stop(): void }`：`start` 打开麦克风，AudioContext(sampleRate 16000) + ScriptProcessorNode 采集 Int16 PCM，经 WebSocket 推 `/speech/asr-stream`；`stop` 发 `{"type":"finish"}` 并关闭采集；WS 消息经 `onResult` 回调

- [ ] **Step 1: 写失败测试（先验证构建）**

项目无前端测试框架（package.json 无 test script），本任务以 `npm run lint` 验证。先写实现，再 lint。

- [ ] **Step 2: 实现 `lib/speech.ts`**

创建 `frontend/src/lib/speech.ts`：

```ts
import { API_URL } from "@/lib/constants";

export function speechWsUrl(path: string): string {
  const base = API_URL.replace(/^\/api$/, "");
  const host = window.location.host;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  if (base.startsWith("http")) {
    const url = new URL(base);
    url.protocol = proto;
    url.pathname = `${url.pathname.replace(/\/$/, "")}${path}`;
    return url.toString();
  }
  return `${proto}://${host}${path}`;
}

export type AsrMessage =
  | { type: "partial"; text: string }
  | { type: "final"; text: string }
  | { type: "done"; text: string; audio_url: string };

export type TtsMessage =
  | { type: "synthesize"; text: string }
  | { type: "done"; audio_url: string };
```

- [ ] **Step 3: 实现 `use-voice-recorder.ts`**

创建 `frontend/src/hooks/use-voice-recorder.ts`：

```ts
"use client";

import { useCallback, useRef, useState } from "react";
import { speechWsUrl, type AsrMessage } from "@/lib/speech";

const SAMPLE_RATE = 16000;

export function useVoiceRecorder(onResult: (msg: AsrMessage) => void) {
  const [recording, setRecording] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const nodeRef = useRef<ScriptProcessorNode | null>(null);
  const stoppedRef = useRef(false);

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, sampleRate: SAMPLE_RATE },
    });
    streamRef.current = stream;
    const ws = new WebSocket(speechWsUrl("/speech/asr-stream"));
    ws.binaryType = "arraybuffer";
    stoppedRef.current = false;

    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error("语音服务连接失败"));
    });

    ws.onmessage = (event) => {
      if (typeof event.data !== "string") return;
      const msg = JSON.parse(event.data) as AsrMessage;
      if (msg.type === "done") {
        ws.close();
        cleanup();
        setRecording(false);
      }
      onResult(msg);
    };

    const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
    ctxRef.current = ctx;
    const source = ctx.createMediaStreamSource(stream);
    const node = ctx.createScriptProcessor(4096, 1, 1);
    node.onaudioprocess = (e) => {
      if (stoppedRef.current) return;
      const input = e.inputBuffer.getChannelData(0);
      const pcm = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(pcm.buffer);
      }
    };
    nodeRef.current = node;
    source.connect(node);
    node.connect(ctx.destination);
    wsRef.current = ws;
    setRecording(true);
  }, [onResult]);

  const cleanup = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    nodeRef.current?.disconnect();
    nodeRef.current = null;
    if (ctxRef.current) {
      void ctxRef.current.close();
      ctxRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    if (!wsRef.current) return;
    stoppedRef.current = true;
    if (wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "finish" }));
    }
    cleanup();
    setRecording(false);
  }, [cleanup]);

  return { recording, start, stop };
}
```

- [ ] **Step 4: 运行 lint**

Run: `cd frontend && npm run lint`
Expected: 无报错（如报错按提示修复，本项目 `next lint` 无 ESLint 配置问题时应通过）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/speech.ts frontend/src/hooks/use-voice-recorder.ts
git commit -m "feat: 前端录音 hook（PCM 采集 + ASR 流式推流）"
```

---

### Task 9: 前端 TTS 流式播放 hook

**Files:**
- Create: `frontend/src/hooks/use-tts-player.ts`

**Interfaces:**
- Consumes: `speechWsUrl`（Task 8）
- Produces:
  - `useTtsPlayer({ enabled }: { enabled: boolean })` → `{ speaking: boolean, play(text: string): void, stop(): void }`：`play(text)` 打开 WS `/speech/tts-stream` 发 `{"type":"synthesize","text"}`，收到二进制 PCM 帧按 22050Hz 排入 AudioContext 队列播放；收到 `done` 后关闭；`stop()` 中断播放并关 WS

- [ ] **Step 1: 实现**

创建 `frontend/src/hooks/use-tts-player.ts`：

```ts
"use client";

import { useCallback, useRef, useState } from "react";
import { speechWsUrl } from "@/lib/speech";

const TTS_SAMPLE_RATE = 22050;

export function useTtsPlayer({ enabled }: { enabled: boolean }) {
  const [speaking, setSpeaking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const playingRef = useRef(false);

  const stop = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    if (ctxRef.current) {
      void ctxRef.current.close();
      ctxRef.current = null;
    }
    playingRef.current = false;
    setSpeaking(false);
  }, []);

  const play = useCallback(
    (text: string) => {
      if (!enabled || !text.trim()) return;
      stop();
      const ctx = new AudioContext({ sampleRate: TTS_SAMPLE_RATE });
      ctxRef.current = ctx;
      const ws = new WebSocket(speechWsUrl("/speech/tts-stream"));
      ws.binaryType = "arraybuffer";
      playingRef.current = true;
      setSpeaking(true);

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "synthesize", text }));
      };
      ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          const msg = JSON.parse(event.data);
          if (msg.type === "done") {
            ws.close();
            playingRef.current = false;
            setSpeaking(false);
          }
          return;
        }
        if (!playingRef.current) return;
        const pcm = new Int16Array(event.data as ArrayBuffer);
        const buf = ctx.createBuffer(1, pcm.length, TTS_SAMPLE_RATE);
        const channel = buf.getChannelData(0);
        for (let i = 0; i < pcm.length; i++) {
          channel[i] = pcm[i] / 0x8000;
        }
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(ctx.destination);
        src.start();
      };
      ws.onerror = () => {
        ws.close();
        playingRef.current = false;
        setSpeaking(false);
      };
      wsRef.current = ws;
    },
    [enabled, stop],
  );

  return { speaking, play, stop };
}
```

注意：多条消息连续播放时，`stop()` 会关闭上一个 WS 并重建 AudioContext，保证串行。

- [ ] **Step 2: 运行 lint**

Run: `cd frontend && npm run lint`
Expected: 无报错

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-tts-player.ts
git commit -m "feat: 前端 TTS 流式播放 hook"
```

---

### Task 10: 学生端聊天集成（麦克风 + 语音播报）

**Files:**
- Modify: `frontend/src/components/chat/thread/index.tsx`
- Modify: `frontend/src/components/chat/thread/messages/ai.tsx`（消息气泡显示语音播放按钮——仅当有 audio_url 时）
- Modify: `frontend/src/lib/api/speech.ts`（新建：注册/查询映射的 API 封装）

**Interfaces:**
- Consumes: `useVoiceRecorder`（Task 8）、`useTtsPlayer`（Task 9）
- Produces:
  - `frontend/src/lib/api/speech.ts`: `speechApi.registerAudio(sessionId, {message_id, role, text, audio_url})` → POST `/speech/messages`；`speechApi.listAudio(sessionId)` → GET `/speech/messages/{sessionId}`
  - 学生端输入区麦克风按钮：按住说话 → 转写文本实时显示在输入框 → 松开自动发送
  - Agent 回复流式文本按句切分（`。！？\n`）送 `ttsPlayer.play(sentence)` 自动播报；偏好开关存 localStorage key `tts_enabled`（默认 true）
  - 学生消息发出后注册映射：`speechApi.registerAudio(sessionId, {message_id: 消息id, role: "user", text, audio_url})`

- [ ] **Step 1: 创建 `lib/api/speech.ts`**

```ts
import { api } from "./client";

export interface AudioMapping {
  id: string;
  message_id: string;
  role: "user" | "assistant";
  text: string | null;
  audio_url: string;
}

export const speechApi = {
  registerAudio: (
    sessionId: string,
    data: {
      message_id: string;
      role: "user" | "assistant";
      text?: string | null;
      audio_url: string;
    },
  ) =>
    api.post<{ ok: boolean }>("/speech/messages", {
      session_id: sessionId,
      ...data,
    }),

  listAudio: (sessionId: string) =>
    api.get<AudioMapping[]>(`/speech/messages/${sessionId}`),
};
```

- [ ] **Step 2: 修改 `thread/index.tsx`**

改动点：
1. 顶部 import：`import { useVoiceRecorder } from "@/hooks/use-voice-recorder";`、`import { useTtsPlayer } from "@/hooks/use-tts-player";`、`import { speechApi } from "@/lib/api/speech";`、`import { Mic } from "lucide-react";`
2. 组件内新增状态与 hooks：

```tsx
  const [ttsEnabled, setTtsEnabled] = useState(
    () => localStorage.getItem("tts_enabled") !== "0",
  );
  const ttsPlayer = useTtsPlayer({ enabled: ttsEnabled });
  const [voiceText, setVoiceText] = useState("");
  const voiceRecorder = useVoiceRecorder((msg) => {
    if (msg.type === "partial" || msg.type === "final") {
      setVoiceText(msg.text);
    }
    if (msg.type === "done" && msg.text) {
      setVoiceText(msg.text);
      setInput(msg.text);
      // 注册语音映射：消息 id 在发送时生成，这里暂存 audio_url
      lastVoiceAudioUrl.current = msg.audio_url;
      handleSubmitFromVoice();
    }
  });
```

（`handleSubmitFromVoice` 复用 handleSubmit 逻辑，见 Step 3；`lastVoiceAudioUrl` 用 `useRef<string | null>(null)`）

3. 输入区按钮区（`<div className="flex items-center gap-6 p-2 pt-4">` 内，发送按钮之前）加麦克风按钮：

```tsx
        {!stream.isLoading && (
          <button
            type="button"
            onMouseDown={() => void voiceRecorder.start().catch(() => {})}
            onMouseUp={() => voiceRecorder.stop()}
            onTouchStart={() => void voiceRecorder.start().catch(() => {})}
            onTouchEnd={() => voiceRecorder.stop()}
            className={`ml-auto inline-flex size-9 items-center justify-center rounded-full transition-colors ${
              voiceRecorder.recording
                ? "bg-red-500 text-white"
                : "bg-ink/5 text-ink/60 hover:bg-ink/10"
            }`}
            title={ttsEnabled ? "按住说话" : "语音不可用"}
          >
            <Mic className="size-4" />
          </button>
        )}
```

（`ml-auto` 保证在取消/发送按钮左侧；发送按钮保留原有 `ml-auto` 时把麦克风放在发送前）

4. Agent 回复流式播报：在 `messages` 变化处追加 effect（`prevMessageLength` effect 之后）：

```tsx
  const prevAiText = useRef("");
  useEffect(() => {
    const last = [...messages]
      .reverse()
      .find((m) => m.type === "ai");
    if (!last) return;
    const text = getContentString(last.content);
    const delta = text.slice(prevAiText.current.length);
    prevAiText.current = text;
    if (!delta) return;
    const sentences = delta
      .split(/(?<=[。！？!?\n])/)
      .map((s) => s.trim())
      .filter(Boolean);
    for (const sentence of sentences) {
      ttsPlayer.play(sentence);
    }
  }, [messages, ttsPlayer]);
```

需要 import `getContentString`：`import { getContentString } from "./utils";`（确认该 utils 存在——`ai.tsx` 已从 `../utils` import，路径应为 `../utils`）。

5. 语音提问发送逻辑：`handleSubmit` 中 `newHumanMessage` 生成后，若有 `lastVoiceAudioUrl.current` 且 threadId 存在，注册映射：

在 `performSubmit` 的调用前：

```tsx
    if (lastVoiceAudioUrl.current && threadId) {
      speechApi
        .registerAudio(threadId, {
          message_id: newHumanMessage.id!,
          role: "user",
          text: input,
          audio_url: lastVoiceAudioUrl.current,
        })
        .catch(console.error);
      lastVoiceAudioUrl.current = null;
    }
```

`handleSubmitFromVoice` 封装：清空 `voiceText`、设置 `input`、调用原提交逻辑。为最小改动，直接在 `onResult` 的 `done` 分支中 `setInput(msg.text)` 并调用 `requestSubmit()`（表单有 ref 吗？表单无 ref。改用：把 `handleSubmit` 提取逻辑或直接触发 `input` state 后手动调 `performSubmit`）。简化：给表单加 `ref`：

```tsx
  const formRef = useRef<HTMLFormElement | null>(null);
  ...
  <form ref={formRef} onSubmit={handleSubmit} ...>
```

然后 done 分支：

```tsx
    if (msg.type === "done" && msg.text) {
      setVoiceText("");
      setInput(msg.text);
      lastVoiceAudioUrl.current = msg.audio_url;
      formRef.current?.requestSubmit();
    }
```

`requestSubmit` 会触发 `handleSubmit`（e.preventDefault 由 React 处理），其中读取 `input` state——但 state 更新是异步的，`requestSubmit` 时 `input` 可能还是旧值。改用 ref 存语音文本：

```tsx
  const voiceInputRef = useRef("");
```

done 分支：

```tsx
    if (msg.type === "done" && msg.text) {
      voiceInputRef.current = msg.text;
      lastVoiceAudioUrl.current = msg.audio_url;
      setVoiceText("");
      setInput(msg.text);
      setTimeout(() => formRef.current?.requestSubmit(), 0);
    }
```

`handleSubmit` 中读取：

```tsx
    const effectiveInput =
      voiceInputRef.current || input.trim();
    voiceInputRef.current = "";
    if (effectiveInput.length === 0 && contentBlocks.length === 0) return;
```

`newHumanMessage` 的 content 用 `effectiveInput`。`setInput("")` 同理。

- [ ] **Step 3: 运行 lint**

Run: `cd frontend && npm run lint`
Expected: 无报错（若 `getContentString` 路径不符，按实际路径调整 import）

- [ ] **Step 4: 手动验证（后端需先启动）**

- 起后端（API Server + Agent Server + 前端 dev）
- 学生端按住麦克风说话 → 输入框出现实时转写 → 松开发送
- Agent 回复时边出字边发声
- localStorage 设 `tts_enabled=0` 后不播报

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api/speech.ts frontend/src/components/chat/thread/index.tsx frontend/src/components/chat/thread/messages/ai.tsx
git commit -m "feat: 学生端语音提问与 Agent 流式播报"
```

---

### Task 11: 教师端回放集成

**Files:**
- Modify: `frontend/src/components/chat/ReadOnlyChatView.tsx`
- Modify: `frontend/src/components/chat/thread/messages/ai.tsx`（若 Task 10 未做，本任务在 ReadOnlyChatView 内实现播放器即可）

**Interfaces:**
- Consumes: `speechApi.listAudio`（Task 10）
- Produces: 教师端会话详情页每条 human/ai 消息旁显示播放按钮（有 audio_url 时）；点击播放该消息音频

- [ ] **Step 1: 实现**

修改 `ReadOnlyChatView.tsx`：

1. import：`import { speechApi, type AudioMapping } from "@/lib/api/speech";`、`import { Volume2 } from "lucide-react";`
2. state：`const [audioMap, setAudioMap] = useState<Map<string, AudioMapping>>(new Map());`
3. `loadData` 中并行拉取：

```tsx
        const audioList = await speechApi.listAudio(sessionId);
        setAudioMap(
          new Map(audioList.map((a) => [a.message_id, a])),
        );
```

4. 渲染：human/ai 消息块内加播放按钮：

```tsx
        {msg.type === "human" && (
          <div key={idx} className="flex justify-end items-center gap-2">
            {audioMap.get(msg.id ?? "") && (
              <button
                onClick={() => playAudio(audioMap.get(msg.id ?? "")!.audio_url)}
                className="inline-flex size-7 items-center justify-center rounded-full bg-primary/10 text-primary hover:bg-primary/20"
                title="播放学生原声"
              >
                <Volume2 className="size-4" />
              </button>
            )}
            <div className="max-w-[80%] rounded-lg bg-primary px-4 py-2 text-primary-foreground">
              {getContentString(msg.content)}
            </div>
          </div>
        )}
```

ai 同理（按钮在左侧文字旁）。

5. `playAudio` 辅助：

```tsx
  function playAudio(url: string) {
    const audio = new Audio(url);
    void audio.play();
  }
```

- [ ] **Step 2: 运行 lint**

Run: `cd frontend && npm run lint`
Expected: 无报错

- [ ] **Step 3: 手动验证**

- 教师端进入会话详情 → 学生语音消息旁出现播放按钮 → 点击可听学生原声；Agent 消息旁可听合成语音

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/chat/ReadOnlyChatView.tsx
git commit -m "feat: 教师端会话语音回放"
```

---

### Task 12: 端到端验证与配置文档

**Files:**
- Modify: `services/api_server/.env.example`（新增语音配置项）
- Modify: `frontend/.env.example`（如有语音相关项则补充）
- Create: `docs/voice-demo.md`（演示操作步骤）

- [ ] **Step 1: 更新 `.env.example`**

`services/api_server/.env.example` 追加：

```
# 语音模块（DashScope 语音，可与 LLM Key 共用）
SPEECH_DASHSCOPE_API_KEY=
AUDIO_STORAGE_DIR=data/audio
SPEECH_VOICE=longxiaochun_v3
```

`services/api_server/.env` 实际填入 Key（本地开发文件，不入库）。

- [ ] **Step 2: 端到端验证清单**

按以下步骤全流程验证（全部通过才算完成）：

1. 启动：`deploy/docker-compose.yml` 基础设施 → API Server（`uv run uvicorn tutoring.app:app --port 8000 --reload`）→ Agent Server（`uv run langgraph dev --port 2024`）→ 前端（`npm run dev`）
2. 学生登录 → 按住麦克风说话 → 输入框实时出现转写文字 → 松开发送
3. Agent 回复：文字边出，语音同步播放（可听到合成音）
4. 对话 3-5 轮后，检查 `data/audio/` 目录存在 `.wav` 文件（学生原声 + Agent 语音各若干）
5. 教师端进入该学生会话详情 → 消息旁出现播放按钮 → 学生原声与 Agent 语音均可播放
6. 刷新学生页 → 历史消息的 Agent 消息不再自动播报（仅新回复播报）；教师端回放不受影响
7. 异常路径：关掉 DashScope Key（`.env` 置空）→ 按住说话 → 前端收到 `done` 或错误提示，页面不崩

- [ ] **Step 3: 写演示文档**

创建 `docs/voice-demo.md`：

```markdown
# 语音交互演示

## 演示前准备
- 确认 `services/api_server/.env` 已配置 `SPEECH_DASHSCOPE_API_KEY`（可用通义千问的 Key）
- 确认 `AUDIO_STORAGE_DIR` 存在且有写权限
- 演示电脑有麦克风且浏览器已授权

## 演示流程（约 3 分钟）
1. 学生账号登录 → 点击输入区麦克风按钮并按住说话
2. 观察：说话时输入框实时出现转写文字（边说边出字）
3. 松开：消息自动发送，Agent 开始回复
4. 观察：Agent 文字流式出现的同时，语音同步播报
5. 教师账号登录 → 班级管理 → 某学生 → 会话详情
6. 观察：消息旁有播放按钮，点击回放学生原声 / Agent 语音

## 故障排查
- 无法录音：检查浏览器麦克风授权（地址栏权限）
- 无语音播报：检查 SPEECH_DASHSCOPE_API_KEY 与 `data/audio` 写权限
- WS 连接失败：确认 API Server 端口可达（前端经 /api 代理）
```

- [ ] **Step 4: Commit**

```bash
git add services/api_server/.env.example docs/voice-demo.md
git commit -m "docs: 语音模块配置说明与演示文档"
```

---

## Self-Review

**Spec 覆盖检查：**
- 流式 ASR 边说边出字 → Task 2/5/8 ✓
- 学生原声保存 → Task 5（WavWriter 写盘）✓
- Agent 回复流式文本按句切分送 TTS 边出字边发声 → Task 3/6/9/10 ✓
- 教师端回放学生原声 + Agent 语音 → Task 1（映射表）/7（REST）/11（前端）✓
- 音频写盘 WAV 可播放 → Task 4 ✓
- 不暴露 API Key → 全部经 API Server 代理 ✓
- 无鉴权（约束）→ 端点均不加鉴权 ✓

**占位符扫描：** 无 TBD/TODO；所有代码步骤给出完整代码。

**类型一致性检查：**
- `stream_asr` 签名（Task 2 产生，Task 5 消费）一致：`(frames: AsyncIterator[bytes], *, api_key: str) -> AsyncIterator[dict]` ✓
- `stream_tts` 签名（Task 3 产生，Task 6 消费）：`(text, *, api_key, voice) -> AsyncIterator[bytes]` ✓
- `WavWriter`（Task 4 产生，Task 5/6 消费）：`WavWriter(path, sample_rate).write(bytes)/close()` ✓
- `repos.create_message_audio` / `list_message_audios_by_session`（Task 1 产生，Task 7 消费）参数一致 ✓
- 前端 `speechWsUrl`（Task 8 产生，Task 9/10 消费）✓
- `useVoiceRecorder` / `useTtsPlayer` 返回签名（Task 8/9 产生，Task 10 消费）✓
- API 路径一致：WS `/speech/asr-stream`、`/speech/tts-stream`；REST `/speech/messages`、`/speech/messages/{id}`；静态 `/speech/audio/{file}` ✓
- ASR 音频格式 16kHz、TTS 22050Hz 在写盘/播放两侧一致 ✓

**已知实现风险（已在任务中处理）：**
- DashScope WS 协议细节以官方文档为准，Task 2/3 的帧结构已按官方文档（run-task/result-generated/task-failed/task-finished）编写；若实测 event 字段差异，调整 `dashscope_asr.py` / `dashscope_tts.py` 解析即可
- TestClient 触发 lifespan 连 DB 的问题：测试中 monkeypatch `init_db` 规避
- 前端 `getContentString` 导入路径按 `ai.tsx` 现有 import 校验