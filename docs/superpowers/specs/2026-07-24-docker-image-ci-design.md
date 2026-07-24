# Docker Image CI Design

## Goal

Publish the Teaching Agent's three application images to the Gitea Container
Registry whenever `main` changes. The workflow does not deploy to a server.

## Scope

- Build and publish `api_server`, `agent_server`, and `frontend` images.
- Trigger on pushes to `main` and manual workflow dispatches.
- Tag every published image with the source commit SHA and `latest`.
- Use a repository secret named `REGISTRY_TOKEN` to authenticate to
  `git.gqt.plus` as the fixed `gqt` registry user.

## Workflow

The workflow is stored at `.gitea/workflows/docker-images.yml` and contains
three independent jobs, allowing images to build and publish in parallel.

| Job | Docker context | Image name | Path filter |
| --- | --- | --- | --- |
| API server | `services/api_server` | `gqt/tutoring-api-server` | `services/api_server/**` |
| Agent server | `services/agent_server` | `gqt/tutoring-agent-server` | `services/agent_server/**` |
| Frontend | `frontend` | `gqt/tutoring-frontend` | `frontend/**` |

Each job also runs when `deploy/**` or the workflow file changes, so Docker
deployment-related changes can republish the affected application images.

Each job checks out the source, builds its image with both tags, logs in using
`REGISTRY_TOKEN`, then pushes both tags. The registry address is
`git.gqt.plus`.

## Failure Behavior And Verification

- A failed image build or push fails only its corresponding job; other jobs
  continue independently.
- The workflow does not include application linting or test gates in this
  initial version. Docker build and registry push are its acceptance checks.
- After a push, Actions run status and failed job logs are inspected using
  Gitea MCP. Any reproducible build defect is fixed locally, committed,
  pushed, and verified with a new run.

## Exclusions

- No SSH, SCP, production deployment, or deployment-password secret.
- No images are built for PostgreSQL, Neo4j, Redis, or LightRAG because the
  production compose stack uses their upstream images.
