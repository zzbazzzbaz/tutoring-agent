import { Client } from "@langchain/langgraph-sdk";
import { AGENT_URL } from "@/lib/constants";

export function createClient(authToken: string | undefined) {
  const defaultHeaders: Record<string, string> = {};
  if (authToken) {
    defaultHeaders["Authorization"] = `Bearer ${authToken}`;
  }
  return new Client({
    apiUrl: AGENT_URL,
    ...(Object.keys(defaultHeaders).length ? { defaultHeaders } : {}),
  });
}
