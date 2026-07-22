# Development Plan for the Teaching Agent Server

## Project Purpose and Goals

Extract the tutoring agent from the FastAPI business backend into an independent `uv` project served by LangGraph Agent Server. The browser must communicate with Agent Server directly while retaining the backend's existing authentication, session ownership, course, and project rules.

## Context and Background

The current backend proxies LangGraph state and streaming endpoints so it can authenticate requests, inject trusted prompt context, enforce run options, and update session activity. This duplicates Agent Server transport behaviour. The replacement keeps the backend as the source of truth for users, opaque tokens, sessions, courses, and projects, while Agent Server owns graphs, runs, checkpoints, interrupts, and streaming.

The browser's bearer token cannot be validated locally because it is an opaque database token. Agent Server will therefore call a protected backend authorisation endpoint. That endpoint will validate the user and requested session and return a versioned, non-secret prompt context. Client-supplied graph context will not be trusted.

## Development Tasks

### Phase 1: Define Contracts and Project Boundaries

- [x] Add a versioned backend authorisation request and response contract.
- [x] Define read and run access semantics matching the existing student and teacher rules.
- [x] Define the independent `agent_server` package, configuration, and LangGraph manifest.
- [x] Perform a self-review of the phase and record any corrections.
- [x] Continue under the user's explicit instruction to complete the implementation.

### Phase 2: Implement Agent Server

- [x] Move the graph, model, prompt, tool, and quiz schemas into `agent_server` without backend imports.
- [x] Implement an HTTP client for the backend authorisation endpoint.
- [x] Implement LangGraph authentication and deny-by-default resource authorisation.
- [x] Bind backend-issued prompt context in the graph factory and ignore untrusted client context.
- [x] Add `.python-version`, `pyproject.toml`, `uv.lock`, `langgraph.json`, and `.env.example`; load the shared `backend/.env` directly.
- [x] Perform a self-review of the phase and record any corrections.
- [x] Continue under the user's explicit instruction to complete the implementation.

### Phase 3: Implement Backend Integration

- [x] Add a service-authenticated internal endpoint that validates the bearer token and session access.
- [x] Return only safe user claims and `AgentContextV1` data.
- [x] Reject deleted sessions and update activity for authorised runs.
- [x] Remove the proxy router and Agent implementation after direct integration is verified.
- [x] Remove backend-only LangChain and LangGraph dependencies that are no longer used.
- [x] Perform a self-review of the phase and record any corrections.
- [x] Continue under the user's explicit instruction to complete the implementation.

### Phase 4: Automated Verification

- [x] Test prompt rendering and context validation for free and project sessions.
- [x] Test missing, invalid, and mismatched credentials.
- [x] Test student ownership, teacher read access, and denial of teacher writes to another user's session.
- [x] Test LangGraph resource filters and ensure forged context cannot affect prompts.
- [x] Run backend and Agent Server test suites, linting, import checks, and LangGraph configuration validation.
- [x] Perform a self-review of the phase and record any corrections.
- [x] Continue under the user's explicit instruction to complete the implementation.

### Phase 5: Agent Chat UI End-to-End Test

- [x] Clone `langchain-ai/agent-chat-ui` under `test_frontend/`.
- [x] Install dependencies with npm as required by the user-level project convention.
- [x] Configure the UI for the local Agent Server, graph `tutor`, and bearer authentication.
- [x] Start backend, Agent Server, and the test UI on non-conflicting ports.
- [x] Use browser automation to verify authentication, direct streaming, state persistence, and quiz interrupt/resume behaviour.
- [x] Perform a self-review of the phase and record any corrections.
- [x] Continue under the user's explicit instruction to complete the implementation.

## Important Considerations & Requirements

- [x] Do not over-engineer the solution or retain duplicate proxy code.
- [x] Do not add placeholder or TODO code.
- [x] Never commit secrets copied from `backend/.env`; generated environment files must remain ignored.
- [x] Fail closed when backend authorisation is unavailable.
- [x] Do not persist the original bearer token in graph state, thread metadata, or checkpoints.
- [x] Keep `session.id` and LangGraph `thread_id` identical.
- [x] Permit authenticated users to create empty threads; require a valid matching backend session before every read or run.
- [x] Configure CORS for the browser and verify unauthenticated preflight handling.

## Technical Decisions

The backend remains the sole owner of business data. Agent Server calls one narrow authorisation endpoint per protected browser request rather than importing backend ORM models or sharing database access. The endpoint is protected by both the user's bearer token and a service secret.

Prompt templates live with the agent. Prompt values come from a strict `AgentContextV1` returned by the backend. The graph factory closes over that verified context, so the graph does not consume client runtime context.

LangGraph resource authorisation is deny-by-default. Student thread access is filtered by owner metadata; teacher reads are allowed only after backend authorisation; runs require session ownership for every role.

## Testing Strategy

Unit tests use mock transports and isolated temporary databases. Integration tests start the real FastAPI and LangGraph development servers. The cloned Agent Chat UI is treated as a disposable test fixture and browser automation verifies the public workflow rather than relying only on HTTP probes.

## Debugging Protocol

- **Tests fail**: Analyse the failure and fix the root cause rather than weakening assertions.
- **Authentication fails**: Check the bearer header, service secret, session ownership, and Agent Server auth hook independently.
- **Streaming fails**: Check CORS preflight, Agent Server logs, stream mode, and thread creation options.
- **Integration issues**: Verify backend, Agent Server, LightRAG, and UI URLs from the process that consumes them.
- **Unclear requirements**: Preserve current backend behaviour and document any unavoidable difference.

## QA Checklist

- [x] All user instructions followed.
- [x] All requirements implemented and tested.
- [x] No critical code smell warnings.
- [x] British English used throughout this plan.
- [x] Python is managed by `uv` and pinned with `.python-version`.
- [x] Node dependencies are managed with npm.
- [x] No secrets or generated runtime state are tracked.
- [x] Backend and Agent Server ownership boundaries are enforced.
- [x] Direct browser-to-Agent-Server authentication is verified.
- [x] Prompt context spoofing and cross-user thread access are rejected.

## Implementation Results and Corrections

- The installed LangGraph API invokes authentication before route parameters are populated, so thread IDs are parsed from the request path and collection actions are explicitly excluded.
- The installed authentication middleware does not pass the documented request body argument to the authenticate callback. Run authorisation therefore derives its trusted context from the path and backend session lookup.
- Agent Chat UI renders custom interrupts as JSON by default. The integration fixture adds a quiz-specific renderer that resumes the graph with a native LangGraph command.
- The browser test completed an authenticated knowledge lookup, a streamed model response, a quiz interrupt, answer submission, and model assessment on the same persisted thread.
