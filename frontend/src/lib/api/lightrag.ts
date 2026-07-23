import { api } from "./client";
import type {
  LightRAGDocumentsResponse,
  LightRAGDocumentStatus,
  LightRAGGraphResponse,
  LightRAGPipelineStatus,
} from "@/lib/types";

export const lightragApi = {
  uploadDocument: (formData: FormData) =>
    api.postForm<{ status: string; message: string; track_id: string }>(
      "/lightrag/documents/upload",
      formData,
    ),

  listDocuments: (params: {
    page: number;
    page_size: number;
    status_filter?: LightRAGDocumentStatus;
  }) => api.post<LightRAGDocumentsResponse>("/lightrag/documents/paginated", params),

  statusCounts: () =>
    api.get<{ status_counts: Record<string, number> }>(
      "/lightrag/documents/status_counts",
    ),

  pipelineStatus: () =>
    api.get<LightRAGPipelineStatus>("/lightrag/documents/pipeline_status"),

  trackStatus: (trackId: string) =>
    api.get<unknown>(`/lightrag/documents/track_status/${trackId}`),

  deleteDocument: (docId: string) =>
    api.delete<unknown>("/lightrag/documents/delete_document", {
      doc_ids: [docId],
      delete_file: true,
      delete_llm_cache: false,
    }),

  popularLabels: (limit = 300) =>
    api.get<string[] | { labels: string[] }>(
      `/lightrag/graph/label/popular?limit=${limit}`,
    ),

  searchLabels: (q: string, limit = 50) =>
    api.get<string[] | { labels: string[] }>(
      `/lightrag/graph/label/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),

  graph: (label: string, maxDepth = 3, maxNodes = 1000) =>
    api.get<LightRAGGraphResponse>(
      `/lightrag/graphs?label=${encodeURIComponent(label)}&max_depth=${maxDepth}&max_nodes=${maxNodes}`,
    ),
};
