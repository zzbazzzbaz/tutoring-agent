// 班级管理-班级会话只读详情页
"use client";

import { useParams, useSearchParams } from "next/navigation";
import { ReadOnlyChatView } from "@/components/chat/ReadOnlyChatView";

export default function ClassSessionDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const classId = params.classId as string;
  const sid = params.sid as string;
  // 支持通过 ?back= 指定返回地址（如从学生分析页进入时返回学生分析页）
  const backHref = searchParams.get("back") || `/teacher/manage/classes/${classId}/sessions`;

  return (
    <div className="h-full overflow-y-auto">
      <ReadOnlyChatView
        sessionId={sid}
        backHref={backHref}
      />
    </div>
  );
}
