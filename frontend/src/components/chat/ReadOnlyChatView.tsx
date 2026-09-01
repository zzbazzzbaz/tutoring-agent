"use client";

import { useState, useEffect } from "react";
import { createClient } from "./client";
import { useAuth } from "@/components/auth/AuthProvider";
import { sessionsApi } from "@/lib/api/sessions";
import { progressApi } from "@/lib/api/progress";
import { projectsApi } from "@/lib/api/projects";
import { Button } from "@/components/ui/button";
import { ArrowLeft, FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import { MarkdownText } from "@/components/chat/thread/markdown-text";
import { DeliverableCard } from "@/components/projects/DeliverableCard";
import type { Mainline, ProjectProgress } from "@/lib/types";
import type { Message } from "@langchain/langgraph-sdk";

export function ReadOnlyChatView({
  sessionId,
  backHref,
}: {
  sessionId: string;
  backHref: string;
}) {
  const router = useRouter();
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [sessionInfo, setSessionInfo] = useState<{
    title: string | null;
    mode: string;
    project_name: string | null;
    project_id: string | null;
  } | null>(null);
  const [deliverables, setDeliverables] = useState<{
    mainline: Mainline | null;
    progress: ProjectProgress;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadData() {
      try {
        setError(null);
        setLoading(true);
        const session = await sessionsApi.get(sessionId);
        if (cancelled) return;
        setSessionInfo({
          title: session.title,
          mode: session.mode,
          project_name: session.project_name,
          project_id: session.project_id,
        });

        if (session.mode === "project" && session.project_id) {
          try {
            const [proj, prog] = await Promise.all([
              projectsApi.get(session.project_id),
              progressApi.get(sessionId),
            ]);
            if (!cancelled)
              setDeliverables({
                mainline: proj.mainline,
                progress: prog.progress ?? {},
              });
          } catch {
            if (!cancelled) setDeliverables(null);
          }
        }

        const client = createClient(token ?? undefined);
        const state = await client.threads.getState(sessionId);
        if (cancelled) return;
        const values = state.values as Record<string, unknown> | Record<string, unknown>[];
        const msgs = Array.isArray(values) ? values[0]?.messages : values?.messages;
        setMessages((msgs as Message[]) ?? []);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "加载对话失败",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadData();
    return () => {
      cancelled = true;
    };
  }, [sessionId, token]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">加载对话中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <p className="text-destructive">{error}</p>
          <Button
            variant="outline"
            onClick={() => router.push(backHref)}
            className="mt-4"
          >
            返回
          </Button>
        </div>
      </div>
    );
  }

  const title =
    sessionInfo?.title ||
    (sessionInfo?.mode === "free"
      ? "自由学习"
      : sessionInfo?.project_name || "项目模式");

  const deliverableStages =
    deliverables?.mainline?.stages.filter((s) => s.deliverable) ?? [];
  const showPanel = deliverableStages.length > 0;
  const submittedCount = deliverableStages.filter(
    (s) => deliverables?.progress[s.id]?.deliverable,
  ).length;

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex h-full min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-3 border-b px-4 py-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(backHref)}
          >
            <ArrowLeft className="mr-2 size-4" />
            返回
          </Button>
          <span className="text-sm font-medium">查看对话: {title}</span>
          <span className="text-xs text-muted-foreground">(只读)</span>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <div className="mx-auto max-w-3xl space-y-4">
            {messages && messages.length > 0 ? (
              messages.map((msg, idx) => {
                const type = msg.type;
                if (type === "human") {
                  return (
                    <div
                      key={idx}
                      className="flex justify-end"
                    >
                      <div className="max-w-[80%] rounded-lg bg-primary px-4 py-2 text-primary-foreground">
                        {getContentString(msg.content)}
                      </div>
                    </div>
                  );
                }
                if (type === "ai") {
                  const contentStr = getContentString(msg.content);
                  if (!contentStr) return null;
                  return (
                    <div
                      key={idx}
                      className="flex justify-start"
                    >
                      <div className="max-w-[80%] rounded-lg bg-muted px-4 py-2">
                        <MarkdownText>{contentStr}</MarkdownText>
                      </div>
                    </div>
                  );
                }
                return null;
              })
            ) : (
              <p className="text-center text-muted-foreground">
                暂无对话消息
              </p>
            )}
          </div>
        </div>
      </div>

      {showPanel && (
        <div className="border-ink/10 bg-paper-card/60 flex h-full w-80 shrink-0 flex-col border-l backdrop-blur-sm">
          <div className="border-ink/10 flex items-center gap-2 border-b px-4 py-3">
            <FileText className="text-brand size-4 shrink-0" />
            <span className="text-ink text-sm font-semibold">产出物</span>
            <span className="text-xs text-ink/45">
              已提交 {submittedCount}/{deliverableStages.length}
            </span>
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            {deliverableStages.map((stage) => {
              const sp = deliverables!.progress[stage.id];
              if (!sp?.deliverable) {
                return (
                  <div
                    key={stage.id}
                    className="flex items-center gap-2 rounded-lg border border-dashed border-ink/10 px-3 py-2 text-xs text-ink/40"
                  >
                    <FileText className="size-3.5 shrink-0" />
                    <span>
                      {stage.order}. {stage.title}「{stage.deliverable!.title}」
                      未提交
                    </span>
                  </div>
                );
              }
              return (
                <DeliverableCard
                  key={stage.id}
                  stageTitle={`${stage.order}. ${stage.title}`}
                  deliverableTitle={stage.deliverable!.title}
                  content={sp.deliverable}
                  done={!!sp.deliverable_done}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function getContentString(
  content: Message["content"],
): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((block) => {
        if (typeof block === "string") return block;
        if (block && typeof block === "object" && "text" in block) {
          return (block as { text: string }).text;
        }
        return "";
      })
      .join("");
  }
  return "";
}
