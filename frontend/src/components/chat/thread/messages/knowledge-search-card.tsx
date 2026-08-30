"use client";

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronDown,
  ChevronUp,
  FileText,
  Maximize2,
  Network,
  Search,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  SigmaContainer,
  useCamera,
  useRegisterEvents,
  useSigma,
} from "@react-sigma/core";
import { useLayoutForce } from "@react-sigma/layout-force";
import Graph from "graphology";
import { EdgeRectangleProgram } from "sigma/rendering";
import { NodeBorderProgram } from "@sigma/node-border";
import "@react-sigma/core/lib/style.css";

const NODE_COLOR = "#0b3d31";
const NODE_BORDER = "#e5e7eb";
const NODE_SELECTED = "#f57f17";
const EDGE_COLOR = "#d3d3d3";

export type KnowledgeSearchResult = {
  query?: string;
  response?: string;
  chunks?: { content: string; score?: number; file_path?: string }[];
  entities?: {
    entity_name: string;
    entity_type?: string;
    description?: string;
  }[];
  relations?: { src_id: string; tgt_id: string; description?: string }[];
  error?: string;
};

export function parseKnowledgeSearchResult(
  content: unknown,
): KnowledgeSearchResult | null {
  if (typeof content !== "string") return null;
  try {
    const parsed = JSON.parse(content);
    if (!parsed || typeof parsed !== "object") return null;
    return parsed as KnowledgeSearchResult;
  } catch {
    return null;
  }
}

function GraphTab({
  entities,
  relations,
}: {
  entities: KnowledgeSearchResult["entities"];
  relations: KnowledgeSearchResult["relations"];
}) {
  const [selected, setSelected] = useState<string | null>(null);

  const graph = useMemo(() => {
    const g = new Graph();
    const degree: Record<string, number> = {};
    const addNode = (name: string, isMissing = false) => {
      if (g.hasNode(name)) return;
      g.addNode(name, {
        label: name,
        size: isMissing ? 3 : Math.min(4 + (degree[name] ?? 0) * 1.2, 16),
        color: isMissing ? "#9ca3af" : NODE_COLOR,
        borderColor: NODE_BORDER,
        x: Math.random() * 100 - 50,
        y: Math.random() * 100 - 50,
      });
    };
    for (const r of relations ?? []) {
      degree[r.src_id] = (degree[r.src_id] ?? 0) + 1;
      degree[r.tgt_id] = (degree[r.tgt_id] ?? 0) + 1;
    }
    const entityNames = new Set(
      (entities ?? []).map((e) => e.entity_name || "未知实体"),
    );
    for (const e of entities ?? []) {
      addNode(e.entity_name || "未知实体");
    }
    for (const r of relations ?? []) {
      if (!entityNames.has(r.src_id)) addNode(r.src_id, true);
      if (!entityNames.has(r.tgt_id)) addNode(r.tgt_id, true);
      if (g.hasNode(r.src_id) && g.hasNode(r.tgt_id)) {
        g.addEdge(r.src_id, r.tgt_id, {
          label: r.description || "",
          size: 1,
        });
      }
    }
    return g;
  }, [entities, relations]);

  return (
    <div className="border-ink/10 bg-paper relative h-64 overflow-hidden rounded-md border">
      <SigmaContainer
        graph={graph}
        settings={{
          defaultNodeType: "border",
          defaultEdgeType: "rect",
          renderEdgeLabels: false,
          hideEdgesOnMove: true,
          defaultEdgeColor: EDGE_COLOR,
          labelColor: { color: "#000", attribute: "labelColor" },
          labelSize: 12,
          labelRenderedSizeThreshold: 4,
          edgeProgramClasses: { rect: EdgeRectangleProgram },
          nodeProgramClasses: { border: NodeBorderProgram },
        }}
        className="!h-full !w-full overflow-hidden"
      >
        <GraphSetup />
        <GraphEvents />
        <GraphClickHandler
          selected={selected}
          onSelect={setSelected}
        />
        <GraphControls />
      </SigmaContainer>
      <div className="bg-paper/90 border-ink/10 text-muted-foreground pointer-events-none absolute inset-x-0 bottom-0 z-10 border-t px-3 py-2 text-xs leading-relaxed backdrop-blur-sm">
        {selected
          ? (entities ?? []).find((e) => e.entity_name === selected)
              ?.description || selected
          : "点击实体节点查看描述"}
      </div>
    </div>
  );
}

