"use client";

import { RoleGuard } from "@/components/auth/RoleGuard";

export default function StudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RoleGuard role="student">
      <div className="h-screen overflow-hidden">{children}</div>
    </RoleGuard>
  );
}
