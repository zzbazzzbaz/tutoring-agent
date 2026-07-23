"use client";

import "@/lightrag-webui/i18n";
import GraphViewer from "@/lightrag-webui/features/GraphViewer";

export function KnowledgeGraphPanel() {
  return (
    <div className="h-[calc(100vh-8.5rem)] min-h-[640px] overflow-hidden rounded-xl border bg-background">
      <GraphViewer />
    </div>
  );
}
