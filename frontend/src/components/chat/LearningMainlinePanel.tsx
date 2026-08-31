"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Check,
  ChevronDown,
  ChevronUp,
  FileText,
  Map,
  Target,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { projectsApi } from "@/lib/api/projects";
import { progressApi } from "@/lib/api/progress";
import { useStreamContext } from "./StreamProvider";
import type {
  Mainline,
  MainlineStage,
  ProjectProgress,
  StageProgress,
} from "@/lib/types";

function StageNode({
  stage,
  progress,
  isLast,
}: {
  stage: MainlineStage;
  progress?: StageProgress;
  isLast: boolean;
}) {
  const status = progress?.status ?? "pending";
  const deliverable = stage.deliverable;
  const showDeliverable = !!deliverable && status !== "pending";
  const deliverableDone = !!progress?.deliverable_done;

  return (
    <div className="relative flex gap-3">
      {/* 节点与连线 */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex size-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
            status === "completed" &&
              "border-emerald-500 bg-emerald-500 text-white",
            status === "in_progress" &&
              "border-brand bg-brand/10 text-brand",
            status === "pending" && "border-ink/15 bg-paper-card text-ink/25",
          )}
        >
          {status === "completed" ? (
            <Check className="size-3.5" strokeWidth={3} />
          ) : (
            <span className="text-[11px] font-semibold">{stage.order}</span>
          )}
        </div>
        {!isLast && (
          <div
            className={cn(
              "w-px flex-1",
              status === "completed" ? "bg-emerald-400" : "bg-ink/10",
            )}
          />
        )}
      </div>

      {/* 阶段内容 */}
      <div className="flex min-w-0 flex-1 flex-col gap-0.5 pb-5">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "text-sm font-medium",
              status === "pending" && "text-ink/40",
            )}
          >
            {stage.title}
          </span>
          {status === "in_progress" && (
            <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand">
              进行中
            </span>
          )}
          {status === "completed" && (
            <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-600">
              已完成
            </span>
          )}
        </div>

        {stage.student_desc && status !== "completed" && (
          <p className="text-xs leading-relaxed text-ink/45">
            {stage.student_desc}
          </p>
        )}

        {showDeliverable && (
          <div className="mt-1 flex items-center gap-1.5">
            <FileText className="size-3.5 shrink-0 text-ink/35" />
            <span className="truncate text-xs text-ink/55">
              {deliverable?.title}
            </span>
            <span
              className={cn(
                "shrink-0 text-[11px]",
                deliverableDone ? "text-emerald-600" : "text-amber-600",
              )}
            >
              {deliverableDone ? "· 已达标" : "· 待完成"}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export function LearningMainlinePanel({
  projectId,
  sessionId,
}: {
  projectId: string;
  sessionId: string;
}) {
  const [mainline, setMainline] = useState<Mainline | null>(null);
  const [fetchedProgress, setFetchedProgress] = useState<ProjectProgress>({});
  const [collapsed, setCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);

  const stream = useStreamContext();
  const liveProgress =
    (stream.values as { progress?: ProjectProgress } | undefined)?.progress ??
    {};

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      projectsApi.get(projectId),
      progressApi.get(sessionId),
    ])
      .then(([proj, prog]) => {
        if (!active) return;
        setMainline(proj.mainline);
        setFetchedProgress(prog.progress ?? {});
      })
      .catch(console.error)
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [projectId, sessionId]);

  const progress = useMemo(
    () => ({ ...fetchedProgress, ...liveProgress }),
    [fetchedProgress, liveProgress],
  );

  if (loading) return null;
  if (!mainline || mainline.stages.length === 0) return null;

  const completed = mainline.stages.filter(
    (s) => progress[s.id]?.status === "completed",
  ).length;
  const percent = Math.round((completed / mainline.stages.length) * 100);

  return (
    <div className="border-ink/10 bg-paper-card overflow-hidden rounded-xl border shadow-sm">
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="hover:bg-paper flex w-full cursor-pointer items-center gap-2 px-4 py-3 text-left transition-colors"
      >
        <Map className="text-brand size-4 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="text-ink text-sm font-semibold">学习主线</div>
          {!collapsed && (
            <div className="mt-1 flex items-center gap-2">
              <div className="bg-ink/8 h-1.5 w-24 overflow-hidden rounded-full">
                <div
                  className="bg-brand h-full rounded-full transition-all"
                  style={{ width: `${percent}%` }}
                />
              </div>
              <span className="text-xs text-ink/45">
                {completed}/{mainline.stages.length} 阶段
              </span>
            </div>
          )}
        </div>
        {collapsed ? (
          <ChevronDown className="size-4 text-ink/40" />
        ) : (
          <ChevronUp className="size-4 text-ink/40" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-ink/8 border-t px-4 py-3">
              {mainline.objective && (
                <div className="mb-3 flex items-start gap-2">
                  <Target className="mt-0.5 size-3.5 shrink-0 text-ink/35" />
                  <p className="text-xs leading-relaxed text-ink/55">
                    {mainline.objective}
                  </p>
                </div>
              )}
              <div className="flex flex-col">
                {mainline.stages.map((stage, idx) => (
                  <StageNode
                    key={stage.id}
                    stage={stage}
                    progress={progress[stage.id]}
                    isLast={idx === mainline.stages.length - 1}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
