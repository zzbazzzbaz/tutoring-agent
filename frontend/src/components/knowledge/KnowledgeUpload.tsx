"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { lightragApi } from "@/lib/api/lightrag";
import { toast } from "sonner";

export function KnowledgeUpload({ onUploaded }: { onUploaded: () => void }) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleUpload() {
    const file = inputRef.current?.files?.[0];
    if (!file) {
      toast.error("请选择要上传的文件");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    setLoading(true);
    try {
      const result = await lightragApi.uploadDocument(formData);
      toast.success(`文件已提交处理，Track ID: ${result.track_id}`);
      if (inputRef.current) inputRef.current.value = "";
      onUploaded();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "上传失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-md border bg-white p-4">
      <h2 className="mb-3 text-base font-semibold">文件上传</h2>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input ref={inputRef} type="file" />
        <Button onClick={handleUpload} disabled={loading}>
          <Upload className="mr-2 size-4" />
          {loading ? "上传中..." : "上传文件"}
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        上传后 LightRAG 会异步解析并构建 chunk、实体和关系。
      </p>
    </div>
  );
}
