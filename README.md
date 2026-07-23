## 启动命令

cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/services/api_server"
uv run uvicorn tutoring.app:app --host 127.0.0.1 --port 8000 --reload

cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/services/agent_server"
uv run langgraph dev --host 127.0.0.1 --port 2024

cd "/Volumes/ExternalStorageA/project/2026.7/教学Agent/frontend"
npm run dev

## TODO

- 知识库图谱界面当前存在编辑入口，但业务后端尚未适配实体/关系编辑 API；需要改为真正只读，或补齐后端代理与权限控制。
- 前端当前直接迁入 LightRAG WebUI 源码，依赖和组件边界偏重；需要整理代码质量，隔离 vendor 代码、清理未用模块并收敛适配层。
