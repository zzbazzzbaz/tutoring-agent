"use client";

import React, {
  createContext,
  useContext,
  ReactNode,
  useEffect,
} from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { type Message } from "@langchain/langgraph-sdk";
import {
  uiMessageReducer,
  isUIMessage,
  isRemoveUIMessage,
  type UIMessage,
  type RemoveUIMessage,
} from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import { useAuth } from "@/components/auth/AuthProvider";
import { useSessions } from "./SessionProvider";
import { ASSISTANT_ID } from "@/lib/constants";
import { toast } from "sonner";
import { getAgentApiUrl } from "./client";

export type StateType = { messages: Message[]; ui?: UIMessage[] };

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
      context?: Record<string, unknown>;
    };
    CustomEventType: UIMessage | RemoveUIMessage;
  }
>;

type StreamContextType = ReturnType<typeof useTypedStream>;
const StreamContext = createContext<StreamContextType | undefined>(undefined);

async function checkGraphStatus(
  apiUrl: string,
  authToken?: string,
): Promise<boolean> {
  try {
    const headers: HeadersInit = {};
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
    const res = await fetch(`${apiUrl}/info`, { headers });
    return res.ok;
  } catch (e) {
    console.error(e);
    return false;
  }
}

async function sleep(ms = 4000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function StreamProvider({
  children,
  readOnly = false,
}: {
  children: ReactNode;
  readOnly?: boolean;
}) {
  const { token } = useAuth();
  const { refreshSessions } = useSessions();
  const [threadId, setThreadId] = useQueryState("session");
  const agentApiUrl = getAgentApiUrl();

  const streamValue = useTypedStream({
    apiUrl: agentApiUrl,
    assistantId: ASSISTANT_ID,
    defaultHeaders: token
      ? { Authorization: `Bearer ${token}` }
      : {},
    threadId: threadId ?? null,
    fetchStateHistory: true,
    onCustomEvent: (event, options) => {
      if (isUIMessage(event) || isRemoveUIMessage(event)) {
        options.mutate((prev) => {
          const ui = uiMessageReducer(prev.ui ?? [], event);
          return { ...prev, ui };
        });
      }
    },
    onThreadId: (id) => {
      setThreadId(id);
      if (!readOnly) {
        sleep()
          .then(() => refreshSessions())
          .catch(console.error);
      }
    },
  });

  useEffect(() => {
    if (token) {
        checkGraphStatus(agentApiUrl, token).then((ok) => {
        if (!ok) {
          toast.error("无法连接到 Agent 服务器", {
            description: `请确保 Agent Server 运行在 ${agentApiUrl}`,
            duration: 10000,
            richColors: true,
            closeButton: true,
          });
        }
      });
    }
  }, [agentApiUrl, token]);

  return (
    <StreamContext.Provider value={streamValue}>
      {children}
    </StreamContext.Provider>
  );
}

export function useStreamContext(): StreamContextType {
  const context = useContext(StreamContext);
  if (context === undefined) {
    throw new Error(
      "useStreamContext must be used within a StreamProvider",
    );
  }
  return context;
}

export default StreamContext;
