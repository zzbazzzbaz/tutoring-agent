"use client";

import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/common/Pagination";
import { lightragApi } from "@/lib/api/lightrag";
import type { LightRAGDocument, LightRAGDocumentStatus } from "@/lib/types";
import { toast } from "sonner";

const statuses: Array<{ value: LightRAGDocumentStatus; label: string }> = [
  { value: "pending", label: "待处理" },
  { value: "parsing", label: "解析中" },
  { value: "analyzing", label: "分析中" },
  { value: "processing", label: "处理中" },
  { value: "preprocessed", label: "预处理" },
  { value: "processed", label: "已完成" },
  { value: "failed", label: "失败" },
];

function statusLabel(status: string) {
  const lower = status.toLowerCase();
  return statuses.find((item) => item.value === lower)?.label ?? status;
}

function fileName(doc: LightRAGDocument) {
  return doc.file_path?.split("/").pop() || doc.id;
}

export function KnowledgeDocumentTable({
  refreshKey,
  onChanged,
}: {
  refreshKey: number;
  onChanged: () => void;
}) {
  const [documents, setDocuments] = useState<LightRAGDocument[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<LightRAGDocumentStatus | undefined>();
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const result = await lightragApi.listDocuments({
        page,
        page_size: 20,
        status_filter: statusFilter,
      });
      setDocuments(result.items);
      setTotal(result.total);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载文档失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [page, statusFilter, refreshKey]);

  async function handleDelete(doc: LightRAGDocument) {
    if (!confirm(`确定删除「${fileName(doc)}」吗？关联 chunk、实体和关系会一并删除。`)) {
      return;
    }
    try {
      await lightragApi.deleteDocument(doc.id);
      toast.success("删除任务已提交");
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    }
  }

  return (
    <div className="rounded-md border bg-white p-4">
      <div className="mb-3 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <h2 className="text-base font-semibold">文件列表</h2>
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={statusFilter ?? ""}
          onChange={(e) => {
            setPage(1);
            setStatusFilter((e.target.value || undefined) as LightRAGDocumentStatus | undefined);
          }}
        >
          <option value="">全部状态</option>
          {statuses.map((status) => (
            <option key={status.value} value={status.value}>
              {status.label}
            </option>
          ))}
        </select>
      </div>
      {loading ? (
        <p className="text-sm text-muted-foreground">加载中...</p>
      ) : documents.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无文件</p>
      ) : (
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">文件</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium">Chunks</th>
                <th className="px-4 py-2 text-left font-medium">更新时间</th>
                <th className="px-4 py-2 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} className="border-t">
                  <td className="px-4 py-2">
                    <div className="font-medium">{fileName(doc)}</div>
                    {doc.error_msg && (
                      <div className="text-xs text-destructive">{doc.error_msg}</div>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={doc.status.toLowerCase() === "failed" ? "destructive" : "secondary"}>
                      {statusLabel(doc.status)}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {doc.chunks_count ?? 0}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {doc.updated_at ? new Date(doc.updated_at).toLocaleString("zh-CN") : "-"}
                  </td>
                  <td className="px-4 py-2">
                    <Button size="sm" variant="ghost" onClick={() => handleDelete(doc)}>
                      <Trash2 className="size-4 text-destructive" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 pb-4">
            <Pagination page={page} pageSize={20} total={total} onPageChange={setPage} />
          </div>
        </div>
      )}
    </div>
  );
}
