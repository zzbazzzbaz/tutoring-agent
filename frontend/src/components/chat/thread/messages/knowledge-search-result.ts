export type KnowledgeSearchResult = {
  query?: string;
  response?: string;
  chunks?: { content: string; score?: number; file_path?: string }[];
  entities?: {
    entity_name: string;
    entity_type?: string;
    description?: string;
  }[];
  relations?: { src_id: string; tgt_id: string; description?: string }[];
  error?: string;
};

export function parseKnowledgeSearchResult(
  content: unknown,
): KnowledgeSearchResult | null {
  if (typeof content !== "string") return null;
  try {
    const parsed = JSON.parse(content);
    if (!parsed || typeof parsed !== "object") return null;
    return parsed as KnowledgeSearchResult;
  } catch {
    return null;
  }
}
