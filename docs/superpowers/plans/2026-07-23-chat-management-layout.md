# Chat Management Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the frontend to a focused chat page with one session-history sidebar and separate role-aware management pages for projects and students.

**Architecture:** Chat routes will own `SessionProvider` and render a chat workspace sidebar plus the main chat area. Management routes will live under `/student/manage/...` and `/teacher/manage/...`, using a management layout with section navigation and a return-to-chat action. Old `/projects` and `/students` route files will be removed rather than redirected.

**Tech Stack:** Next.js App Router, React 19, TypeScript, Tailwind CSS, nuqs, shadcn/Radix UI, LangGraph SDK.

## Global Constraints

- Do not change backend APIs, schemas, auth behavior, streaming behavior, quiz interrupts, or role permissions.
- Do not preserve old route compatibility for `/student/projects`, `/teacher/projects`, or `/teacher/students`.
- Internal navigation must only point at `/student/manage/...` and `/teacher/manage/...` management routes.
- Chat page must have a single persistent left rail on desktop: the session list sidebar.
- Management pages must not show the chat session list.
- Build verification command is `npm run build` from `frontend/`.
- Browser verification must use the running local services at API `:8000`, Agent `:2024`, Frontend `:3000`.

---

## File Structure

### Create

- `frontend/src/components/chat/ChatWorkspaceSidebar.tsx` — session list sidebar, new session action, management entry, user/logout footer.
- `frontend/src/components/layout/ManagementLayout.tsx` — role-aware management shell with return-to-chat and project/student section navigation.
- `frontend/src/app/student/manage/layout.tsx` — student management layout wrapper.
- `frontend/src/app/student/manage/projects/page.tsx` — moved student project list route.
- `frontend/src/app/student/manage/projects/[id]/page.tsx` — moved student project detail route.
- `frontend/src/app/teacher/manage/layout.tsx` — teacher management layout wrapper.
- `frontend/src/app/teacher/manage/projects/page.tsx` — moved teacher project table route.
- `frontend/src/app/teacher/manage/projects/[id]/page.tsx` — moved teacher project detail route.
- `frontend/src/app/teacher/manage/students/page.tsx` — moved teacher student table route.
- `frontend/src/app/teacher/manage/students/[id]/page.tsx` — moved teacher student session table route.
- `frontend/src/app/teacher/manage/students/[id]/sessions/[sid]/page.tsx` — moved teacher read-only session route.

### Modify

- `frontend/src/components/chat/ChatView.tsx` — wrap chat layout with `SessionProvider`, sidebar, stream provider, and modal.
- `frontend/src/components/chat/thread/index.tsx` — remove desktop session-history sidebar and keep only chat content/input.
- `frontend/src/components/chat/thread/history/index.tsx` — remove if unused after moving session list into `ChatWorkspaceSidebar`.
- `frontend/src/components/projects/ProjectList.tsx` — update project detail links to new base paths.
- `frontend/src/components/projects/ProjectDetail.tsx` — update back links and project chat launch links.
- `frontend/src/components/projects/ProjectTable.tsx` — update teacher project detail links.
- `frontend/src/components/students/StudentTable.tsx` — update student detail links.
- `frontend/src/components/students/StudentSessionTable.tsx` — update back links and read-only session links.
- `frontend/src/app/student/layout.tsx` — remove global `AppSidebar`; keep role guard/content shell only.
- `frontend/src/app/teacher/layout.tsx` — remove global `AppSidebar`; keep role guard/content shell only.

### Delete

- `frontend/src/components/layout/AppSidebar.tsx` if unused after migration.
- `frontend/src/app/student/projects/page.tsx`
- `frontend/src/app/student/projects/[id]/page.tsx`
- `frontend/src/app/teacher/projects/page.tsx`
- `frontend/src/app/teacher/projects/[id]/page.tsx`
- `frontend/src/app/teacher/students/page.tsx`
- `frontend/src/app/teacher/students/[id]/page.tsx`
- `frontend/src/app/teacher/students/[id]/sessions/[sid]/page.tsx`

---

### Task 1: Add Chat Workspace Sidebar

**Files:**
- Create: `frontend/src/components/chat/ChatWorkspaceSidebar.tsx`
- Modify: none

