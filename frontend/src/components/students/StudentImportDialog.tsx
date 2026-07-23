"use client";

import { useState, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { usersApi } from "@/lib/api/users";
import { toast } from "sonner";
import { Upload, FileSpreadsheet } from "lucide-react";
import type { ImportResult } from "@/lib/types";

export function StudentImportDialog({
  open,
  onClose,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (selected) {
      if (!/\.(xlsx|xls)$/i.test(selected.name)) {
        toast.error("请上传 .xlsx 或 .xls 文件");
        return;
      }
      setFile(selected);
      setResult(null);
    }
  }

  async function handleImport() {
    if (!file) {
      toast.error("请选择文件");
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await usersApi.import(formData);
      setResult(res);
      onImported();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "导入失败",
      );
    } finally {
      setLoading(false);
    }
  }

  function handleClose() {
    setFile(null);
    setResult(null);
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>导入学生</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="rounded-md border-2 border-dashed p-6 text-center">
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <FileSpreadsheet className="size-8 text-green-500" />
                <p className="text-sm font-medium">{file.name}</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => inputRef.current?.click()}
                >
                  重新选择
                </Button>
              </div>
            ) : (
              <div
                className="flex cursor-pointer flex-col items-center gap-2"
                onClick={() => inputRef.current?.click()}
              >
                <Upload className="size-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  点击选择文件或拖拽到此处
                </p>
                <p className="text-xs text-muted-foreground">
                  支持 .xlsx / .xls
                </p>
              </div>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xls"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>
          {result && (
            <div className="rounded-md border p-4">
              <p className="font-medium">导入完成</p>
              <div className="mt-2 flex gap-4 text-sm">
                <span className="text-green-600">
                  ✅ 成功: {result.created}
                </span>
                <span className="text-yellow-600">
                  ⏭️ 跳过: {result.skipped}
                </span>
                <span className="text-muted-foreground">
                  总计: {result.total}
                </span>
              </div>
              {result.errors.length > 0 && (
                <div className="mt-2">
                  <p className="text-sm text-red-600">错误详情:</p>
                  <ul className="ml-4 list-disc text-xs text-red-600">
                    {result.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            {result ? "关闭" : "取消"}
          </Button>
          {!result && (
            <Button onClick={handleImport} disabled={loading || !file}>
              {loading ? "导入中..." : "导入"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
