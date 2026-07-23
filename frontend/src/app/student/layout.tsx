"use client";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppSidebar } from "@/components/layout/AppSidebar";

export default function StudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RoleGuard role="student">
      <div className="flex h-screen">
        <AppSidebar role="student" />
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </RoleGuard>
  );
}