**Interfaces:**
- Consumes: `useSessions()` from `SessionProvider`, `useAuth()` from `AuthProvider`, `useQueryState("session")`, `usePathname()`.
- Produces: `ChatWorkspaceSidebar({ role, onNewSession, mobileOpen, onMobileOpenChange }: { role: UserRole; onNewSession: () => void; mobileOpen?: boolean; onMobileOpenChange?: (open: boolean) => void })`.

- [ ] **Step 1: Write failing browser check**

Run current UI and observe the existing failure state:

```bash
agent-browser open http://127.0.0.1:3000/student/chat
agent-browser snapshot -i
```

Expected before implementation: snapshot shows the global navigation sidebar with `对话` and `项目` plus the chat area, not the new single chat workspace sidebar.

- [ ] **Step 2: Create `ChatWorkspaceSidebar.tsx`**

Implement a client component with this shape:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderOpen, LogOut, Plus, Settings } from "lucide-react";
import { useQueryState } from "nuqs";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { useAuth } from "@/components/auth/AuthProvider";
import { useSessions } from "@/components/chat/SessionProvider";
import { cn } from "@/lib/utils";
import type { Session, UserRole } from "@/lib/types";
import { useEffect } from "react";

function sessionTitle(session: Session) {
  return session.title || (session.mode === "free" ? "自由学习" : session.project_name || "项目模式");
}

export function ChatWorkspaceSidebar({
  role,
  onNewSession,
  mobileOpen = false,
  onMobileOpenChange,
}: {
  role: UserRole;
  onNewSession: () => void;
  mobileOpen?: boolean;
  onMobileOpenChange?: (open: boolean) => void;
}) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { sessions, sessionsLoading, refreshSessions } = useSessions();
  const [sessionId, setSessionId] = useQueryState("session");

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  const manageHref = role === "teacher" ? "/teacher/manage/projects" : "/student/manage/projects";
  const manageLabel = role === "teacher" ? "管理中心" : "项目中心";

  const content = (
    <div className="flex h-full w-full flex-col bg-background">
      <div className="border-b p-3">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold">教学 Agent</p>
            <p className="text-xs text-muted-foreground">会话列表</p>
          </div>
          <Button size="sm" onClick={onNewSession}>
            <Plus className="mr-1 size-4" />
            新建
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {sessionsLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-12 w-full" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <p className="p-3 text-sm text-muted-foreground">暂无会话</p>
        ) : (
          <div className="space-y-1">
            {sessions.map((session) => {
              const active = sessionId === session.id;
              return (
                <Button
                  key={session.id}
                  variant="ghost"
                  className={cn("h-auto w-full justify-start px-3 py-2 text-left", active && "bg-primary/10 text-primary")}
                  onClick={() => setSessionId(session.id)}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{sessionTitle(session)}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {session.mode === "project" ? `项目：${session.project_name || "未命名项目"}` : "自由学习"}
                    </span>
                  </span>
                </Button>
              );
            })}
          </div>
        )}
      </div>
      <div className="space-y-2 border-t p-3">
        <Button asChild variant={pathname.startsWith(manageHref) ? "secondary" : "outline"} className="w-full justify-start">
          <Link href={sessionId ? `${manageHref}?session=${sessionId}` : manageHref}>
            {role === "teacher" ? <Settings className="mr-2 size-4" /> : <FolderOpen className="mr-2 size-4" />}
            {manageLabel}
          </Link>
        </Button>
        <div className="rounded-md bg-muted/50 p-2 text-sm">
          <p className="truncate font-medium">{user?.name}</p>
          <p className="truncate text-xs text-muted-foreground">{user?.username}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={logout} className="w-full justify-start">
          <LogOut className="mr-2 size-4" />
          退出登录
        </Button>
      </div>
    </div>
  );

  return (
    <>
      <aside className="hidden h-screen w-[280px] shrink-0 border-r bg-background lg:block">
        {content}
      </aside>
      <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <SheetContent side="left" className="w-[280px] p-0 lg:hidden">
          {content}
        </SheetContent>
      </Sheet>
    </>
  );
}
```

If `refreshSessions()` fails, `SessionProvider` currently logs the error and leaves `sessions` empty. The sidebar must keep rendering the empty state `暂无会话` and must not block the chat main area.

- [ ] **Step 3: Run type/build check**

Run:

```bash
cd frontend
npm run build
```

Expected: build can fail only because the component is not yet wired or unrelated existing warnings appear; TypeScript errors in `ChatWorkspaceSidebar.tsx` must be fixed before continuing.

- [ ] **Step 4: Commit task changes if committing is requested**

Do not commit unless the user explicitly requests commits.

---

### Task 2: Rework ChatView To Use One Sidebar

**Files:**
- Modify: `frontend/src/components/chat/ChatView.tsx`
- Modify: `frontend/src/components/chat/thread/index.tsx`

**Interfaces:**
- Consumes: `ChatWorkspaceSidebar({ role, onNewSession })` from Task 1.
- Produces: chat page with one desktop sidebar and chat content area.

- [ ] **Step 1: Write failing browser check**

Run:

```bash
agent-browser open http://127.0.0.1:3000/student/chat
agent-browser snapshot -i
```

Expected before implementation: snapshot still shows the old global navigation or a chat-internal sidebar toggle.

- [ ] **Step 2: Update `ChatView.tsx` props and structure**

Change `ChatView` to accept role and render the sidebar inside `SessionProvider`:

```tsx
export function ChatView({
  role,
  readOnly = false,
}: {
  role: "student" | "teacher";
  readOnly?: boolean;
}) {
  return (
    <SessionProvider>
      <ChatShell role={role} readOnly={readOnly} />
    </SessionProvider>
  );
}

