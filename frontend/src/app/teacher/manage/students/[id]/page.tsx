/*
 * 学生管理已并入班级管理，全局学生详情页废弃
 * 原内容已注释，保留文件便于历史追溯
 */
/* "use client";

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
 */