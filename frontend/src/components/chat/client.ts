import { Client } from "@langchain/langgraph-sdk";
import { AGENT_URL } from "@/lib/constants";

export function createClient(authToken: string | undefined) {
  const defaultHeaders: Record<string, string> = {};
  if (authToken) {
    defaultHeaders["Authorization"] = `Bearer ${authToken}`;
  }

  const apiUrl = AGENT_URL.startsWith("/")
    ? new URL(AGENT_URL, window.location.origin).toString()
    : AGENT_URL;

  return new Client({
    apiUrl,
    ...(Object.keys(defaultHeaders).length ? { defaultHeaders } : {}),
  });
}
