"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { MarkdownText } from "@/components/chat/thread/markdown-text";
import { projectsApi } from "@/lib/api/projects";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { Project, ProjectStatus } from "@/lib/types";

export function ProjectFormModal({
  open,
  onClose,
  onSaved,
  project,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  project?: Project;
}) {
  const [name, setName] = useState("");
  const [backgroundMd, setBackgroundMd] = useState("");
  const [status, setStatus] = useState<ProjectStatus>("draft");
  const [tab, setTab] = useState<"edit" | "preview">("edit");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (project) {
      setName(project.name);
      setBackgroundMd(project.background_md);
      setStatus(project.status as ProjectStatus);
    } else {
      setName("");
      setBackgroundMd("");
      setStatus("draft");
    }
    setTab("edit");
  }, [project, open]);

  async function handleSave() {
    if (!name.trim() || !backgroundMd.trim()) {
      toast.error("项目名称和背景不能为空");
      return;
    }
    setLoading(true);
    try {
      if (project) {
        await projectsApi.update(project.id, {
          name,
          background_md: backgroundMd,
          status,
        });
        toast.success("项目已更新");
      } else {
        await projectsApi.create({
          name,
          background_md: backgroundMd,
          status,
        });
        toast.success("项目已创建");
      }
      onSaved();
      onClose();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "保存失败",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {project ? "编辑项目" : "新建项目"}
          </DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="name">项目名称</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="请输入项目名称"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label>项目背景 (Markdown)</Label>
            <div className="flex gap-2 border-b">
              <button
                className={cn(
                  "px-3 py-1 text-sm",
                  tab === "edit"
                    ? "border-b-2 border-primary font-medium"
                    : "text-muted-foreground",
                )}
                onClick={() => setTab("edit")}
              >
                编辑
              </button>
              <button
                className={cn(
                  "px-3 py-1 text-sm",
                  tab === "preview"
                    ? "border-b-2 border-primary font-medium"
                    : "text-muted-foreground",
                )}
                onClick={() => setTab("preview")}
              >
                预览
              </button>
            </div>
            {tab === "edit" ? (
              <Textarea
                value={backgroundMd}
                onChange={(e) => setBackgroundMd(e.target.value)}
                placeholder={"## 项目描述\n请描述项目背景..."}
                className="min-h-[200px] font-mono text-sm"
              />
            ) : (
              <div className="min-h-[200px] overflow-y-auto rounded-md border p-3">
                <MarkdownText>{backgroundMd}</MarkdownText>
              </div>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label>状态</Label>
            <RadioGroup
              value={status}
              onValueChange={(v) => setStatus(v as ProjectStatus)}
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="draft" id="draft" />
                <Label htmlFor="draft">
                  草稿 (仅教师可见)
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="published" id="published" />
                <Label htmlFor="published">
                  已发布 (学生可见)
                </Label>
              </div>
            </RadioGroup>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={loading}>
            {loading ? "保存中..." : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
