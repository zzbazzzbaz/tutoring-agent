"use client";

import { RoleGuard } from "@/components/auth/RoleGuard";

export default function TeacherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RoleGuard role="teacher">
      <div className="h-screen overflow-hidden">{children}</div>
    </RoleGuard>
  );
}
