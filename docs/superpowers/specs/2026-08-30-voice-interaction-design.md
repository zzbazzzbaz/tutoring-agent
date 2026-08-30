# 语音交互模块设计

日期：2026-08-30
状态：已确认（2026-08-30 更新为流式播报档位）

## 背景

领导演示后反馈：系统"没有高级感、没有体现出智能化"。明确改进方向之一为**双向语音对话**：学生语音提问、Agent 语音播报，教师端可回放学生原声与 Agent 语音。UI 视觉不做改动。

约束：现场真机演示、无期限、无需考虑安全性问题（不引入鉴权/权限设计负担）。

**交互档位：流式播报**（用户确认）
- 学生端流式 ASR：边说边出字，语音提问体验即时
- Agent 回复流式文本的同时，已生成的句子实时送 TTS，前端边出字边发声
- 不做全实时语音对话（Agent 工具检索期间有静默，演示反而不稳）

## 技术选型

沿用阿里云 DashScope（项目已用于通义千问，同一 API Key 生态）：

| 环节 | 服务 | 模型 | 延迟 |
| --- | --- | --- | --- |
| 语音识别 ASR | DashScope Qwen-Audio-3.0-ASR | `qwen-audio-3.0-asr-flash-streaming`（WebSocket 流式，边说边出字） | ~300ms 出字 |
| 语音合成 TTS | DashScope Qwen-Audio-TTS | `qwen-audio-3.0-tts-flash`（WebSocket 流式合成） | <200ms 首包 |
| 音频存储 | API Server 本地磁盘 | 数据库存路径，静态挂载直接提供 | — |

选型理由：
- ASR 用 streaming 版：官方为低延迟实时交互打造的旗舰模型，100ms 级分块解码、~300ms 出字，中文错字率 7.8%，支持热词与 Prompt 上下文（可注入课程领域背景）；教育场景专项优化（古诗词/文言、七大方言、标点与数字归一化）。
- TTS 用 flash 流式：首包 <200ms，第一个字产出即出音频；支持 LaTeX 公式转语音（数学题朗读）、指令控制方言/情感/角色。
- 端到端瓶颈在 Agent 推理（LLM + 工具调用 + 知识检索，首段文本约 2~8s），语音模型本身均亚秒级，Agent 思考期间前端显示"思考中"状态掩盖停顿。

不暴露 DashScope API Key 给前端：前端只与 API Server 交互，ASR/TTS 由 API Server 代理调用。

## 架构

```
学生前端 ──(录音流 WebSocket)──▶ API Server /speech/asr-stream
    │  ▲                          │ 1. 转发音频帧 → DashScope ASR 流式
    │  │ 识别中间结果             │ 2. 同时把音频帧写盘保存原声
    │  └──────────────────────────┤ 3. 说话结束返回 {text, audio_url}
    │
    │──(转写文本)──▶ Agent Server (LangGraph) 流式回复文本
    │
    │──(回复文本流)──▶ API Server /speech/tts-stream (WebSocket)
    │                     ▲  │ 1. 按句切分送 DashScope TTS 流式合成
    │                     │  │ 2. 音频帧回传前端播放（边出字边发声）
    │                     │  │ 3. 同时写盘，结束返回 audio_url
    │                     └──┘
```

### 数据流：一次语音提问的完整链路

1. 学生按住麦克风说话，录音流经 WebSocket `WS /speech/asr-stream` 推给 API Server
2. API Server 边转发音频帧给 DashScope ASR 流式识别，边把音频帧写盘（学生原声）
3. ASR 中间结果实时回传前端显示（边说边出字）；学生说完（松手/点停止）→ API Server 结束识别 → 返回 `{text, audio_url}`
4. 前端把 `text` 作为消息发送给 Agent（LangGraph SDK），并记录本轮消息 id
5. Agent 流式回复文本 → 前端按句切分（句号/问号/换行），完整句子经 `WS /speech/tts-stream` 送 API Server
6. API Server 转发 DashScope TTS 流式合成 → 音频帧回传前端播放（边出字边发声），同时写盘
7. Agent 回复结束 → API Server 返回完整 audio_url
8. 前端注册语音映射：`POST /sessions/{id}/audio`（学生原声 → user 消息 id，Agent 语音 → assistant 消息 id）
9. 教师端读会话时 `GET /sessions/{id}/audio` 拉取全部映射，按消息渲染播放器

## 数据库变更

新表 `message_audio`：

```
message_audio
├── id            UUID PK
├── session_id    UUID FK → session.id（索引）
├── message_id    LangGraph 消息 id（string）
├── role          user / assistant
├── text          转写文本或合成文本
├── audio_path    磁盘相对路径
└── created_at    timestamp
```

## API Server 新增 `speech` 模块

| 端点 | 说明 |
| --- | --- |
| `WS /speech/asr-stream` | 双向流式：接收前端音频帧 → 转发 DashScope ASR 流式 + 写盘保存原声 → 回传识别中间/最终结果，结束时返回 `{text, audio_url}` |
| `WS /speech/tts-stream` | 双向流式：接收按句切分的文本 → 转发 DashScope TTS 流式 → 音频帧回传前端 + 写盘，结束时返回 `{audio_url}` |
| `POST /sessions/{id}/audio` | 注册消息与音频的映射 |
| `GET /sessions/{id}/audio` | 返回该会话全部语音映射 |
| 静态音频 | FastAPI 静态挂载音频目录，直接 URL 访问（不加鉴权） |

### 格式处理

- 流式 ASR 支持 pcm/wav/mp3/opus 二进制流；前端优先用 Web Audio API 取 PCM 16k 16bit 单声道推帧（兼容性最稳），备选 MediaRecorder opus 流（实现时验证）
- TTS 流式输出音频格式：实现时验证 pcm 或 mp3/opus；若用 PCM，前端经 Web Audio API（AudioContext）播放

### 配置新增（API Server `.env`）

- `DASHSCOPE_SPEECH_API_KEY`（与现有 LLM Key 可共用）
- `AUDIO_STORAGE_DIR`（本地磁盘目录，默认 `./data/audio`）

## 前端改动

**学生端（`/student/chat`）**
- 输入区新增麦克风按钮：按住说话 → 录音流推 ASR → 边说边显示转写文字 → 松手发送
- Agent 消息流式回复：文字边出边把完整句子送 TTS，同步语音播放（可关闭，偏好存 localStorage）
- 播放中显示进度/停止按钮；Agent 思考期间显示"思考中"状态

**教师端（`/teacher/manage/classes/[classId]/sessions/[sid]`）**
- 会话详情页：按 `message_audio` 映射，在学生消息和 Agent 消息旁渲染播放按钮（学生原声、Agent 语音），文字照常显示

## 测试方案

| 层 | 测试 |
| --- | --- |
| API Server | `speech` 模块单测：mock DashScope 客户端，验证流式转发/写盘/结果回传链路；`/sessions/{id}/audio` 增查链路 |
| 前端 | 手动验证：语音说话→边出字→发送→Agent 回复边出字边发声→教师端回放 |
| 端到端 | 本地全栈手动验证语音闭环，重点验证流式播放无卡顿、写盘完整 |

## 实施顺序

1. 数据库迁移（`message_audio` 表）
2. API Server `speech` 模块（ASR 流式代理 + TTS 流式代理 + 音频映射端点 + 静态挂载）
3. 前端学生端录音/流式播报
4. 前端教师端回放
5. 测试与演示验证