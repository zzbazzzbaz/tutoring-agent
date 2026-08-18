// 班级表单弹窗组件
"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { classesApi } from "@/lib/api/classes";
import { toast } from "sonner";
import type { ClassInfo } from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  classData: ClassInfo | null;
  onSaved: () => void;
}

export function ClassFormDialog({ open, onOpenChange, classData, onSaved }: Props) {
  const [grade, setGrade] = useState("");
  const [classname, setClassname] = useState("");
  const [status, setStatus] = useState<"active" | "archived">("active");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (classData) {
      setGrade(classData.grade);
      setClassname(classData.classname);
      setStatus(classData.status);
    } else {
      setGrade("");
      setClassname("");
      setStatus("active");
    }
  }, [classData, open]);

  async function handleSubmit() {
    if (!grade.trim() || !classname.trim()) {
      toast.error("请填写完整信息");
      return;
    }
    setLoading(true);
    try {
      if (classData) {
        await classesApi.update(classData.id, {
          grade: grade.trim(),
          classname: classname.trim(),
          status,
        });
        toast.success("班级已更新");
      } else {
        await classesApi.create({
          grade: grade.trim(),
          classname: classname.trim(),
        });
        toast.success("班级已创建");
      }
      onSaved();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  const isEdit = !!classData;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑班级" : "新建班级"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div>
            <label className="mb-1 block text-sm font-medium">年级</label>
            <Input
              placeholder="如: 2026级"
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">班级名称</label>
            <Input
              placeholder="如: 心理1班"
              value={classname}
              onChange={(e) => setClassname(e.target.value)}
            />
          </div>
          {isEdit && (
            <div>
              <label className="mb-1 block text-sm font-medium">状态</label>
              <select
                className="flex h-10 w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={status}
                onChange={(e) => setStatus(e.target.value as "active" | "archived")}
              >
                <option value="active">活跃</option>
                <option value="archived">已归档</option>
              </select>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={loading}>
              {loading ? "保存中..." : "保存"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}