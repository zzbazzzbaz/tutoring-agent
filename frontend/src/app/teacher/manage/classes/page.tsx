// 班级管理-班级详细页面
"use client";

import { ClassList } from "@/components/classes/ClassList";

export default function TeacherManageClassesPage() {
  return (
    <div className="h-full overflow-y-auto">
      <ClassList />
    </div>
  );
}