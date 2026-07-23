# Chat and Management Layout Design

**Date**: 2026-07-23
**Status**: Approved for planning
**Author**: Brainstorming session

## Overview

Refine the production frontend layout so the chat page is dedicated to conversation, while project and student administration move into separate management pages. The chat page should have only one left sidebar, used for session history. Management navigation should be accessible from the chat page through a clear button rather than competing with chat navigation inside the same sidebar.

## Goals

- Keep the chat page focused on AI conversation and session switching.
- Remove the current double-sidebar feeling caused by global navigation plus chat history.
- Preserve role-specific features for students and teachers.
- Migrate project/student pages into explicit management routes where that makes the UI clearer.
- Keep the implementation incremental and avoid changing backend APIs.

## Non-Goals

- No redesign of chat message rendering, streaming, quiz interrupts, or file upload behavior.
- No backend schema or API changes.
- No change to role permissions.
- No new project/student business functionality beyond route, navigation, and layout placement.

## Target UX

### Chat Pages

Routes:

- `/student/chat`
- `/teacher/chat`

Layout:

- A single left sidebar shows session history.
- Sidebar top contains app identity and a new-session action.
- Sidebar middle contains session list.
- Sidebar bottom contains user info, logout, and a role-aware management entry button.
- Main content contains only the chat interface.
- Chat-internal sidebars/drawers should be removed or disabled on desktop so there is no second left rail.

Student management entry:

- Button label: `项目中心`
- Destination: `/student/manage/projects`.

Teacher management entry:

- Button label: `管理中心`
- Destination: `/teacher/manage/projects`.

### Management Pages

Management pages are separate from chat and optimized for tables/forms/detail views.

Student management area:

- Shows project browsing and project detail pages.
- Provides a `返回对话` action to return to `/student/chat`.
- If the user entered management from a selected chat session, `返回对话` should preserve `?session=<id>` when that value is available in the URL state.
- Project detail can still launch a project-mode chat session.

Teacher management area:

- Shows project management and student management.
- Provides clear navigation between `项目` and `学生`.
- Provides a `返回对话` action to return to `/teacher/chat`.
- If the user entered management from a selected chat session, `返回对话` should preserve `?session=<id>` when that value is available in the URL state.
- Student conversation viewing remains read-only.

## Routing

Preferred route structure:

```text
/student/chat
/student/manage/projects
/student/manage/projects/[id]

/teacher/chat
/teacher/manage/projects
/teacher/manage/projects/[id]
/teacher/manage/students
/teacher/manage/students/[id]
/teacher/manage/students/[id]/sessions/[sid]
```

Old route compatibility:

- Do not keep compatibility redirects for the old project/student routes.
- Remove or replace old `/student/projects`, `/teacher/projects`, and `/teacher/students` route files as part of the route migration.
- Internal navigation should only point at the new `/manage/...` routes.

## Component Boundaries

### Chat Workspace Sidebar

Create or refactor a chat-specific sidebar component responsible for:

- Session list loading and selection.
- New session action.
- Role-aware management entry button.
- User identity and logout.

This component depends on `SessionProvider` and `AuthProvider`. The chat route must wrap both the sidebar and chat main area in `SessionProvider` so session list state is shared.

### Chat Main Area

The chat thread component should render only the conversation content and input. It should not own the desktop session sidebar. On mobile, the session sidebar can become a sheet/drawer opened from a single header button, but it must still be the same session-list component and must not introduce a second persistent rail.

### Management Layout

Create a role-aware management layout responsible for:

- Management section navigation.
- `返回对话` action.
- Role guard remains enforced by existing student/teacher route layouts or equivalent nested layouts.

## Data Flow

- Session data continues to come from API Server through `sessionsApi`.
- New session creation still creates an API session and then a matching LangGraph thread.
- Selecting a session updates the `session` query parameter on the relevant chat route.
- Management pages continue using existing project and user API clients.

## Error Handling

- If session loading fails, keep the chat page usable and show an empty/error state in the sidebar.
- If new session creation fails, preserve the current rollback behavior for partially created API sessions.
- No old-route redirect behavior is required.
- Management entry links from chat should include the active `session` query when present so `返回对话` can preserve context.

## Testing

- Build must pass with `npm run build`.
- Browser verification should cover:
  - Student login -> chat page has one sidebar with sessions.
  - Student management button opens project area and `返回对话` returns to chat.
  - Teacher login -> chat page has one sidebar with sessions.
  - Teacher management area exposes project and student sections.
  - Teacher student detail still shows read-only conversation links.
  - Teacher read-only student conversation page still renders messages.
  - Student project detail can still launch project-mode chat.
  - Internal navigation uses only new management routes.
  - Creating and sending a chat message still works.
