# Tencent Cloud Production Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the Teaching Agent stack from public Gitea `latest` images to `~/tutoring` on Tencent Cloud, serve it through HTTPS, and initialize its test data.

**Architecture:** A Docker Compose stack runs all seven services on an internal network. Host Nginx is the only public entry point and proxies the frontend, API, and agent paths. PostgreSQL, Neo4j, and Redis use bind-mounted directories under `~/tutoring/data`; Certbot manages the host TLS certificate.

**Tech Stack:** Docker Engine and Compose, Nginx, Certbot, PostgreSQL with pgvector, Neo4j Community, Redis, LightRAG, Gitea Container Registry.

## Global Constraints

- Deploy under `~/tutoring` without cloning application source code.
- Pull `git.gqt.plus/gqt/tutoring-frontend:latest`, `git.gqt.plus/gqt/tutoring-agent-server:latest`, and `git.gqt.plus/gqt/tutoring-api-server:latest` anonymously.
- Persist PostgreSQL, Neo4j, and Redis to `~/tutoring/data/{postgres,neo4j,redis}`.
- Publish frontend, API, and agent ports only on loopback as `127.0.0.1:3000`, `127.0.0.1:8000`, and `127.0.0.1:2024`; all other service traffic stays on the Compose network.
- Use `tutoring.chatgqt.top`, Nginx, Certbot HTTP-01, HTTP-to-HTTPS redirection, and automatic certificate renewal.
- Apply container limits totaling `3 GiB`: Neo4j 640 MiB, PostgreSQL 384 MiB, LightRAG 640 MiB, agent server 512 MiB, API server 256 MiB, frontend 192 MiB, Redis 64 MiB, Docker/runtime headroom 384 MiB.
- Neo4j must use a 256 MiB initial heap, 256 MiB maximum heap, and 256 MiB page cache.
- Run `seed_users.py` only after health and HTTPS checks; it drops and recreates the API business tables.

---

### Task 1: Inspect The Remote Host And Create Deployment Files

**Files:**
- Create: `~/tutoring/docker-compose.yml`
- Create: `~/tutoring/.env`
- Create: `~/tutoring/init-db.sql`
- Create: `~/tutoring/data/postgres/`
- Create: `~/tutoring/data/neo4j/`
- Create: `~/tutoring/data/redis/`

**Interfaces:**
- Consumes: Public registry image references and deployment secrets supplied interactively on the server.
- Produces: A Compose project named `teaching-agent` and a local `.env` usable by `docker compose --env-file .env`.

- [ ] **Step 1: Inspect operating-system, Docker, proxy, certificate, firewall, and port state**

Run over SSH:

```bash
hostnamectl
free -h
df -h "$HOME"
docker --version
docker compose version
sudo systemctl is-active nginx
sudo systemctl is-active certbot.timer
sudo ss -ltnp
sudo ufw status
```

Expected: Docker Compose is available, sufficient disk is available, and any existing Nginx configuration or listeners on ports 80 and 443 are identified before changes.

- [ ] **Step 2: Create state directories and protect the deployment environment file**

Run over SSH:

```bash
mkdir -p "$HOME/tutoring/data/postgres" "$HOME/tutoring/data/neo4j" "$HOME/tutoring/data/redis"
chmod 700 "$HOME/tutoring" "$HOME/tutoring/data"
umask 077
```

- [ ] **Step 3: Write `~/tutoring/init-db.sql`**

Create the file with exactly:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

SELECT 'CREATE DATABASE tutoring_agent_server_db'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'tutoring_agent_server_db'
)\gexec

\connect tutoring_agent_server_db
CREATE EXTENSION IF NOT EXISTS vector;
```

- [ ] **Step 4: Generate deployment secrets and write `~/tutoring/.env`**

Generate values locally on the host:

```bash
openssl rand -base64 36
openssl rand -base64 36
openssl rand -hex 32
```

Write an environment file with this exact variable set, replacing generated values and DashScope credentials as appropriate:

```dotenv
POSTGRES_PASSWORD=<generated PostgreSQL password>
NEO4J_PASSWORD=<generated Neo4j password>
DASHSCOPE_API_KEY=<DashScope API key>
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.6-flash
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIM=1024
AGENT_SERVER_SECRET=<generated random secret>
CORS_ALLOW_ORIGINS=https://tutoring.chatgqt.top
LANGSMITH_TRACING=false
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=teaching-agent
```

Then run:

```bash
chmod 600 "$HOME/tutoring/.env"
```

- [ ] **Step 5: Write `~/tutoring/docker-compose.yml`**

Create a Compose file that includes the following service definitions and exact resource constraints:

```yaml
name: teaching-agent

