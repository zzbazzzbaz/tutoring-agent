import Graph from "graphology";
import type { LightRAGGraphResponse } from "@/lib/types";
import type { GraphEdgeAttributes, GraphNodeAttributes } from "./types";

function stringValue(value: unknown) {
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function numberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function nodeLabel(id: string, properties?: Record<string, unknown>) {
  return stringValue(properties?.entity_name) ?? stringValue(properties?.label) ?? id;
}

function edgeLabel(type?: string, properties?: Record<string, unknown>) {
  return stringValue(properties?.keywords) ?? stringValue(type) ?? "";
}

export function buildKnowledgeGraph(data: LightRAGGraphResponse) {
  const graph = new Graph<GraphNodeAttributes, GraphEdgeAttributes>({ multi: true });
  const radius = Math.max(1, data.nodes.length / 8);

  data.nodes.forEach((node, index) => {
    const angle = (index / Math.max(1, data.nodes.length)) * Math.PI * 2;
    graph.addNode(node.id, {
      label: nodeLabel(node.id, node.properties),
      size: 8,
      color: "#2563EB",
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
      properties: node.properties,
    });
  });

  data.edges.forEach((edge, index) => {
    if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) return;
    const weight = numberValue(edge.properties?.weight) ?? 1;
    graph.addDirectedEdgeWithKey(edge.id ?? `edge-${index}`, edge.source, edge.target, {
      label: edgeLabel(edge.type, edge.properties),
      size: Math.max(1, Math.min(6, weight)),
      color: "#94A3B8",
      properties: edge.properties,
    });
  });

  return graph;
}
