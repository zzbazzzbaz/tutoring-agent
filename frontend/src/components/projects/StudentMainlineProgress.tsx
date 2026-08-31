"use client";

import { useEffect, useState } from "react";
import { Check, FileText, Map, Target } from "lucide-react";
import { cn } from "@/lib/utils";
import { sessionsApi } from "@/lib/api/sessions";
import { projectsApi } from "@/lib/api/projects";
import { progressApi } from "@/lib/api/progress";
import type {
  Mainline,
  ProjectProgress,
  Session,
} from "@/lib/types";

interface SessionProgressView {
  sessionId: string;
  projectId: string;
  projectName: string;
  lastActiveAt: string;
  mainline: Mainline | null;
  progress: ProjectProgress;
}

function formatTime(date: string | null | undefined): string {
  if (!date) return "";
  try {
    return new Date(date).toLocaleString("zh-CN", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function StudentMainlineProgress({ userId }: { userId: string }) {
  const [views, setViews] = useState<SessionProgressView[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await sessionsApi.listByUser(userId, 1, 100);
        const projectSessions = (result.items ?? []).filter(
          (s: Session) => s.mode === "project" && s.project_id,
        );

        const loaded = await Promise.all(
          projectSessions.map(async (s: Session) => {
            try {
              const [proj, prog] = await Promise.all([
                projectsApi.get(s.project_id!),
                progressApi.get(s.id),
              ]);
              return {
                sessionId: s.id,
                projectId: s.project_id!,
                projectName: proj.name,
                lastActiveAt: s.last_active_at,
                mainline: proj.mainline,
                progress: prog.progress ?? {},
              } satisfies SessionProgressView;
            } catch {
              return null;
            }
          }),
        );
        if (!cancelled)
          setViews(loaded.filter((v): v is SessionProgressView => v !== null));
      } catch (err) {
        console.error("加载会话学习主线失败:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (loading) return null;
  if (views.length === 0) return null;

  return (
    <div className="space-y-4">
      {views.map((view) => {
        const stages = view.mainline?.stages ?? [];
        const completed = stages.filter(
          (s) => view.progress[s.id]?.status === "completed",
        ).length;
        if (stages.length === 0) return null;
        const percent = Math.round((completed / stages.length) * 100);
        return (
          <div key={view.sessionId} className="rounded-lg border bg-card p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Map className="size-4 text-muted-foreground" />
                <h3 className="font-medium">{view.projectName}</h3>
              </div>
              <div className="flex items-center gap-2">
                {view.lastActiveAt && (
                  <span className="text-xs text-muted-foreground">
                    {formatTime(view.lastActiveAt)}
                  </span>
                )}
                <div className="bg-muted h-1.5 w-24 overflow-hidden rounded-full">
                  <div
                    className="h-full rounded-full bg-emerald-500"
                    style={{ width: `${percent}%` }}
                  />
                </div>
                <span className="text-xs text-muted-foreground">
                  {completed}/{stages.length} 阶段
                </span>
              </div>
            </div>

            {view.mainline?.objective && (
              <p className="mb-3 flex items-start gap-1.5 text-xs text-muted-foreground">
                <Target className="mt-0.5 size-3.5 shrink-0" />
                {view.mainline.objective}
              </p>
            )}

            {/* 水平步骤条 */}
            <div className="flex items-start">
              {stages.map((stage, idx) => {
                const sp = view.progress[stage.id];
                const status = sp?.status ?? "pending";
                const isLast = idx === stages.length - 1;
                return (
                  <div
                    key={stage.id}
                    className="flex flex-1 items-start last:flex-none"
                  >
                    <div className="flex flex-col items-center">
                      <div
                        className={cn(
                          "flex size-7 shrink-0 items-center justify-center rounded-full border-2",
                          status === "completed" &&
                            "border-emerald-500 bg-emerald-500 text-white",
                          status === "in_progress" &&
                            "border-blue-500 bg-blue-500/10 text-blue-600",
                          status === "pending" &&
                            "border-muted-foreground/25 bg-background text-muted-foreground/40",
                        )}
                      >
                        {status === "completed" ? (
                          <Check className="size-4" strokeWidth={3} />
                        ) : (
                          <span className="text-xs font-semibold">
                            {stage.order}
                          </span>
                        )}
                      </div>
                      <div className="mt-1.5 flex max-w-[120px] items-center gap-1">
                        <span
                          className={cn(
                            "text-center text-xs leading-tight",
                            status === "pending"
                              ? "text-muted-foreground/50"
                              : "text-foreground",
                          )}
                        >
                          {stage.title}
                        </span>
                      </div>
                      {stage.deliverable && (
                        <span
                          className={cn(
                            "mt-1 flex items-center gap-1 text-[10px]",
                            sp?.deliverable_done
                              ? "text-emerald-600"
                              : "text-amber-600",
                          )}
                        >
                          <FileText className="size-3" />
                          {sp?.deliverable_done ? "已达标" : "待完成"}
                        </span>
                      )}
                    </div>
                    {!isLast && (
                      <div
                        className={cn(
                          "mx-2 mt-3.5 h-0.5 flex-1",
                          status === "completed"
                            ? "bg-emerald-400"
                            : "bg-muted-foreground/20",
                        )}
                      />
                    )}
                  </div>
                );
              })}
            </div>

            {/* 产出物详情 */}
            {stages.some((s) => view.progress[s.id]?.deliverable) && (
              <div className="mt-4 space-y-2 rounded-md border bg-muted/40 p-3">
                {stages.map((stage) => {
                  const sp = view.progress[stage.id];
                  if (!sp?.deliverable) return null;
                  return (
                    <div key={stage.id} className="text-xs">
                      <span className="font-medium">
                        {stage.order}. {stage.title}「
                        {stage.deliverable?.title}」：
                      </span>
                      <span className="text-muted-foreground">
                        {sp.deliverable.slice(0, 120)}
                        {sp.deliverable.length > 120 ? "…" : ""}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
