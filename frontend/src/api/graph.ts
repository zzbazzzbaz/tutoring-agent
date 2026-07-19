import { apiClient } from './client'

export interface GraphNode {
  id: string
  label: string
  type?: string
  degree?: number
  properties?: Record<string, unknown>
  [key: string]: unknown
}

export interface GraphEdge {
  id?: string
  source: string
  target: string
  label?: string
  [key: string]: unknown
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  [key: string]: unknown
}

export const graphApi = {
  listLabels: async (): Promise<string[]> => {
    const res = await apiClient.get<string[]>('/graph/label/list')
    return res.data
  },

  popularLabels: async (limit = 300): Promise<string[]> => {
    const res = await apiClient.get<string[]>('/graph/label/popular', { params: { limit } })
    return res.data
  },

  searchLabels: async (query: string): Promise<string[]> => {
    const res = await apiClient.get<string[]>('/graph/label/search', { params: { query } })
    return res.data
  },

  getGraph: async (params: {
    label: string
    max_depth?: number
    max_nodes?: number
  }): Promise<GraphData> => {
    const res = await apiClient.get<GraphData>('/graphs', {
      params: {
        label: params.label,
        max_depth: params.max_depth ?? 3,
        max_nodes: params.max_nodes ?? 1000,
      },
    })
    return res.data
  },
}
