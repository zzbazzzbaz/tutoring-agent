/*
 * 学生管理已并入班级管理，全局学生会话详情页废弃
 * 原内容已注释，保留文件便于历史追溯
 */
/* 
"use client";

import { use } from "react";
import { StudentSessionDetail } from "@/components/students/StudentSessionDetail";

export default function TeacherManageStudentSessionDetailPage({
  params,
}: {
  params: Promise<{ id: string; sid: string }>;
}) {
  const { id, sid } = use(params);
  return (
    <div className="h-full overflow-y-auto">
      <StudentSessionDetail studentId={id} sessionId={sid} />
    </div>
  );
}
 */