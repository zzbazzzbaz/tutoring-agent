# 路由拦截调试指南

调试前端页面时，路由拦截会强制跳转到登录页，导致无法直接访问功能页面。本文档说明所有拦截点的位置以及如何开启/关闭。

---

## 拦截点一览

| # | 文件 | 类型 | 作用 |
|---|------|------|------|
| 1 | `src/middleware.ts` | 服务端中间件 | 未登录 → 重定向 `/login`；角色不匹配 → 重定向对应角色页 |
| 2 | `src/app/page.tsx` | 服务端 redirect | 根路径 `/` → 重定向 `/login` |
| 3 | `src/components/auth/RoleGuard.tsx` | 客户端守卫组件 | 包裹在页面外层，未认证或角色不对 → 跳转登录页 |
| 4 | `src/lib/api/client.ts` | API 客户端 | 收到 401 → 清除凭证并跳转 `/login` |

---

## 当前状态：调试模式（已全部禁用）

所有拦截已注释掉，可直接访问任意页面无需登录。

**改动摘要：**

- `middleware.ts` — 函数体直接 `return NextResponse.next()`，原逻辑全部注释
- `app/page.tsx` — `redirect("/login")` 改为 `redirect("/teacher/chat")`
- `RoleGuard.tsx` — 直接 `return <>{children}</>`，跳过所有鉴权判断
- `api/client.ts` — `clearAuth()` 中 `window.location.href = "/login"` 已注释

---

## 恢复方法

### 1. middleware.ts

将函数体恢复为原逻辑：

```ts
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === "/login") {
    const authCookie = request.cookies.get("tutoring_auth")?.value;
    const roleCookie = request.cookies.get("tutoring_role")?.value;
    if (authCookie === "1" && roleCookie) {
      const home =
        roleCookie === "teacher" ? "/teacher/chat" : "/student/chat";
      return NextResponse.redirect(new URL(home, request.url));
    }
    return NextResponse.next();
  }

  const authCookie = request.cookies.get("tutoring_auth")?.value;
  const roleCookie = request.cookies.get("tutoring_role")?.value;

  if (authCookie !== "1") {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (pathname.startsWith("/student") && roleCookie !== "student") {
    return NextResponse.redirect(new URL("/teacher/chat", request.url));
  }
  if (pathname.startsWith("/teacher") && roleCookie !== "teacher") {
    return NextResponse.redirect(new URL("/student/chat", request.url));
  }

  return NextResponse.next();
}
```

### 2. app/page.tsx

```ts
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/login");
}
```

### 3. RoleGuard.tsx

取消 `useEffect` 和条件渲染部分的注释，删除开头的 `return <>{children}</>;`。

### 4. api/client.ts

在 `clearAuth()` 中取消注释：

```ts
window.location.href = "/login";
```

---

## 页面路由一览

### 公共页面

| 路由 | 文件 | 说明 |
|------|------|------|
| `/` | `src/app/page.tsx` | 根路径，生产环境重定向到 `/login` |
| `/login` | `src/app/login/page.tsx` | 登录页 |

### 学生端

| 路由 | 文件 | 说明 |
|------|------|------|
| `/student/chat` | `src/app/student/chat/page.tsx` | 学生聊天页 |
| `/student/manage/projects` | `src/app/student/manage/projects/page.tsx` | 学生项目列表 |
| `/student/manage/projects/[id]` | `src/app/student/manage/projects/[id]/page.tsx` | 学生项目详情 |

### 教师端

| 路由 | 文件 | 说明 |
|------|------|------|
| `/teacher/chat` | `src/app/teacher/chat/page.tsx` | 教师聊天页 |
| `/teacher/manage/projects` | `src/app/teacher/manage/projects/page.tsx` | 教师项目列表 |
| `/teacher/manage/projects/new` | `src/app/teacher/manage/projects/new/page.tsx` | 新建项目 |
| `/teacher/manage/projects/[id]` | `src/app/teacher/manage/projects/[id]/page.tsx` | 教师项目详情 |
| `/teacher/manage/projects/[id]/edit` | `src/app/teacher/manage/projects/[id]/edit/page.tsx` | 编辑项目 |
| `/teacher/manage/students` | `src/app/teacher/manage/students/page.tsx` | 学生管理列表 |
| `/teacher/manage/students/[id]` | `src/app/teacher/manage/students/[id]/page.tsx` | 学生详情 |
| `/teacher/manage/students/[id]/sessions/[sid]` | `src/app/teacher/manage/students/[id]/sessions/[sid]/page.tsx` | 学生会话详情 |
| `/teacher/manage/knowledge` | `src/app/teacher/manage/knowledge/page.tsx` | 知识库管理 |

---

## 注意事项

- 调试模式下，**服务端渲染的接口调用**可能因无 token 而失败，属正常现象
- 如需测试完整登录流程，按上述方法恢复所有拦截点
- 建议调试完成后及时恢复，避免将调试代码提交到生产分支
