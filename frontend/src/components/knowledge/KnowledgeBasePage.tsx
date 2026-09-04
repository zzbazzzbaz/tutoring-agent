"use client";

import { useState } from "react";
import { KnowledgeDocumentTable } from "@/components/knowledge/KnowledgeDocumentTable";
import { KnowledgeGraphPanel } from "@/components/knowledge/KnowledgeGraphPanel";
import { KnowledgePipelineStatus } from "@/components/knowledge/KnowledgePipelineStatus";
import { KnowledgeUpload } from "@/components/knowledge/KnowledgeUpload";
import { cn } from "@/lib/utils";

export function KnowledgeBasePage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [tab, setTab] = useState<"documents" | "graph">("documents");

  function refresh() {
    setRefreshKey((key) => key + 1);
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#f0f2f5] dark:bg-[#0f172a]">
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-ink/10 bg-paper-card px-4">
        <h1 className="text-base font-semibold">知识库</h1>
        <div className="flex rounded-lg bg-paper p-1">
          {[
            ["documents", "文件"],
            ["graph", "图谱"],
          ].map(([value, label]) => (
            <button
              key={value}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm transition-colors",
                tab === value
                  ? "bg-paper-card font-medium shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setTab(value as "documents" | "graph")}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {tab === "documents" ? (
          <div className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
              <KnowledgeUpload onUploaded={refresh} />
              <KnowledgePipelineStatus refreshKey={refreshKey} />
            </div>
            <KnowledgeDocumentTable refreshKey={refreshKey} onChanged={refresh} />
          </div>
        ) : (
          <KnowledgeGraphPanel />
        )}
      </div>
    </div>
  );
}
