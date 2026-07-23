"use client";

import { use } from "react";
import { ReadOnlyChatView } from "@/components/chat/ReadOnlyChatView";

export default function StudentSessionViewPage({
  params,
}: {
  params: Promise<{ id: string; sid: string }>;
}) {
  const { id, sid } = use(params);
  return (
    <div className="h-full">
      <ReadOnlyChatView studentId={id} sessionId={sid} />
    </div>
  );
}