services:
  postgres:
    image: pgvector/pgvector:pg17
    restart: unless-stopped
    mem_limit: 384m
    environment:
      POSTGRES_USER: tutoring
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
      POSTGRES_DB: tutoring_db
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5

  neo4j:
    image: neo4j:5.26-community
    restart: unless-stopped
    mem_limit: 640m
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:?Set NEO4J_PASSWORD in .env}
      NEO4J_server_memory_heap_initial__size: 256m
      NEO4J_server_memory_heap_max__size: 256m
      NEO4J_server_memory_pagecache_size: 256m
    volumes:
      - ./data/neo4j:/data
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p $$NEO4J_PASSWORD 'RETURN 1' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    mem_limit: 64m
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - ./data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 1s
      retries: 5

  lightrag:
    image: ghcr.io/hkuds/lightrag:latest
    restart: unless-stopped
    mem_limit: 640m
    environment:
      WORKSPACE: workspace-1
      LIGHTRAG_KV_STORAGE: PGKVStorage
      LIGHTRAG_VECTOR_STORAGE: PGVectorStorage
      LIGHTRAG_GRAPH_STORAGE: Neo4JStorage
      LIGHTRAG_DOC_STATUS_STORAGE: PGDocStatusStorage
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_USER: tutoring
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
      POSTGRES_DATABASE: tutoring_db
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USERNAME: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD:?Set NEO4J_PASSWORD in .env}
      NEO4J_DATABASE: neo4j
      LLM_BINDING: openai
      LLM_MODEL: ${LLM_MODEL:?Set LLM_MODEL in .env}
      LLM_BINDING_HOST: ${DASHSCOPE_BASE_URL:?Set DASHSCOPE_BASE_URL in .env}
      LLM_BINDING_API_KEY: ${DASHSCOPE_API_KEY:?Set DASHSCOPE_API_KEY in .env}
      EMBEDDING_BINDING: openai
      EMBEDDING_MODEL: ${EMBEDDING_MODEL:?Set EMBEDDING_MODEL in .env}
      EMBEDDING_DIM: ${EMBEDDING_DIM:?Set EMBEDDING_DIM in .env}
      EMBEDDING_BINDING_HOST: ${DASHSCOPE_BASE_URL:?Set DASHSCOPE_BASE_URL in .env}
      EMBEDDING_BINDING_API_KEY: ${DASHSCOPE_API_KEY:?Set DASHSCOPE_API_KEY in .env}
      SUMMARY_LANGUAGE: Chinese
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy

  api_server:
    image: git.gqt.plus/gqt/tutoring-api-server:latest
    restart: unless-stopped
    mem_limit: 256m
    environment:
      DATABASE_URL: postgresql+asyncpg://tutoring:${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}@postgres:5432/tutoring_db
      AGENT_SERVER_SECRET: ${AGENT_SERVER_SECRET:?Set AGENT_SERVER_SECRET in .env}
      LIGHTRAG_BASE_URL: http://lightrag:9621
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import json, urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/health'))['status'] == 'healthy'"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  agent_server:
    image: git.gqt.plus/gqt/tutoring-agent-server:latest
    restart: unless-stopped
    mem_limit: 512m
    environment:
      POSTGRES_URI: postgresql://tutoring:${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}@postgres:5432/tutoring_agent_server_db?sslmode=disable
      REDIS_URI: redis://redis:6379
      DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY:?Set DASHSCOPE_API_KEY in .env}
      DASHSCOPE_BASE_URL: ${DASHSCOPE_BASE_URL:?Set DASHSCOPE_BASE_URL in .env}
      LLM_MODEL: ${LLM_MODEL:?Set LLM_MODEL in .env}
      BACKEND_INTERNAL_URL: http://api_server:8000
      AGENT_SERVER_SECRET: ${AGENT_SERVER_SECRET:?Set AGENT_SERVER_SECRET in .env}
      LIGHTRAG_QUERY_URL: http://lightrag:9621/query
      CORS_ALLOW_ORIGINS: ${CORS_ALLOW_ORIGINS:?Set CORS_ALLOW_ORIGINS in .env}
      LANGSMITH_TRACING: ${LANGSMITH_TRACING:?Set LANGSMITH_TRACING in .env}
      LANGSMITH_ENDPOINT: ${LANGSMITH_ENDPOINT:?Set LANGSMITH_ENDPOINT in .env}
      LANGSMITH_API_KEY: ${LANGSMITH_API_KEY?Set LANGSMITH_API_KEY in .env}
      LANGSMITH_PROJECT: ${LANGSMITH_PROJECT:?Set LANGSMITH_PROJECT in .env}
    ports:
      - "127.0.0.1:2024:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      api_server:
        condition: service_healthy
      lightrag:
        condition: service_started
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ok')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  frontend:
    image: git.gqt.plus/gqt/tutoring-frontend:latest
    restart: unless-stopped
    mem_limit: 192m
    environment:
      NODE_ENV: production
      PORT: 3000
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      api_server:
        condition: service_healthy
      agent_server:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:3000"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
