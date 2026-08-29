// 班级管理-班级会话只读详情页
"use client";

import { useParams } from "next/navigation";
import { ReadOnlyChatView } from "@/components/chat/ReadOnlyChatView";

export default function ClassSessionDetailPage() {
  const params = useParams();
  const classId = params.classId as string;
  const sid = params.sid as string;

  return (
    <div className="h-full overflow-y-auto">
      <ReadOnlyChatView
        sessionId={sid}
        backHref={`/teacher/manage/classes/${classId}/sessions`}
      />
    </div>
  );
}
