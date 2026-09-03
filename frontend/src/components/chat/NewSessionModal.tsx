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
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSessions } from "./SessionProvider";
import { projectsApi } from "@/lib/api/projects";
import type { Project } from "@/lib/types";
import { toast } from "sonner";

export function NewSessionModal({
  open,
  onClose,
  onCreated,
  preselectProjectId,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (sessionId: string) => void;
  preselectProjectId?: string;
}) {
  const { createSession } = useSessions();
  const [mode, setMode] = useState<"free" | "project">("free");
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && preselectProjectId) {
      setMode("project");
      setSelectedProject(preselectProjectId);
    }
  }, [open, preselectProjectId]);

  useEffect(() => {
    if (open && mode === "project") {
      projectsApi
        .list("published", 1, 100)
        .then((data) => setProjects(data.items))
        .catch(console.error);
    }
  }, [open, mode]);

  async function handleCreate() {
    if (mode === "project" && !selectedProject) {
      toast.error("请选择一个案例");
      return;
    }
    setLoading(true);
    try {
      const session = await createSession(
        mode,
        mode === "project" ? selectedProject : undefined,
      );
      onCreated(session.id);
      onClose();
      setMode("free");
      setSelectedProject("");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "创建会话失败",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建会话</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="flex flex-col gap-2">
            <RadioGroup
              value={mode}
              onValueChange={(v) => setMode(v as "free" | "project")}
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem value="free" id="free" />
                <Label htmlFor="free">自由学习模式</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="project" id="project" />
                <Label htmlFor="project">案例模式</Label>
              </div>
            </RadioGroup>
          </div>
          {mode === "project" && (
            <div className="flex flex-col gap-2">
              <Label>选择案例</Label>
              <Select
                value={selectedProject}
                onValueChange={setSelectedProject}
              >
                <SelectTrigger>
                  <SelectValue placeholder="请选择案例" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleCreate} disabled={loading}>
            {loading ? "创建中..." : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
