# Tencent Cloud Production Deployment Design

## Goal

Deploy the teaching agent on `82.157.111.219` under `~/tutoring` without
cloning application source code. The stack will use the public `latest`
images published by Gitea and serve `https://tutoring.chatgqt.top` with
automatically renewed TLS certificates.

## Topology

Docker Compose runs the following services:

- `postgres`: application and agent PostgreSQL databases with pgvector.
- `neo4j`: LightRAG graph storage.
- `redis`: agent runtime state.
- `lightrag`: knowledge-base API backed by PostgreSQL and Neo4j.
- `api_server`: `git.gqt.plus/gqt/tutoring-api-server:latest`.
- `agent_server`: `git.gqt.plus/gqt/tutoring-agent-server:latest`.
- `frontend`: `git.gqt.plus/gqt/tutoring-frontend:latest`.

Only the frontend is reachable from the host. Nginx proxies `/`, `/api`, and
`/agent` to the frontend, API server, and agent server respectively. Database,
Redis, LightRAG, and application service ports are internal Docker network
ports and are not published publicly.

## Server Layout

`~/tutoring` contains:

- `docker-compose.yml`: production Compose definition using published images.
- `.env`: deployment secrets and public origin settings, readable only by the
  deployment user.
- `init-db.sql`: PostgreSQL bootstrap script.
- `data/postgres`, `data/neo4j`, and `data/redis`: bind-mounted persistent
  state directories.

The deployment host pulls the public Gitea Registry images with their
`latest` tags. No Docker registry credentials or source checkout are required.

## Resource Budget

Docker Compose applies the following container hard limits. Their sum is
exactly `3 GiB`:

| Service | Limit |
| --- | ---: |
| Neo4j | 640 MiB |
| PostgreSQL | 384 MiB |
| LightRAG | 640 MiB |
| Agent server | 512 MiB |
| API server | 256 MiB |
| Frontend | 192 MiB |
| Redis | 64 MiB |
| Docker/runtime headroom | 384 MiB |

Neo4j uses a fixed `256m` initial and maximum JVM heap plus a `256m` page
cache. This leaves room within its container limit for native JVM memory and
database overhead.

## TLS And Proxying

Nginx is installed or updated on the host with a virtual host for
`tutoring.chatgqt.top`. Certbot obtains a certificate using the HTTP-01
challenge on port 80, configures HTTPS on port 443, redirects HTTP to HTTPS,
and manages automatic renewal using the system-installed renewal timer.

## Deployment Flow

1. Inspect the host's Docker, Nginx, Certbot, firewall, and existing port use.
2. Create the persistent directories and production Compose files in
   `~/tutoring`.
3. Pull the three Gitea application images and start the stack with Docker
   Compose.
4. Verify container health and internal service reachability.
5. Configure Nginx and obtain the TLS certificate.
6. Verify the HTTPS site and its `/api` and `/agent` reverse-proxy routes.
7. Run the API seed script inside the API container.

## Data Initialization

The seed script deliberately drops and recreates the API business tables before
creating three test users and three published projects. It is run only after
the stack is healthy and is treated as destructive initialization. It does not
delete the PostgreSQL extensions, the agent database, Neo4j data, or Redis
data.

## Failure Handling

- If an image pull, health check, proxy test, or certificate issuance fails,
  stop before running the destructive seed script and report the failed stage.
- Persistent host directories are never removed during deployment.
- Compose restart policy is `unless-stopped` for all services.
- A later application update consists of pulling the three `latest` images and
  recreating only `api_server`, `agent_server`, and `frontend`; data services
  and their persistent directories remain untouched.
