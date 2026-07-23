"use client";

import { useState } from "react";
import { KnowledgeDocumentTable } from "@/components/knowledge/KnowledgeDocumentTable";
import { KnowledgeGraphPanel } from "@/components/knowledge/KnowledgeGraphPanel";
import { KnowledgePipelineStatus } from "@/components/knowledge/KnowledgePipelineStatus";
import { KnowledgeUpload } from "@/components/knowledge/KnowledgeUpload";

export function KnowledgeBasePage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [tab, setTab] = useState<"documents" | "graph">("documents");

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
      <div className="flex gap-2">
        <button
          className={`rounded-md px-3 py-2 text-sm ${tab === "documents" ? "bg-muted font-medium" : "text-muted-foreground"}`}
          onClick={() => setTab("documents")}
        >
          文件管理
        </button>
        <button
          className={`rounded-md px-3 py-2 text-sm ${tab === "graph" ? "bg-muted font-medium" : "text-muted-foreground"}`}
          onClick={() => setTab("graph")}
        >
          知识图谱
        </button>
      </div>
      {tab === "documents" ? (
        <>
          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <KnowledgeUpload onUploaded={refresh} />
            <KnowledgePipelineStatus refreshKey={refreshKey} />
          </div>
          <KnowledgeDocumentTable refreshKey={refreshKey} onChanged={refresh} />
        </>
      ) : (
        <KnowledgeGraphPanel />
      )}
    </div>
  );
}
