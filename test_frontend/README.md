# Agent Chat UI Integration Fixture

`agent-chat-ui/` is based on <https://github.com/langchain-ai/agent-chat-ui> and is
kept as a local end-to-end test fixture.

The fixture adds bearer-token support to both LangGraph streaming and thread-list
requests. Its ignored `.env` points to `http://127.0.0.1:2024`, graph `tutor`, and a
token issued by the teaching backend.

Install and start it with npm:

```bash
cd test_frontend/agent-chat-ui
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Create a teaching session through `POST http://127.0.0.1:8000/sessions`, then create
the matching empty LangGraph thread once with the same session ID:

```bash
curl -X POST http://127.0.0.1:2024/threads \
  -H "Authorization: Bearer <student-token>" \
  -H "Content-Type: application/json" \
  --data '{"thread_id":"<session-id>","metadata":{"graph_id":"tutor"}}'
```

Open the UI at:

```text
http://127.0.0.1:3000/?threadId=<session-id>
```

The generic `New thread` action is outside this fixture's workflow because teaching
sessions are business resources owned by the backend. Agent Server stamps the
authenticated owner on new threads and reauthorises every state read and run against
the matching backend session.
