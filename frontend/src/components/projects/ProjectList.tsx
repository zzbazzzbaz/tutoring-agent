"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { projectsApi } from "@/lib/api/projects";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Project } from "@/lib/types";

export function ProjectList({
  basePath,
  publishedOnly = false,
}: {
  basePath: string;
  publishedOnly?: boolean;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    projectsApi
      .list(publishedOnly ? "published" : undefined)
      .then(setProjects)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [publishedOnly]);

  if (loading) return <div className="p-4">加载中...</div>;

  if (projects.length === 0) {
    return (
      <div className="p-4 text-muted-foreground">暂无项目</div>
    );
  }

  return (
    <div className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <Link
          key={project.id}
          href={`${basePath}/projects/${project.id}`}
        >
          <Card className="transition-shadow hover:shadow-md">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">
                  {project.name}
                </CardTitle>
                {!publishedOnly && (
                  <Badge
                    variant={
                      project.status === "published"
                        ? "default"
                        : "secondary"
                    }
                  >
                    {project.status === "published" ? "已发布" : "草稿"}
                  </Badge>
                )}
              </div>
              <CardDescription className="line-clamp-2">
                {project.background_md.slice(0, 100)}
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>
      ))}
    </div>
  );
}