function ChatShell({ role, readOnly }: { role: "student" | "teacher"; readOnly: boolean }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [projectPreselect, setProjectPreselect] = useState<string | undefined>(undefined);
  const [_sessionId, setSessionId] = useQueryState("session");
  const [projectParam, setProjectParam] = useQueryState("project");

  useEffect(() => {
    if (projectParam) {
      setProjectPreselect(projectParam);
      setModalOpen(true);
      setProjectParam(null);
    }
  }, [projectParam, setProjectParam]);

  return (
    <div className="flex h-screen overflow-hidden">
      {!readOnly && (
        <ChatWorkspaceSidebar
          role={role}
          onNewSession={() => {
            setProjectPreselect(undefined);
            setModalOpen(true);
          }}
          mobileOpen={mobileSidebarOpen}
          onMobileOpenChange={setMobileSidebarOpen}
        />
      )}
      <div className="min-w-0 flex-1">
        <StreamProvider readOnly={readOnly}>
          <ArtifactProvider>
            <ChatContent
              readOnly={readOnly}
              onOpenSessions={() => setMobileSidebarOpen(true)}
            />
          </ArtifactProvider>
        </StreamProvider>
      </div>
      <NewSessionModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setProjectPreselect(undefined);
        }}
        onCreated={(id) => setSessionId(id)}
        preselectProjectId={projectPreselect}
      />
    </div>
  );
}
```

Keep the existing `project` query handling exactly as shown so project details can still launch project-mode chat.

- [ ] **Step 3: Remove desktop session-history rail from `thread/index.tsx`**

Remove the `ThreadHistory` import and the `motion.div` block that renders it at the start of the component. Add an optional `onOpenSessions?: () => void` prop to `Thread` and wire one mobile-only header button to that callback. Desktop must not render a second persistent rail.

- [ ] **Step 4: Update chat page call sites**

Modify:

```tsx
// frontend/src/app/student/chat/page.tsx
<ChatView role="student" />

// frontend/src/app/teacher/chat/page.tsx
<ChatView role="teacher" />
```

- [ ] **Step 5: Verify browser behavior**

Run:

```bash
agent-browser open http://127.0.0.1:3000/student/chat
agent-browser snapshot -i
```

Expected: one left sidebar with `教学 Agent`, `会话列表`, `新建`, session rows, and `项目中心`; no separate `对话`/`项目` global sidebar.

---

### Task 3: Add Management Layouts And Routes

**Files:**
- Create: `frontend/src/components/layout/ManagementLayout.tsx`
- Create: `frontend/src/app/student/manage/layout.tsx`
- Create: `frontend/src/app/teacher/manage/layout.tsx`
- Create/move page files under `student/manage` and `teacher/manage`
- Modify: `frontend/src/app/student/layout.tsx`
- Modify: `frontend/src/app/teacher/layout.tsx`

**Interfaces:**
- Produces: `ManagementLayout({ role, children }: { role: UserRole; children: React.ReactNode })`.

- [ ] **Step 1: Write failing route check**

Run:

```bash
curl -I http://127.0.0.1:3000/student/manage/projects
curl -I http://127.0.0.1:3000/teacher/manage/projects
```

Expected before implementation: routes are missing or return Next 404.

- [ ] **Step 2: Implement `ManagementLayout.tsx`**

Use this interface:

```tsx
"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ArrowLeft, FolderOpen, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { UserRole } from "@/lib/types";

