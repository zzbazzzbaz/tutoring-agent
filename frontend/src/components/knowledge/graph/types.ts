import type { LightRAGGraphEdge, LightRAGGraphNode } from "@/lib/types";

export interface KnowledgeGraphData {
  nodes: LightRAGGraphNode[];
  edges: LightRAGGraphEdge[];
}

export interface GraphNodeAttributes {
  label: string;
  size: number;
  color: string;
  x: number;
  y: number;
  properties?: Record<string, unknown>;
}

export interface GraphEdgeAttributes {
  label: string;
  size: number;
  color: string;
  properties?: Record<string, unknown>;
}
