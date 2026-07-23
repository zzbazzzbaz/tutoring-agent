import { lightragApi } from "@/lib/api/lightrag";

export type QueryMode = "local" | "global" | "hybrid" | "naive" | "mix" | "bypass";

export interface Message {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface QueryRequest {
  query: string;
  mode?: QueryMode;
  response_type?: string;
  top_k?: number;
  chunk_top_k?: number;
  max_entity_tokens?: number;
  max_relation_tokens?: number;
  max_total_tokens?: number;
  max_token_for_text_unit?: number;
  max_token_for_global_context?: number;
  max_token_for_local_context?: number;
  only_need_context?: boolean;
  only_need_prompt?: boolean;
  enable_rerank?: boolean;
  history_turns?: number;
  hl_keywords?: string[];
  ll_keywords?: string[];
  user_prompt?: string;
  conversation_history?: Message[];
  stream?: boolean;
}

export interface LightragStatus {
  status: string;
  message?: string;
  core_version?: string;
  api_version?: string;
  pipeline_busy?: boolean;
  pipeline_active?: boolean;
  configuration?: { max_graph_nodes?: string | number };
  webui_title?: string | null;
  webui_description?: string | null;
}

export interface LightragNodeType {
  id: string;
  labels: string[];
  properties: Record<string, unknown>;
}

export interface LightragEdgeType {
  id: string;
  source: string;
  target: string;
  type?: string;
  properties: Record<string, unknown>;
}

export interface LightragGraphType {
  nodes: LightragNodeType[];
  edges: LightragEdgeType[];
  is_truncated?: boolean;
}

interface EntityOperationSummary {
  operation_status?: string;
  final_entity?: string;
  merged?: boolean;
  merge_error?: string;
  merge_status?: string;
}

interface EntityUpdateResponse {
  status: string;
  message: string;
  operation_summary?: EntityOperationSummary | null;
}

function normalizeLabels(value: string[] | { labels?: string[] }) {
  return Array.isArray(value) ? value : value.labels ?? [];
}

export async function queryGraphs(label: string, maxDepth: number, maxNodes: number) {
  return lightragApi.graph(label, maxDepth, maxNodes) as Promise<LightragGraphType>;
}

export async function getPopularLabels(limit = 300) {
  return normalizeLabels(await lightragApi.popularLabels(limit));
}

export async function searchLabels(query: string, limit = 50) {
  return normalizeLabels(await lightragApi.searchLabels(query, limit));
}

export async function checkHealth(): Promise<LightragStatus> {
  const pipeline = await lightragApi.pipelineStatus();
  return {
    status: "healthy",
    pipeline_busy: pipeline.busy,
    pipeline_active: pipeline.busy,
  };
}

export async function updateEntity(
  _entityName?: string,
  _updatedData?: Record<string, unknown>,
  _allowRename?: boolean,
  _allowMerge?: boolean,
): Promise<EntityUpdateResponse> {
  return {
    status: "unsupported",
    message: "当前页面不支持编辑实体",
    operation_summary: null,
  };
}

export async function updateRelation(
  _sourceEntity?: string,
  _targetEntity?: string,
  _updatedData?: Record<string, unknown>,
) {
  return { status: "unsupported", message: "当前页面不支持编辑关系" };
}

export async function checkEntityNameExists(_entityName?: string) {
  return false;
}
