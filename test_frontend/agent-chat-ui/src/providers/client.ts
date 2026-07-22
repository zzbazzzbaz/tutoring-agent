import { Client } from "@langchain/langgraph-sdk";

export function createClient(
  apiUrl: string,
  apiKey: string | undefined,
  authScheme: string | undefined,
  authToken: string | undefined,
) {
  const defaultHeaders = {
    ...(authScheme ? { "X-Auth-Scheme": authScheme } : {}),
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  };
  return new Client({
    apiKey,
    apiUrl,
    ...(Object.keys(defaultHeaders).length ? { defaultHeaders } : {}),
  });
}
