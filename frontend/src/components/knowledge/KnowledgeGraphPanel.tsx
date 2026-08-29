"use client";

import "@/lightrag-webui/i18n";
import dynamic from "next/dynamic";

const GraphViewer = dynamic(
  () => import("@/lightrag-webui/features/GraphViewer"),
  { ssr: false },
);

export function KnowledgeGraphPanel() {
  return (
    <div className="h-[calc(100vh-8.5rem)] min-h-[640px] overflow-hidden rounded-xl border border-ink/25 bg-paper-card">
      <GraphViewer />
    </div>
  );
}