function GraphSetup() {
  const sigma = useSigma();
  const layout = useLayoutForce({
    maxIterations: 800,
    settings: {
      attraction: 0.0003,
      repulsion: 0.3,
      gravity: 0.0001,
      inertia: 0.6,
      maxMove: 40,
    },
  });

  useEffect(() => {
    const graph = sigma.getGraph();
    if (!graph || graph.order === 0) return;
    const positions = layout.positions();
    graph.updateEachNodeAttributes(
      (node, attr) => {
        const pos = positions[node];
        if (pos) {
          attr.x = pos.x;
          attr.y = pos.y;
        }
        return attr;
      },
      { attributes: ["x", "y"] },
    );
    sigma.refresh();
    try {
      sigma.getCamera().animatedReset();
    } catch {
      /* ignore */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sigma]);

  return null;
}

function GraphEvents() {
  const registerEvents = useRegisterEvents();
  const sigma = useSigma();
  const [draggedNode, setDraggedNode] = useState<string | null>(null);

  useEffect(() => {
    registerEvents({
      downNode: (e) => {
        setDraggedNode(e.node);
        sigma.getGraph().setNodeAttribute(e.node, "highlighted", true);
      },
      mousemovebody: (e) => {
        if (!draggedNode) return;
        const pos = sigma.viewportToGraph(e);
        sigma.getGraph().setNodeAttribute(draggedNode, "x", pos.x);
        sigma.getGraph().setNodeAttribute(draggedNode, "y", pos.y);
        e.preventSigmaDefault();
        e.original.preventDefault();
        e.original.stopPropagation();
      },
      mouseup: () => {
        if (draggedNode) {
          setDraggedNode(null);
          sigma.getGraph().removeNodeAttribute(draggedNode, "highlighted");
        }
      },
    });
  }, [registerEvents, sigma, draggedNode]);

  return null;
}

function GraphClickHandler({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (node: string | null) => void;
}) {
  const sigma = useSigma();
  const registerEvents = useRegisterEvents();

  useEffect(() => {
    const resetColors = () => {
      sigma.getGraph().forEachNode((node) => {
        sigma.getGraph().setNodeAttribute(node, "color", NODE_COLOR);
        sigma.getGraph().setNodeAttribute(node, "borderColor", NODE_BORDER);
      });
    };
    registerEvents({
      clickNode: (e) => {
        resetColors();
        sigma.getGraph().setNodeAttribute(e.node, "color", NODE_SELECTED);
        sigma.getGraph().setNodeAttribute(e.node, "borderColor", NODE_SELECTED);
        onSelect(e.node);
      },
      clickStage: () => {
        resetColors();
        onSelect(null);
      },
    });
  }, [registerEvents, sigma, onSelect, selected]);

  return null;
}

function GraphControls() {
  const { zoomIn, zoomOut } = useCamera({ duration: 200, factor: 1.5 });
  const sigma = useSigma();

  const resetView = () => {
    try {
      sigma.setCustomBBox(null);
      sigma.refresh();
      sigma
        .getCamera()
        .animate({ x: 0.5, y: 0.5, ratio: 1.1 }, { duration: 500 });
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="absolute right-2 bottom-8 z-10 flex flex-col gap-1.5">
      <GraphControlButton
        onClick={zoomIn}
        title="放大"
      >
        <ZoomIn className="size-4" />
      </GraphControlButton>
      <GraphControlButton
        onClick={zoomOut}
        title="缩小"
      >
        <ZoomOut className="size-4" />
      </GraphControlButton>
      <GraphControlButton
        onClick={resetView}
        title="重置视图"
      >
        <Maximize2 className="size-4" />
      </GraphControlButton>
    </div>
  );
}

function GraphControlButton({
  onClick,
  title,
  children,
}: {
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="bg-paper-card/90 hover:bg-paper-card border-ink/10 text-ink/70 hover:text-ink flex size-8 cursor-pointer items-center justify-center rounded-lg border shadow-sm backdrop-blur-sm transition-colors"
    >
      {children}
    </button>
  );
}

export function KnowledgeSearchCard({
  result,
}: {
  result: KnowledgeSearchResult;
}) {
  const [expanded, setExpanded] = useState(false);
  const [tab, setTab] = useState<"chunks" | "graph">("chunks");

  const chunkCount = result.chunks?.length ?? 0;
  const entityCount = result.entities?.length ?? 0;
  const hasData = chunkCount > 0 || entityCount > 0;
  const hasGraph = entityCount > 0 && (result.relations?.length ?? 0) > 0;

  if (result.error || !hasData) {
    return (
      <div className="border-ink/10 bg-paper text-muted-foreground flex items-center gap-2 rounded-lg border px-3 py-2 text-xs">
        <Search className="size-3.5 shrink-0" />
        {result.error ?? "未检索到相关知识"}
        {result.query && <span>「{result.query}」</span>}
      </div>
    );
  }

  return (
    <div className="border-ink/10 bg-paper-card overflow-hidden rounded-lg border">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="hover:bg-paper flex w-full cursor-pointer items-center justify-between gap-2 px-4 py-2.5 text-left transition-colors"
      >
        <span className="text-ink flex min-w-0 items-center gap-2 text-sm font-medium">
          <Search className="text-brand size-4 shrink-0" />
          <span className="shrink-0">检索知识库</span>
          {result.query && (
            <span className="text-muted-foreground min-w-0 truncate">
              「{result.query}」
            </span>
          )}
        </span>
        <span className="text-muted-foreground flex shrink-0 items-center gap-3 text-xs">
          {chunkCount > 0 && <span>{chunkCount} 片段</span>}
          {entityCount > 0 && <span>{entityCount} 实体</span>}
          {expanded ? (
            <ChevronUp className="size-4" />
          ) : (
            <ChevronDown className="size-4" />
          )}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            {hasGraph && (
              <div className="border-ink/10 bg-paper flex gap-1 border-b px-3 pt-2">
                <TabButton
                  active={tab === "chunks"}
                  onClick={() => setTab("chunks")}
                  icon={<FileText className="size-3.5" />}
                >
                  引用
                </TabButton>
                <TabButton
                  active={tab === "graph"}
                  onClick={() => setTab("graph")}
                  icon={<Network className="size-3.5" />}
                >
                  知识图谱
                </TabButton>
              </div>
            )}

            <div className="space-y-2 p-3">
              {tab === "graph" && hasGraph ? (
                <GraphTab
                  entities={result.entities}
                  relations={result.relations}
                />
              ) : (
                <>
                  {result.response && (
                    <p className="text-muted-foreground text-xs leading-relaxed">
                      {result.response.slice(0, 200)}
                    </p>
                  )}
                  {(result.chunks ?? []).map((chunk, idx) => (
                    <div
                      key={idx}
                      className="border-ink/10 bg-paper rounded-md border px-3 py-2"
                    >
                      <p className="text-ink line-clamp-3 text-sm leading-relaxed">
                        {chunk.content}
                      </p>
                      <p className="text-muted-foreground mt-1 flex items-center gap-2 text-xs">
                        {chunk.file_path && (
                          <span className="truncate">{chunk.file_path}</span>
                        )}
                        {typeof chunk.score === "number" && (
                          <span className="shrink-0">
                            相关度 {(chunk.score * 100).toFixed(0)}%
                          </span>
                        )}
                      </p>
                    </div>
                  ))}
                  {chunkCount === 0 && (
                    <p className="text-muted-foreground text-xs">
                      仅检索到知识图谱实体，无文本片段
                    </p>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex cursor-pointer items-center gap-1.5 rounded-t-md px-3 py-1.5 text-xs font-medium transition-colors",
        active
          ? "bg-paper-card text-ink shadow-sm"
          : "text-muted-foreground hover:bg-paper hover:text-ink",
      )}
    >
      {icon}
      {children}
    </button>
  );
}
