"use client";

import { ManagementLayout } from "@/components/layout/ManagementLayout";

export default function StudentManageLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ManagementLayout role="student">{children}</ManagementLayout>;
}
