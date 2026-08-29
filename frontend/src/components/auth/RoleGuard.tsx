"use client";

import { useEffect, type ReactNode } from "react";
import { useAuth } from "./AuthProvider";
import { ROUTES } from "@/lib/constants";
import type { UserRole } from "@/lib/types";

// [调试模式] 路由拦截已临时禁用，见 docs/route-guard-debug.md
// 恢复方法：取消下方 useEffect 和条件渲染的注释
export function RoleGuard({
  role,
  children,
}: {
  role: UserRole;
  children: ReactNode;
}) {
  return <>{children}</>;
  //
  // const { user, loading, isAuthenticated } = useAuth();
  //
  // useEffect(() => {
  //   if (loading) return;
  //   if (!isAuthenticated) {
  //     window.location.href = ROUTES.LOGIN;
  //     return;
  //   }
  //   if (user && user.role !== role) {
  //     window.location.href =
  //       user.role === "teacher" ? ROUTES.TEACHER_CHAT : ROUTES.STUDENT_CHAT;
  //   }
  // }, [user, role, loading, isAuthenticated]);
  //
  // if (loading || !isAuthenticated || (user && user.role !== role)) {
  //   return (
  //     <div className="flex min-h-screen items-center justify-center">
  //       <p className="text-muted-foreground">加载中...</p>
  //     </div>
  //   );
  // }
  //
  // return <>{children}</>;
}
