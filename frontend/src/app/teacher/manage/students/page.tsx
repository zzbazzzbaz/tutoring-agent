"use client";

import { StudentTable } from "@/components/students/StudentTable";

export default function TeacherManageStudentsPage() {
  return (
    <div className="h-full overflow-y-auto">
      <StudentTable />
    </div>
  );
}