```

- [ ] **Step 6: Validate Compose expansion before pulling images**

Run over SSH:

```bash
cd "$HOME/tutoring"
docker compose --env-file .env config >/dev/null
docker compose --env-file .env config --images
```

Expected: command exits with status 0 and lists the seven image references; no unresolved environment-variable error appears.

- [ ] **Step 7: Commit deployment-plan changes in the repository**

```bash
git add docs/superpowers/plans/2026-07-24-tencent-cloud-production-deployment.md
git commit -m "docs: plan Tencent Cloud deployment"
```

### Task 2: Pull Images And Start The Stack

**Files:**
- Modify: `~/tutoring/docker-compose.yml` only if remote validation exposes an actual incompatibility.

**Interfaces:**
- Consumes: Validated Compose configuration from Task 1.
- Produces: Healthy Compose services and a local frontend listener on `127.0.0.1:3000`.

- [ ] **Step 1: Pull the published application images explicitly**

Run over SSH:

```bash
docker pull git.gqt.plus/gqt/tutoring-frontend:latest
docker pull git.gqt.plus/gqt/tutoring-agent-server:latest
docker pull git.gqt.plus/gqt/tutoring-api-server:latest
```

Expected: all three pulls succeed without `docker login`.

- [ ] **Step 2: Pull remaining images and start services**

Run over SSH:

```bash
cd "$HOME/tutoring"
docker compose --env-file .env pull
docker compose --env-file .env up -d
```

Expected: Compose creates all seven services and exits successfully.

- [ ] **Step 3: Verify container health, memory limits, and internal ports**

Run over SSH after startup stabilizes:

```bash
cd "$HOME/tutoring"
docker compose ps
docker stats --no-stream
docker inspect teaching-agent-neo4j-1 --format '{{.HostConfig.Memory}}'
docker inspect teaching-agent-postgres-1 --format '{{.HostConfig.Memory}}'
docker inspect teaching-agent-lightrag-1 --format '{{.HostConfig.Memory}}'
docker inspect teaching-agent-agent_server-1 --format '{{.HostConfig.Memory}}'
docker inspect teaching-agent-api_server-1 --format '{{.HostConfig.Memory}}'
docker inspect teaching-agent-frontend-1 --format '{{.HostConfig.Memory}}'
docker inspect teaching-agent-redis-1 --format '{{.HostConfig.Memory}}'
curl -fsS http://127.0.0.1:3000 >/dev/null
```

Expected: services report `healthy` where a health check exists; configured byte limits match 640m, 384m, 640m, 512m, 256m, 192m, and 64m; frontend, API, and agent ports are published only on loopback.

- [ ] **Step 4: Inspect logs only for services that are unhealthy**

Run over SSH if a service is not healthy:

```bash
cd "$HOME/tutoring"
docker compose logs --tail=200 <service-name>
```

Expected: identify the failing dependency before changing configuration. Do not run the seed script until all relevant services are healthy.

### Task 3: Configure Nginx And Certificate Renewal

**Files:**
- Create: `/etc/nginx/sites-available/tutoring.chatgqt.top`
- Create: `/etc/nginx/sites-enabled/tutoring.chatgqt.top` symlink

**Interfaces:**
- Consumes: Healthy frontend at `127.0.0.1:3000` and DNS A record for `tutoring.chatgqt.top` resolving to `82.157.111.219`.
- Produces: Public HTTP redirect and HTTPS reverse proxy routing `/`, `/api`, and `/agent`.

- [ ] **Step 1: Verify DNS and the host firewall before certificate issuance**

Run over SSH:

```bash
getent ahostsv4 tutoring.chatgqt.top
sudo ufw allow 'Nginx Full'
sudo ufw status
```

Expected: DNS resolves to `82.157.111.219`, and TCP ports 80 and 443 are allowed. Ensure the Tencent Cloud security group also permits inbound TCP 80 and 443 before continuing.

- [ ] **Step 2: Install Nginx and Certbot packages if absent**

Run over SSH:

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

- [ ] **Step 3: Create the initial HTTP Nginx server block**

Create `/etc/nginx/sites-available/tutoring.chatgqt.top` with exactly:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name tutoring.chatgqt.top;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /agent {
        proxy_pass http://127.0.0.1:2024;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The Compose file from Task 1 already binds API and agent only to loopback. Enable the Nginx site and run:

```bash
sudo ln -s /etc/nginx/sites-available/tutoring.chatgqt.top /etc/nginx/sites-enabled/tutoring.chatgqt.top
sudo nginx -t
sudo systemctl reload nginx
```

Expected: Nginx syntax validation succeeds and `curl -I http://tutoring.chatgqt.top` reaches the HTTP server block.

