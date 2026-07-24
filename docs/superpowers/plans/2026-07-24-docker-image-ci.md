# Docker Image CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the API server, Agent server, and frontend Docker images to the Gitea Container Registry for every push to `main`.

**Architecture:** A single Gitea Actions workflow has three independent jobs, one for each application Docker context. Each job builds, authenticates to `git.gqt.plus` with the repository's `REGISTRY_TOKEN`, and pushes immutable SHA and moving `latest` tags. Repository secret setup and post-push job-log inspection are performed using Gitea MCP.

**Tech Stack:** Gitea Actions, Docker CLI, Gitea Container Registry, `actions/checkout@v4`.

## Global Constraints

- Trigger on pushes to `main` and `workflow_dispatch` only.
- Publish `gqt/tutoring-api-server`, `gqt/tutoring-agent-server`, and `gqt/tutoring-frontend` to `git.gqt.plus`.
- Every published image must receive `${{ gitea.sha }}` and `latest` tags.
- Authenticate with repository secret `REGISTRY_TOKEN` and fixed registry username `gqt`.
- Do not configure or execute SSH/SCP/server deployment steps.
- Do not build upstream PostgreSQL, Neo4j, Redis, or LightRAG images.

---

### Task 1: Add the Docker Image Publishing Workflow

**Files:**
- Create: `.gitea/workflows/docker-images.yml`

**Interfaces:**
- Consumes: repository secret `REGISTRY_TOKEN` injected by Gitea Actions as `${{ secrets.REGISTRY_TOKEN }}`.
- Produces: `git.gqt.plus/gqt/tutoring-api-server`, `git.gqt.plus/gqt/tutoring-agent-server`, and `git.gqt.plus/gqt/tutoring-frontend` image tags.

- [ ] **Step 1: Create the workflow with three independent build-and-push jobs**

```yaml
name: Teaching Agent Docker Images

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: git.gqt.plus
  REGISTRY_USERNAME: gqt

jobs:
  api-server:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          docker build \
            -t $REGISTRY/gqt/tutoring-api-server:${{ gitea.sha }} \
            -t $REGISTRY/gqt/tutoring-api-server:latest \
            services/api_server
      - run: echo "${{ secrets.REGISTRY_TOKEN }}" | docker login $REGISTRY -u "$REGISTRY_USERNAME" --password-stdin
      - run: |
          docker push $REGISTRY/gqt/tutoring-api-server:${{ gitea.sha }}
          docker push $REGISTRY/gqt/tutoring-api-server:latest
```

Add matching `agent-server` and `frontend` jobs that use `services/agent_server` and `frontend` respectively, and their corresponding image names.

- [ ] **Step 2: Validate workflow YAML and locally build all Docker contexts**

Run: `docker compose --env-file .env.example -f deploy/docker-compose-prod.yml config`

Expected: exit status `0`; the production compose definition resolves successfully.

Run: `docker build -t tutoring-api-server:ci services/api_server`

Expected: exit status `0` and a locally tagged API server image.

Run: `docker build -t tutoring-agent-server:ci services/agent_server`

Expected: exit status `0` and a locally tagged Agent server image.

Run: `docker build -t tutoring-frontend:ci frontend`

Expected: exit status `0` and a locally tagged frontend image.

- [ ] **Step 3: Commit the workflow**

```bash
git add .gitea/workflows/docker-images.yml
git commit -m "ci: publish application docker images"
```

### Task 2: Configure Registry Access And Verify Gitea Actions

**Files:**
- No repository files changed.

**Interfaces:**
- Consumes: a user-provided Gitea access token with permission to write packages for user `gqt`.
- Produces: repository Actions secret `REGISTRY_TOKEN` and a successful workflow run.

- [ ] **Step 1: Upsert the repository secret using Gitea MCP**

Call `gitea_upsert_repo_action_secret` with:

```json
{
  "owner": "gqt",
  "repo": "tutoring-agent",
  "name": "REGISTRY_TOKEN",
  "data": "<user-provided-package-write-token>",
  "description": "Gitea Container Registry token with package write access"
}
```

- [ ] **Step 2: Push the workflow commit to `origin/main`**

Run: `git push origin main`

Expected: exit status `0`; Gitea creates a workflow run for the new commit.

- [ ] **Step 3: Inspect the Actions run and its job logs with Gitea MCP**

Call `gitea_list_repo_action_runs` for `gqt/tutoring-agent`, then call
`gitea_list_repo_action_run_jobs` for the newest run. For any failed job,
call `gitea_get_repo_action_job_log_preview` with that job ID.

Expected: all three jobs complete successfully.

- [ ] **Step 4: Repair and retry if a job fails**

Use the failed job log to reproduce the Docker command locally. Make the
smallest source or Dockerfile fix, run that image's local build command from
Task 1, commit the fix, push `main`, and inspect the replacement run through
Gitea MCP.

- [ ] **Step 5: Verify repository state**

Run: `git status --short`

Expected: no output.
