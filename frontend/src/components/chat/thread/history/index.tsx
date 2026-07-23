"use client";

import { Button } from "@/components/ui/button";
import { useSessions } from "@/components/chat/SessionProvider";
import { useEffect } from "react";
import { useQueryState, parseAsBoolean } from "nuqs";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { PanelRightOpen, PanelRightClose, Plus } from "lucide-react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { cn } from "@/lib/utils";
import type { Session } from "@/lib/types";
import { motion } from "framer-motion";

function SessionList({
  sessions,
  onSessionClick,
  onNewSession,
}: {
  sessions: Session[];
  onSessionClick?: (sessionId: string) => void;
  onNewSession?: () => void;
}) {
  const [sessionId, setSessionId] = useQueryState("session");

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex items-center justify-between border-b p-2">
        <span className="text-sm font-semibold">会话列表</span>
        <Button size="sm" variant="outline" onClick={onNewSession}>
          <Plus className="size-4" />
          新建
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-1">
        {sessions.length === 0 ? (
          <p className="p-3 text-sm text-muted-foreground">暂无会话</p>
        ) : (
          sessions.map((s) => {
            const title =
              s.title ||
              (s.mode === "free"
                ? "自由学习"
                : s.project_name || "项目模式");
            const active = sessionId === s.id;
            return (
              <Button
                key={s.id}
                variant="ghost"
                className={cn(
                  "w-full justify-start text-left font-normal",
                  active && "bg-primary/10 text-primary",
                )}
                onClick={(e) => {
                  e.preventDefault();
                  onSessionClick?.(s.id);
                  if (s.id === sessionId) return;
                  setSessionId(s.id);
                }}
              >
                <div className="flex w-full flex-col">
                  <span className="truncate">{title}</span>
                  <span className="text-xs text-muted-foreground">
                    {s.mode === "project" ? `📁 ${s.project_name}` : "💬 自由学习"}
                  </span>
                </div>
              </Button>
            );
          })
        )}
      </div>
    </div>
  );
}

function SessionListLoading() {
  return (
    <div className="flex h-full w-full flex-col gap-2 overflow-y-auto p-2">
      {Array.from({ length: 10 }).map((_, i) => (
        <Skeleton key={`skeleton-${i}`} className="h-12 w-full" />
      ))}
    </div>
  );
}

export default function ThreadHistory({
  onNewSession,
}: {
  onNewSession?: () => void;
}) {
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );

  const { sessions, sessionsLoading, refreshSessions } = useSessions();

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  return (
    <>
      <div className="shadow-inner-right hidden h-screen w-[260px] shrink-0 flex-col border-r lg:flex">
        {sessionsLoading ? (
          <SessionListLoading />
        ) : (
          <SessionList
            sessions={sessions}
            onNewSession={onNewSession}
          />
        )}
      </div>
      <div className="lg:hidden">
        <Sheet
          open={!!chatHistoryOpen && !isLargeScreen}
          onOpenChange={(open) => {
            if (isLargeScreen) return;
            setChatHistoryOpen(open);
          }}
        >
          <SheetContent side="left" className="flex w-[260px] lg:hidden">
            <SheetHeader>
              <SheetTitle>会话列表</SheetTitle>
            </SheetHeader>
            <SessionList
              sessions={sessions}
              onNewSession={onNewSession}
            />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