- [ ] **Step 4: Request and configure the TLS certificate**

Run over SSH:

```bash
sudo certbot --nginx -d tutoring.chatgqt.top --redirect --non-interactive --agree-tos --email admin@chatgqt.top
sudo systemctl enable --now certbot.timer
sudo certbot renew --dry-run
```

Expected: certificate issuance succeeds, HTTP redirects to HTTPS, the renewal timer is active, and dry-run renewal succeeds.

- [ ] **Step 5: Verify external routes and proxy behavior**

Run from the server and a public network if available:

```bash
curl -fsSI http://tutoring.chatgqt.top
curl -fsSI https://tutoring.chatgqt.top
curl -fsS https://tutoring.chatgqt.top/api/health
curl -fsSI https://tutoring.chatgqt.top/agent/ok
```

Expected: HTTP redirects to HTTPS, frontend returns a successful HTTPS response, API health returns its healthy JSON body, and agent health returns success.

### Task 4: Initialize Data And Perform Final Verification

**Files:**
- No source files changed.

**Interfaces:**
- Consumes: Healthy deployed API service, initialized PostgreSQL volume, and passing HTTPS route checks.
- Produces: Seeded accounts and projects in the API database.

- [ ] **Step 1: Transfer the known seed script, then copy it into the running API container**

Run from the local source checkout:

```bash
scp services/api_server/scripts/seed_users.py ubuntu@82.157.111.219:/home/ubuntu/tutoring/seed_users.py
```

Then run over SSH:

```bash
mkdir -p "$HOME/tutoring/tmp"
mv "$HOME/tutoring/seed_users.py" "$HOME/tutoring/tmp/seed_users.py"
docker cp "$HOME/tutoring/tmp/seed_users.py" teaching-agent-api_server-1:/app/scripts/seed_users.py
```

Expected: the script is present at `/app/scripts/seed_users.py` in the API container.

- [ ] **Step 2: Execute the destructive initialization script after explicit health confirmation**

Run over SSH:

```bash
cd "$HOME/tutoring"
docker compose --env-file .env ps
docker compose --env-file .env exec -T api_server python scripts/seed_users.py
```

Expected: output lists `teacher1`, `student1`, `student2`, and the three computer-network projects. The API business tables have been recreated.

- [ ] **Step 3: Verify seeded API data and final deployment state**

Run over SSH:

```bash
curl -fsS https://tutoring.chatgqt.top/api/health
cd "$HOME/tutoring"
docker compose --env-file .env ps
docker stats --no-stream
```

Expected: API health is healthy, services are up, and current total container memory remains below the 3 GiB configured hard-limit budget.

- [ ] **Step 4: Record deployment facts without recording secrets**

Record the deployment date, host, image tags, certificate expiry, container status, and seed result in an operations note. Do not include passwords, API keys, or full token values.

- [ ] **Step 5: Commit deployment-plan changes in the repository**

```bash
git add docs/superpowers/plans/2026-07-24-tencent-cloud-production-deployment.md
git commit -m "docs: plan Tencent Cloud deployment"
```
