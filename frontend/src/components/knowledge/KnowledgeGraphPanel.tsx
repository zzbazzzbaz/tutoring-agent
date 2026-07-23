"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { lightragApi } from "@/lib/api/lightrag";
import type { LightRAGGraphResponse } from "@/lib/types";
import { toast } from "sonner";
import { GraphViewer } from "./graph/GraphViewer";

function normalizeLabels(value: string[] | { labels: string[] }) {
  return Array.isArray(value) ? value : value.labels ?? [];
}

export function KnowledgeGraphPanel() {
  const [popularLabels, setPopularLabels] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [label, setLabel] = useState("");
  const [maxDepth, setMaxDepth] = useState(3);
  const [maxNodes, setMaxNodes] = useState(1000);
  const [graph, setGraph] = useState<LightRAGGraphResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    lightragApi
      .popularLabels(30)
      .then((result) => {
        const labels = normalizeLabels(result);
        setPopularLabels(labels);
        if (labels[0]) setLabel(labels[0]);
      })
      .catch(console.error);
  }, []);

  async function handleSearch() {
    if (!search.trim()) return;
    try {
      const labels = normalizeLabels(await lightragApi.searchLabels(search.trim(), 20));
      setPopularLabels(labels);
      if (labels[0]) setLabel(labels[0]);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "搜索标签失败");
    }
  }

  async function loadGraph() {
    if (!label.trim()) {
      toast.error("请选择或输入图谱标签");
      return;
    }
    setLoading(true);
    try {
      setGraph(await lightragApi.graph(label.trim(), maxDepth, maxNodes));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载图谱失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4 rounded-md border bg-white p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium">标签</label>
          <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="输入实体标签" />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">深度</label>
          <Input
            type="number"
            min={1}
            max={10}
            value={maxDepth}
            onChange={(e) => setMaxDepth(Number(e.target.value) || 1)}
            className="w-24"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">节点上限</label>
          <Input
            type="number"
            min={1}
            max={5000}
            value={maxNodes}
            onChange={(e) => setMaxNodes(Number(e.target.value) || 1000)}
            className="w-28"
          />
        </div>
        <Button onClick={loadGraph} disabled={loading}>
          {loading ? "加载中..." : "加载图谱"}
        </Button>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索标签"
          onKeyDown={(e) => {
            if (e.key === "Enter") void handleSearch();
          }}
        />
        <Button variant="outline" onClick={handleSearch}>
          <Search className="mr-2 size-4" />
          搜索
        </Button>
      </div>

      {popularLabels.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {popularLabels.slice(0, 30).map((item) => (
            <Button
              key={item}
              variant={item === label ? "secondary" : "outline"}
              size="sm"
              onClick={() => setLabel(item)}
            >
              {item}
            </Button>
          ))}
        </div>
      )}

      {graph ? (
        <GraphViewer data={graph} />
      ) : (
        <div className="flex h-[320px] items-center justify-center rounded-md border text-sm text-muted-foreground">
          选择标签后加载知识图谱。
        </div>
      )}
    </div>
  );
}
