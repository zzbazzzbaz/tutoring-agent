"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { lightragApi } from "@/lib/api/lightrag";
import type { LightRAGPipelineStatus } from "@/lib/types";

export function KnowledgePipelineStatus({ refreshKey }: { refreshKey: number }) {
  const [status, setStatus] = useState<LightRAGPipelineStatus | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [pipeline, statusCounts] = await Promise.all([
        lightragApi.pipelineStatus(),
        lightragApi.statusCounts(),
      ]);
      setStatus(pipeline);
      setCounts(statusCounts.status_counts ?? {});
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [refreshKey]);

  return (
    <div className="rounded-xl border border-ink/25 bg-[#fbf9f3] p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium">状态</h2>
        <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
          <RefreshCw className="mr-2 size-4" />
          刷新
        </Button>
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex flex-wrap gap-2">
          <Badge variant={status?.busy ? "default" : "secondary"}>
            {status?.busy ? "处理中" : "空闲"}
          </Badge>
          {Object.entries(counts).map(([key, value]) => (
            <Badge key={key} variant="outline">
              {key}: {value}
            </Badge>
          ))}
        </div>
        <p className="text-muted-foreground">
          {status?.job_name || "-"} · {status?.docs ?? 0} 文档 · {status?.cur_batch ?? 0}/
          {status?.batchs ?? 0}
        </p>
        {status?.latest_message && (
          <p className="text-muted-foreground">最近消息：{status.latest_message}</p>
        )}
      </div>
    </div>
  );
}
