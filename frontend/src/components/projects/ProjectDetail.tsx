"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { projectsApi } from "@/lib/api/projects";
import { MarkdownText } from "@/components/chat/thread/markdown-text";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft } from "lucide-react";
import type { Project } from "@/lib/types";
import { SkeletonCard } from "@/components/ui/skeleton-loaders";

export function ProjectDetail({
  id,
  basePath,
  readOnly = false,
}: {
  id: string;
  basePath: string;
  readOnly?: boolean;
}) {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    projectsApi
      .get(id)
      .then(setProject)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <SkeletonCard lines={5} className="m-4" />;
  if (!project) return <div className="p-4">案例不存在</div>;

  return (
    <div className="mx-auto max-w-3xl p-6">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push(`${basePath}/projects`)}
        className="mb-4"
      >
        <ArrowLeft className="mr-2 size-4" />
        返回列表
      </Button>
      <div className="mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <Badge
            variant={
              project.status === "published" ? "default" : "secondary"
            }
          >
            {project.status === "published" ? "已发布" : "草稿"}
          </Badge>
        </div>
      </div>
      <div className="prose prose-sm max-w-none">
        <h2 className="mb-3 text-lg font-semibold">案例背景</h2>
        <MarkdownText>{project.background_md}</MarkdownText>
      </div>
      {readOnly && (
        <div className="mt-8 border-t pt-4">
          <Button
            onClick={() =>
              router.push(`/student/chat?project=${project.id}`)
            }
          >
            在对话中讨论此案例
          </Button>
        </div>
      )}
    </div>
  );
}
