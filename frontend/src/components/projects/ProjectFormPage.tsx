"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { SkeletonCard } from "@/components/ui/skeleton-loaders";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { MarkdownText } from "@/components/chat/thread/markdown-text";
import { projectsApi } from "@/lib/api/projects";
import { toast } from "sonner";
import type { Mainline, Project, ProjectStatus } from "@/lib/types";
import { MainlineEditor } from "./MainlineEditor";

export function ProjectFormPage({ projectId }: { projectId?: string }) {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [name, setName] = useState("");
  const [backgroundMd, setBackgroundMd] = useState("");
  const [mainline, setMainline] = useState<Mainline | null>(null);
  const [status, setStatus] = useState<ProjectStatus>("draft");
  const [loading, setLoading] = useState(Boolean(projectId));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    projectsApi
      .get(projectId)
      .then((data) => {
        setProject(data);
        setName(data.name);
        setBackgroundMd(data.background_md);
        setMainline(data.mainline);
        setStatus(data.status);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [projectId]);

  async function handleSave() {
    if (!name.trim() || !backgroundMd.trim()) {
      toast.error("案例名称和背景不能为空");
      return;
    }
    setSaving(true);
    try {
      if (project) {
        await projectsApi.update(project.id, {
          name,
          background_md: backgroundMd,
          mainline,
          status,
        });
        toast.success("案例已更新");
      } else {
        await projectsApi.create({ name, background_md: backgroundMd, mainline, status });
        toast.success("案例已创建");
      }
      router.push("/teacher/manage/projects");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <SkeletonCard lines={6} className="m-4" />;

  return (
    <div className="h-full overflow-y-auto p-4">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push("/teacher/manage/projects")}
        className="mb-4"
      >
        <ArrowLeft className="mr-2 size-4" />
        返回案例列表
      </Button>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">{project ? "编辑案例" : "新建案例"}</h1>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "保存中..." : "保存"}
        </Button>
      </div>

      <div className="mb-4 grid gap-4 md:grid-cols-[1fr_240px]">
        <div className="flex flex-col gap-2">
          <Label htmlFor="name">案例名称</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="请输入案例名称"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label>状态</Label>
          <RadioGroup
            value={status}
            onValueChange={(v) => setStatus(v as ProjectStatus)}
            className="flex gap-4 rounded-md border px-3 py-2"
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem value="draft" id="draft" />
              <Label htmlFor="draft">草稿</Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="published" id="published" />
              <Label htmlFor="published">已发布</Label>
            </div>
          </RadioGroup>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex min-h-[520px] flex-col gap-2">
          <Label>案例背景 Markdown</Label>
          <Textarea
            value={backgroundMd}
            onChange={(e) => setBackgroundMd(e.target.value)}
            placeholder={"## 案例描述\n请描述案例背景..."}
            className="min-h-[520px] flex-1 font-mono text-sm"
          />
        </div>
        <div className="flex min-h-[520px] flex-col gap-2">
          <Label>实时预览</Label>
          <div className="min-h-[520px] flex-1 overflow-y-auto rounded-md border bg-white p-4">
            {backgroundMd.trim() ? (
              <MarkdownText>{backgroundMd}</MarkdownText>
            ) : (
              <p className="text-sm text-muted-foreground">预览内容将在这里显示</p>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 border-t pt-4">
        <MainlineEditor value={mainline} onChange={setMainline} />
      </div>
    </div>
  );
}