export function ManagementLayout({ role, children }: { role: UserRole; children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const session = searchParams.get("session");
  const chatHref = session ? `/${role}/chat?session=${session}` : `/${role}/chat`;
  const items = role === "teacher"
    ? [
        { label: "项目", href: "/teacher/manage/projects", icon: FolderOpen },
        { label: "学生", href: "/teacher/manage/students", icon: Users },
      ]
    : [{ label: "项目", href: "/student/manage/projects", icon: FolderOpen }];

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <header className="flex h-14 shrink-0 items-center justify-between border-b px-4">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm">
            <Link href={chatHref}>
              <ArrowLeft className="mr-2 size-4" />
              返回对话
            </Link>
          </Button>
          <div>
            <h1 className="text-base font-semibold">{role === "teacher" ? "管理中心" : "项目中心"}</h1>
          </div>
        </div>
        <nav className="flex gap-2">
          {items.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Button key={item.href} asChild variant={active ? "secondary" : "ghost"} size="sm">
                <Link href={item.href} className={cn("gap-2")}>
                  <item.icon className="size-4" />
                  {item.label}
                </Link>
              </Button>
            );
          })}
        </nav>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
```

- [ ] **Step 3: Add nested management layouts**

Create:

```tsx
// frontend/src/app/student/manage/layout.tsx
"use client";
import { ManagementLayout } from "@/components/layout/ManagementLayout";
export default function StudentManageLayout({ children }: { children: React.ReactNode }) {
  return <ManagementLayout role="student">{children}</ManagementLayout>;
}
```

```tsx
// frontend/src/app/teacher/manage/layout.tsx
"use client";
import { ManagementLayout } from "@/components/layout/ManagementLayout";
export default function TeacherManageLayout({ children }: { children: React.ReactNode }) {
  return <ManagementLayout role="teacher">{children}</ManagementLayout>;
}
```

- [ ] **Step 4: Move route page contents**

Copy current page contents to new route files, updating base paths:

```tsx
// student/manage/projects/page.tsx
<ProjectList basePath="/student/manage" publishedOnly />

// student/manage/projects/[id]/page.tsx
<ProjectDetail id={id} basePath="/student/manage" readOnly />

// teacher/manage/projects/page.tsx
<ProjectTable />

// teacher/manage/projects/[id]/page.tsx
<ProjectDetail id={id} basePath="/teacher/manage" />

// teacher/manage/students/page.tsx
<StudentTable />

// teacher/manage/students/[id]/page.tsx
<StudentSessionTable studentId={id} />

// teacher/manage/students/[id]/sessions/[sid]/page.tsx
<ReadOnlyChatView studentId={id} sessionId={sid} />
```

- [ ] **Step 5: Remove global `AppSidebar` from role layouts**

Change student and teacher layouts to:

```tsx
return (
  <RoleGuard role="student">
    <div className="h-screen overflow-hidden">{children}</div>
  </RoleGuard>
);
```

and equivalent for teacher.

- [ ] **Step 6: Verify new routes compile**

Run:

```bash
cd frontend
npm run build
```

Expected: build succeeds with no new TypeScript errors.

---

### Task 4: Update Internal Links And Delete Old Routes

**Files:**
- Modify: `frontend/src/components/projects/ProjectList.tsx`
- Modify: `frontend/src/components/projects/ProjectDetail.tsx`
- Modify: `frontend/src/components/projects/ProjectTable.tsx`
- Modify: `frontend/src/components/students/StudentTable.tsx`
- Modify: `frontend/src/components/students/StudentSessionTable.tsx`
- Delete old route files listed in File Structure.

**Interfaces:**
- Consumes: new `/manage/...` routes from Task 3.
- Produces: no internal links to old project/student routes.

- [ ] **Step 1: Write failing link search**

Run:

```bash
grep -R '"/student/projects\|"/teacher/projects\|"/teacher/students\|`/teacher/projects\|`/teacher/students' frontend/src
```

Expected before implementation: matches exist in project and student components.

- [ ] **Step 2: Update project links**

Required changes:

```tsx
// ProjectList.tsx already uses `${basePath}/projects/${project.id}`.
// Ensure callers pass `/student/manage` and `/teacher/manage`.

