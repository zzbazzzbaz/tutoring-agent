"use client";

import { useState, useEffect } from "react";
import { createClient } from "./client";
import { useAuth } from "@/components/auth/AuthProvider";
import { sessionsApi } from "@/lib/api/sessions";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { MarkdownText } from "@/components/chat/thread/markdown-text";
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
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const session = await sessionsApi.get(sessionId);
        setSessionInfo({
          title: session.title,
          mode: session.mode,
          project_name: session.project_name,
        });

        const client = createClient(token ?? undefined);
        const state = await client.threads.getState(sessionId);
        const values = state.values as Record<string, unknown> | Record<string, unknown>[];
        const msgs = Array.isArray(values) ? values[0]?.messages : values?.messages;
        setMessages((msgs as Message[]) ?? []);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "加载对话失败",
        );
      } finally {
        setLoading(false);
      }
    }
    loadData();
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

  return (
    <div className="flex h-full flex-col">
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
