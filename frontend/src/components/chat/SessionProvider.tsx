"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { sessionsApi } from "@/lib/api/sessions";
import type { Session } from "@/lib/types";

interface SessionContextValue {
  sessions: Session[];
  sessionsLoading: boolean;
  refreshSessions: () => Promise<void>;
  createSession: (
    mode: "free" | "project",
    projectId?: string,
  ) => Promise<Session>;
  deleteSession: (id: string) => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | undefined>(
  undefined,
);

export function SessionProvider({ children }: { children: ReactNode }) {
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
      setSessions((prev) => [session, ...prev]);
      return session;
    },
    [],
  );

  const deleteSession = useCallback(async (id: string) => {
    await sessionsApi.delete(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  return (
    <SessionContext.Provider
      value={{
        sessions,
        sessionsLoading,
        refreshSessions,
        createSession,
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
