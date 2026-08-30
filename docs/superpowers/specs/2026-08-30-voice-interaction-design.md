# 语音交互模块设计

日期：2026-08-30
状态：已确认

## 背景

领导演示后反馈：系统"没有高级感、没有体现出智能化"。明确改进方向之一为**双向语音对话**：学生语音提问、Agent 语音播报，教师端可回放学生原声与 Agent 语音。UI 视觉不做改动。

约束：现场真机演示、无期限、无需考虑安全性问题（不引入鉴权/权限设计负担）。

## 技术选型

沿用阿里云 DashScope（项目已用于通义千问，同一 API Key 生态）：

| 环节 | 服务 | 模型 |
| --- | --- | --- |
| 语音识别 ASR | DashScope Paraformer | `paraformer-realtime-v2`（非流式 `call` 即可，录音完成后整段转写） |
| 语音合成 TTS | DashScope CosyVoice | `cosyvoice-v3-flash`（系统音色，如 `longanyang`） |
| 音频存储 | API Server 本地磁盘 | 数据库存路径，静态挂载直接提供 |

不暴露 DashScope API Key 给前端：前端只与 API Server 交互，ASR/TTS 由 API Server 代理调用。

## 架构

```
学生前端 ──(录音上传 webm/opus)──▶ API Server /speech/upload
    │                                 │ 1. 保存原声到本地磁盘
    │                                 │ 2. 调 Paraformer 转写
    │                                 │ 3. 返回 {text, audio_url}
    │
    │──(文字消息)──▶ Agent Server (LangGraph) 流式回复
    │
    │──(回复完成后)──▶ API Server /speech/tts ──▶ CosyVoice 合成
    │                     └── 返回 audio_url → 前端自动播放（可开关）
```

### 数据流：一次语音提问的完整链路

1. 学生按住/点击麦克风录音（MediaRecorder，webm/opus）
2. 录音结束 → 上传 `POST /speech/upload`（multipart）
3. API Server 保存原声文件到磁盘 → 调 Paraformer 非流式转写 → 返回 `{text, audio_url}`
4. 前端把 `text` 作为消息发送给 Agent（LangGraph SDK），并记录本轮消息 id
5. Agent 流式回复完成后，前端调 `POST /speech/tts {text}` → CosyVoice 合成 → 返回 audio_url → 前端自动播放（用户可关闭，偏好存 localStorage）
6. 前端将 `{session_id, message_id, role, text, audio_path}` 注册到 `POST /sessions/{id}/audio`
7. 教师端读会话时 `GET /sessions/{id}/audio` 拉取全部语音映射，按消息渲染播放器

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
| `POST /speech/upload` | multipart 接收录音 → 存原声 → ASR 转写 → 返回 `{text, audio_url}` |
| `POST /speech/tts` | body `{text}` → CosyVoice 合成 → 存文件 → 返回 `{audio_url}` |
| `POST /sessions/{id}/audio` | 注册消息与音频的映射 |
| `GET /sessions/{id}/audio` | 返回该会话全部语音映射 |
| 静态音频 | FastAPI 静态挂载音频目录，直接 URL 访问（不加鉴权） |

### 格式处理

- 前端 MediaRecorder 默认产出 webm/opus 容器
- Paraformer 支持 opus 编码流；若容器格式不被接受，后端用 ffmpeg 转 wav 16k 再识别
- Docker 镜像需安装 ffmpeg（部署文件同步更新）

### 配置新增（API Server `.env`）

- `DASHSCOPE_SPEECH_API_KEY`（与现有 LLM Key 可共用）
- `AUDIO_STORAGE_DIR`（本地磁盘目录，默认 `./data/audio`）

## 前端改动

**学生端（`/student/chat`）**
- 输入区新增麦克风按钮：录音 → 上传 → 转写文本发送
- Agent 消息气泡带音量图标；回复完成后自动播放语音（可关闭，偏好存 localStorage）
- 播放中显示进度/停止按钮

**教师端（`/teacher/manage/classes/[classId]/sessions/[sid]`）**
- 会话详情页：按 `message_audio` 映射，在学生消息和 Agent 消息旁渲染播放按钮（学生原声、Agent 语音），文字照常显示

## 测试方案

| 层 | 测试 |
| --- | --- |
| API Server | `speech` 模块单测：mock DashScope 客户端，验证上传→保存原声→转写→返回链路；`/sessions/{id}/audio` 增查链路 |
| 前端 | 手动验证：录音→转写→发送→自动播报→教师端回放 |
| 端到端 | 本地全栈手动验证语音闭环 |

## 实施顺序

1. 数据库迁移（`message_audio` 表）
2. API Server `speech` 模块（ASR + TTS + 音频映射端点 + 静态挂载）
3. 前端学生端录音/播报
4. 前端教师端回放
5. 测试与演示验证