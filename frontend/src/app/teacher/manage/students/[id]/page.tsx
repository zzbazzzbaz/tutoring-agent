"use client";

import { use } from "react";
import { StudentSessionTable } from "@/components/students/StudentSessionTable";

export default function TeacherManageStudentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <div className="h-full overflow-y-auto">
      <StudentSessionTable studentId={id} />
    </div>
  );
}
