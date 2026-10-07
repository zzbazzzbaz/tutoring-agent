"use client";

import { SessionProvider } from "@/components/chat/SessionProvider";
import { StreamProvider } from "@/components/chat/StreamProvider";
import { ArtifactProvider } from "@/components/chat/thread/artifact";
import { Thread } from "@/components/chat/thread";

export default function TeacherManageProjectAiPage() {
  return (
    <SessionProvider>
      <StreamProvider>
        <ArtifactProvider>
          <div className="h-[calc(100vh-3.5rem)]">
            <Thread
              embedded
              fixedMode="case_design"
              emptyHint="描述你想设计的案例主题和学生情况，我会追问细节，最后帮你生成结构化案例草稿。"
            />
          </div>
        </ArtifactProvider>
      </StreamProvider>
    </SessionProvider>
  );
}
