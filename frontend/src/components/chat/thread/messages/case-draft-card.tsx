import Link from "next/link";
import { FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { CaseDraftToolResult } from "@/lib/case-draft";

export function CaseDraftCard({ result }: { result: CaseDraftToolResult }) {
  if (!result.ok) {
    return (
      <div className="mr-auto max-w-3xl rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        案例保存未成功：{result.error}
      </div>
    );
  }
  return (
    <div className="border-ink/10 bg-paper-card mr-auto max-w-3xl overflow-hidden rounded-lg border">
      <div className="border-ink/10 bg-paper border-b px-4 py-3">
        <p className="text-ink/50 text-xs">
          {result.created ? "案例草稿已生成" : "案例草稿已更新"}
        </p>
        <h3 className="text-ink mt-1 flex items-center gap-2 font-medium">
          <FileText className="text-ink/40 size-4" />
          {result.projectName}
        </h3>
      </div>
      <div className="flex items-center justify-between gap-3 p-4">
        <span className="text-ink/60 text-sm">
          共 {result.stageCount} 个学习阶段 · 草稿
        </span>
        <Button
          size="sm"
          asChild
          className="bg-gradient-to-r from-[#2d59df] to-[#2249c4] text-blue-50 hover:from-[#2d59df] hover:to-[#2249c4]"
        >
          <Link href={`/teacher/manage/projects/${result.projectId}/edit`}>
            打开编辑
          </Link>
        </Button>
      </div>
    </div>
  );
}
