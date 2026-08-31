"use client";

import { useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  FileText,
  Plus,
  Target,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import type { Mainline, MainlineStage } from "@/lib/types";

function emptyStage(order: number): MainlineStage {
  return {
    id: `stg_${String(order).padStart(2, "0")}`,
    order,
    title: "",
    guide: "",
    deliverable: null,
  };
}

export function MainlineEditor({
  value,
  onChange,
}: {
  value: Mainline | null;
  onChange: (mainline: Mainline | null) => void;
}) {
  const [enabled, setEnabled] = useState<boolean>(!!value);
  const mainline: Mainline = value ?? { objective: "", stages: [] };

  const patchStage = (index: number, patch: Partial<MainlineStage>) => {
    const stages = mainline.stages.map((s, i) => (i === index ? { ...s, ...patch } : s));
    onChange({ ...mainline, stages });
  };

  const addStage = () => {
    const stages = [...mainline.stages, emptyStage(mainline.stages.length + 1)];
    onChange({ ...mainline, stages });
  };

  const removeStage = (index: number) => {
    const stages = mainline.stages
      .filter((_, i) => i !== index)
      .map((s, i) => ({ ...s, order: i + 1 }));
    onChange({ ...mainline, stages });
  };

  const moveStage = (index: number, dir: -1 | 1) => {
    const target = index + dir;
    if (target < 0 || target >= mainline.stages.length) return;
    const stages = [...mainline.stages];
    [stages[index], stages[target]] = [stages[target], stages[index]];
    onChange({ ...mainline, stages: stages.map((s, i) => ({ ...s, order: i + 1 })) });
  };

  const toggleDeliverable = (index: number, on: boolean) => {
    patchStage(index, {
      deliverable: on
        ? { title: "", instructions: "" }
        : null,
    });
  };

  if (!enabled) {
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-dashed border-ink/15 p-4">
        <p className="text-sm text-ink/55">
          配置结构化学习主线后，项目模式会话会按阶段引导学生学习，并在前端展示进度。
        </p>
        <div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              setEnabled(true);
              onChange({ objective: "", stages: [] });
            }}
          >
            <Plus className="mr-1 size-4" />
            配置学习主线
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <Label className="text-base font-semibold">学习主线</Label>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            setEnabled(false);
            onChange(null);
          }}
        >
          移除主线
        </Button>
      </div>

      <div className="flex flex-col gap-2">
        <Label>总体学习目标</Label>
        <Input
          value={mainline.objective}
          onChange={(e) => onChange({ ...mainline, objective: e.target.value })}
          placeholder="例如：理解幼儿入园适应行为背后的心理机制，并能设计干预策略"
        />
      </div>

      <div className="flex flex-col gap-3">
        {mainline.stages.map((stage, index) => (
          <div
            key={`${stage.id}-${index}`}
            className="border-ink/10 rounded-xl border bg-paper-card p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="flex size-6 items-center justify-center rounded-full bg-brand/10 text-xs font-semibold text-brand">
                {index + 1}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  disabled={index === 0}
                  onClick={() => moveStage(index, -1)}
                  title="上移"
                >
                  <ArrowUp className="size-3.5" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  disabled={index === mainline.stages.length - 1}
                  onClick={() => moveStage(index, 1)}
                  title="下移"
                >
                  <ArrowDown className="size-3.5" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7 text-red-500 hover:text-red-600"
                  onClick={() => removeStage(index)}
                  title="删除阶段"
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            </div>

            <div className="grid gap-3">
              <div className="grid gap-2">
                <Label>阶段名称</Label>
                <Input
                  value={stage.title}
                  onChange={(e) => patchStage(index, { title: e.target.value })}
                  placeholder="例如：情绪与分离焦虑"
                />
              </div>
              <div className="grid gap-2">
                <Label>
                  引导提示 <span className="text-ink/35">（给 agent 的引导语，可空）</span>
                </Label>
                <Textarea
                  value={stage.guide ?? ""}
                  onChange={(e) => patchStage(index, { guide: e.target.value })}
                  placeholder="例如：先引导学生观察哭闹现象，再推导依恋与情绪机制"
                  className="min-h-[64px]"
                />
              </div>

              <div className="flex items-center gap-2 rounded-lg border border-ink/8 px-3 py-2">
                <FileText className="size-4 text-ink/40" />
                <Label className="flex-1 cursor-pointer text-sm font-normal">
                  该阶段要求产出物（学生须完成才能通过本阶段）
                </Label>
                <Switch
                  checked={!!stage.deliverable}
                  onCheckedChange={(on) => toggleDeliverable(index, on)}
                />
              </div>

              {stage.deliverable && (
                <div className="grid gap-3 rounded-lg border border-ink/8 bg-paper p-3">
                  <div className="grid gap-2">
                    <Label>产出物名称</Label>
                    <Input
                      value={stage.deliverable.title}
                      onChange={(e) =>
                        patchStage(index, {
                          deliverable: {
                            ...stage.deliverable!,
                            title: e.target.value,
                          },
                        })
                      }
                      placeholder="例如：焦虑行为观察记录"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>产出要求</Label>
                    <Textarea
                      value={stage.deliverable.instructions}
                      onChange={(e) =>
                        patchStage(index, {
                          deliverable: {
                            ...stage.deliverable!,
                            instructions: e.target.value,
                          },
                        })
                      }
                      placeholder="例如：请记录并分析 3 个幼儿分离焦虑行为案例"
                      className="min-h-[64px]"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div>
        <Button type="button" variant="outline" size="sm" onClick={addStage}>
          <Plus className="mr-1 size-4" />
          添加阶段
        </Button>
      </div>

      {mainline.stages.length === 0 && (
        <p className="flex items-center gap-1.5 text-xs text-ink/45">
          <Target className="size-3.5" />
          还没有阶段，先添加第一个阶段
        </p>
      )}
    </div>
  );
}
