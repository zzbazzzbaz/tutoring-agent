"use client";

import { useState } from "react";
import { KnowledgeDocumentTable } from "@/components/knowledge/KnowledgeDocumentTable";
import { KnowledgePipelineStatus } from "@/components/knowledge/KnowledgePipelineStatus";
import { KnowledgeUpload } from "@/components/knowledge/KnowledgeUpload";

export function KnowledgeBasePage() {
  const [refreshKey, setRefreshKey] = useState(0);

  function refresh() {
    setRefreshKey((key) => key + 1);
  }

  return (
    <div className="space-y-4 p-4">
      <div>
        <h1 className="text-xl font-bold">知识库</h1>
        <p className="text-sm text-muted-foreground">
          管理全局 LightRAG 文件、处理状态和知识图谱。
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <KnowledgeUpload onUploaded={refresh} />
        <KnowledgePipelineStatus refreshKey={refreshKey} />
      </div>
      <KnowledgeDocumentTable refreshKey={refreshKey} onChanged={refresh} />
      <div className="rounded-md border bg-white p-4 text-sm text-muted-foreground">
        知识图谱将在下一步接入。
      </div>
    </div>
  );
}
