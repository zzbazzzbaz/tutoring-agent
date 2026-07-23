"use client";

import { StudentTable } from "@/components/students/StudentTable";

export default function TeacherStudentsPage() {
  return (
    <div className="h-full overflow-y-auto">
      <StudentTable />
    </div>
  );
}