// ProjectDetail.tsx back link remains:
router.push(`${basePath}/projects`)

// ProjectDetail.tsx project chat launch remains:
router.push(`/student/chat?project=${project.id}`)
```

- [ ] **Step 3: Update teacher links**

Required changes:

```tsx
// ProjectTable.tsx
href={`/teacher/manage/projects/${project.id}`}

// StudentTable.tsx
href={`/teacher/manage/students/${student.id}`}

// StudentSessionTable.tsx back button
router.push("/teacher/manage/students")

// StudentSessionTable.tsx session link
href={`/teacher/manage/students/${studentId}/sessions/${session.id}`}
```

- [ ] **Step 4: Delete old route files**

Delete:

```text
frontend/src/app/student/projects/page.tsx
frontend/src/app/student/projects/[id]/page.tsx
frontend/src/app/teacher/projects/page.tsx
frontend/src/app/teacher/projects/[id]/page.tsx
frontend/src/app/teacher/students/page.tsx
frontend/src/app/teacher/students/[id]/page.tsx
frontend/src/app/teacher/students/[id]/sessions/[sid]/page.tsx
```

- [ ] **Step 5: Verify no old links remain**

Run:

```bash
grep -R '"/student/projects\|"/teacher/projects\|"/teacher/students\|`/teacher/projects\|`/teacher/students' frontend/src || true
```

Expected: no matches.

---

### Task 5: Full Verification

**Files:**
- No intended source edits unless verification finds a defect.

**Interfaces:**
- Consumes: completed Tasks 1-4.
- Produces: verified UI behavior.

- [ ] **Step 1: Run production build**

Run:

```bash
cd frontend
npm run build
```

Expected: build succeeds. Existing lint warnings may remain, but there must be no new errors.

- [ ] **Step 2: Restart dev server cleanly after build**

Run:

```bash
cd frontend
rm -rf .next
npx next dev --port 3000 > /tmp/frontend.log 2>&1 &
```

Expected: `/tmp/frontend.log` shows Next ready on port 3000.

- [ ] **Step 3: Verify student chat layout**

Run:

```bash
agent-browser open http://127.0.0.1:3000/login
agent-browser snapshot -i
```

Log in as `student1 / student123`, then open `/student/chat`.

Expected: one left sidebar with session list and `项目中心`; chat main area has no second persistent left rail.

- [ ] **Step 4: Verify student management route**

Click `项目中心`.

Expected: URL is `/student/manage/projects` or `/student/manage/projects?session=<id>`; project list renders; `返回对话` returns to `/student/chat` and preserves session query if present.

- [ ] **Step 4a: Verify student project-mode launch**

Open one project detail from `/student/manage/projects` and click `在对话中讨论此项目`.

Expected: browser navigates to `/student/chat?project=<projectId>`, the new-session modal opens with project mode preselected, and creating the session opens a project-mode chat.

- [ ] **Step 5: Verify teacher chat and management routes**

Log in as `teacher1 / teacher123`, then open `/teacher/chat`.

Expected: one left sidebar with session list and `管理中心`.

Click `管理中心`.

Expected: URL is `/teacher/manage/projects`; project management renders; top nav exposes `项目` and `学生`.

- [ ] **Step 6: Verify teacher student conversation viewing**

Open `/teacher/manage/students`, select a student, then open a session.

Expected: read-only conversation page renders messages and does not expose editable chat input.

- [ ] **Step 7: Verify chat still sends messages**

On `/student/chat`, create a new session and send:

```text
你好，请简单介绍一下你能帮助我做什么
```

Expected: message streams successfully; no `Thread or assistant not found` error.

- [ ] **Step 8: Verify old routes are not preserved**

Run:

```bash
curl -I http://127.0.0.1:3000/student/projects
curl -I http://127.0.0.1:3000/teacher/projects
curl -I http://127.0.0.1:3000/teacher/students
```

Expected: no 307 redirect to new routes. A 404 is acceptable because compatibility is intentionally not preserved.
