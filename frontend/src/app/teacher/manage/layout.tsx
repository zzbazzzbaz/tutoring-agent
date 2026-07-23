"use client";

import { ManagementLayout } from "@/components/layout/ManagementLayout";

export default function TeacherManageLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ManagementLayout role="teacher">{children}</ManagementLayout>;
}
