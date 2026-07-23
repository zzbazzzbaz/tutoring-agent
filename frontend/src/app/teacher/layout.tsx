"use client";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppSidebar } from "@/components/layout/AppSidebar";

export default function TeacherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RoleGuard role="teacher">
      <div className="flex h-screen">
        <AppSidebar role="teacher" />
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </RoleGuard>
  );
}
