# Docker Compose

`docker-compose.yml` 与 `docker-compose-prod.yml` 完全独立：前者用于本地开发基础设施，后者用于生产完整部署。生产服务间使用 Compose DNS 通信，不使用 `localhost`。

| 服务 | 容器内职责 | 默认宿主机端口 |
| --- | --- | --- |
| `postgres` | API 与 LangGraph 持久化数据库 | 15423 |
| `neo4j` | LightRAG 图数据库 | 17457 / 17864 |
| `lightrag` | 课程知识检索 | 19621 |
| `api_server` | 业务 API 与用户/会话授权 | 8000 |
| `langgraph_redis` | LangGraph Server 队列协调 | 不暴露 |
| `agent_server` | LangGraph API、checkpoint、thread 与 run | 2024 |

## 本地开发基础设施

```bash
cd deploy
docker compose up -d
```

该命令只启动 `postgres`、`neo4j` 和 `lightrag`；API Server 与 Agent Server 分别在本机以热重载方式启动。

## 生产部署

```bash
cd deploy
cp .env.example .env
# 编辑 .env，填入真实密钥和强密码
docker compose -f docker-compose-prod.yml up -d --build
```

Agent Server 使用 PostgreSQL 数据库 `tutoring_agent_server_db` 持久化 checkpoint、store、thread 与 run；初始化脚本会在新 PostgreSQL volume 上自动创建该数据库。

## 查看部署状态

```bash
docker compose ps
docker compose logs -f lightrag

docker compose -f docker-compose-prod.yml ps
docker compose -f docker-compose-prod.yml logs -f agent_server
docker compose -f docker-compose-prod.yml logs -f api_server
```

## 扩容说明

当前未部署网关，生产环境的 `api_server` 和 `agent_server` 都直接绑定宿主机端口，因此各只能运行一个副本。引入反向代理或负载均衡器后，移除这两个服务的 `ports` 映射，再通过 `docker compose -f docker-compose-prod.yml up -d --scale agent_server=3` 扩容 Agent Server。所有副本会共享 PostgreSQL 与 Redis。
