"use client";

import { useMemo, useState } from "react";
import { SigmaContainer, useLoadGraph, useRegisterEvents } from "@react-sigma/core";
import "@react-sigma/core/lib/style.css";
import type { LightRAGGraphResponse } from "@/lib/types";
import { buildKnowledgeGraph } from "./graphAdapter";

function GraphLoader({
  data,
  onSelectNode,
}: {
  data: LightRAGGraphResponse;
  onSelectNode: (node: string | null) => void;
}) {
  const loadGraph = useLoadGraph();
  const registerEvents = useRegisterEvents();
  const graph = useMemo(() => buildKnowledgeGraph(data), [data]);

  useMemo(() => {
    loadGraph(graph);
    registerEvents({
      clickNode: (event) => onSelectNode(event.node),
      clickStage: () => onSelectNode(null),
    });
  }, [graph, loadGraph, onSelectNode, registerEvents]);

  return null;
}

export function GraphViewer({ data }: { data: LightRAGGraphResponse }) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const selected = data.nodes.find((node) => node.id === selectedNode);

  if (data.nodes.length === 0) {
    return (
      <div className="flex h-[520px] items-center justify-center rounded-md border text-sm text-muted-foreground">
        暂无图谱数据
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <div className="h-[520px] overflow-hidden rounded-md border bg-white">
        <SigmaContainer
          style={{ height: "100%", width: "100%" }}
          settings={{ allowInvalidContainer: true, renderEdgeLabels: true }}
        >
          <GraphLoader data={data} onSelectNode={setSelectedNode} />
        </SigmaContainer>
      </div>
      <div className="h-[520px] overflow-y-auto rounded-md border bg-white p-4 text-sm">
        <h3 className="mb-2 font-semibold">节点详情</h3>
        {selected ? (
          <div className="space-y-2">
            <p className="font-medium">{selected.id}</p>
            <pre className="whitespace-pre-wrap rounded bg-muted p-3 text-xs">
              {JSON.stringify(selected.properties ?? {}, null, 2)}
            </pre>
          </div>
        ) : (
          <p className="text-muted-foreground">点击图谱中的节点查看详情。</p>
        )}
      </div>
    </div>
  );
}
