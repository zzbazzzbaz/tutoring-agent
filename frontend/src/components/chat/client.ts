import { Client } from "@langchain/langgraph-sdk";
import { AGENT_URL } from "@/lib/constants";

export function getAgentApiUrl() {
  if (!AGENT_URL.startsWith("/") || typeof window === "undefined") {
    return AGENT_URL;
  }

  return new URL(AGENT_URL, window.location.origin).toString();
}

export function createClient(authToken: string | undefined) {
  const defaultHeaders: Record<string, string> = {};
  if (authToken) {
    defaultHeaders["Authorization"] = `Bearer ${authToken}`;
  }

  return new Client({
    apiUrl: getAgentApiUrl(),
    ...(Object.keys(defaultHeaders).length ? { defaultHeaders } : {}),
  });
}
