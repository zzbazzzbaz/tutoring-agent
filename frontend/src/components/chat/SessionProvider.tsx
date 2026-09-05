"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import { sessionsApi } from "@/lib/api/sessions";
import { ASSISTANT_ID } from "@/lib/constants";
import type { Session } from "@/lib/types";
import { createClient } from "./client";

interface SessionContextValue {
  sessions: Session[];
  sessionsLoading: boolean;
  refreshSessions: () => Promise<void>;
  createSession: (
    mode: "free" | "project",
    projectId?: string,
  ) => Promise<Session>;
  updateSession: (id: string, title: string | null) => Promise<Session>;
  deleteSession: (id: string) => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | undefined>(
  undefined,
);

export function SessionProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  const refreshSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const data = await sessionsApi.list();
      setSessions(data);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const createSession = useCallback(
    async (mode: "free" | "project", projectId?: string) => {
      const session = await sessionsApi.create({
        mode,
        project_id: projectId,
      });
      try {
        await createClient(token ?? undefined).threads.create({
          threadId: session.id,
          graphId: ASSISTANT_ID,
          ifExists: "do_nothing",
        });
      } catch (err) {
        await sessionsApi.delete(session.id).catch(console.error);
        // 原始错误仅记录到控制台，不向用户暴露
        console.error("Failed to create agent thread:", err);
        throw new Error("创建会话失败，请稍后重试");
      }
      setSessions((prev) => [session, ...prev]);
      return session;
    },
    [token],
  );

  const deleteSession = useCallback(async (id: string) => {
    await sessionsApi.delete(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const updateSession = useCallback(async (id: string, title: string | null) => {
    const session = await sessionsApi.update(id, { title });
    setSessions((prev) => prev.map((s) => (s.id === id ? session : s)));
    return session;
  }, []);

  return (
    <SessionContext.Provider
      value={{
        sessions,
        sessionsLoading,
        refreshSessions,
        createSession,
        updateSession,
        deleteSession,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSessions() {
  const ctx = useContext(SessionContext);
  if (!ctx)
    throw new Error("useSessions must be used within SessionProvider");
  return ctx;
}
