"use client";

import { useEffect } from "react";
import { LoginForm } from "@/components/auth/LoginForm";
import { useAuth } from "@/components/auth/AuthProvider";
import { ROUTES } from "@/lib/constants";

export default function LoginPage() {
  const { isAuthenticated, user, loading } = useAuth();

  useEffect(() => {
    if (!loading && isAuthenticated && user) {
      window.location.href =
        user.role === "teacher" ? ROUTES.TEACHER_CHAT : ROUTES.STUDENT_CHAT;
    }
  }, [loading, isAuthenticated, user]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">加载中...</p>
      </div>
    );
  }

  return <LoginForm />;
}
