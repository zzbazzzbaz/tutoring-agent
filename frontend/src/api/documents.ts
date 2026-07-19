import { apiClient } from './client'

export interface DocumentItem {
  id: string
  status: 'pending' | 'processing' | 'processed' | 'failed'
  content_length?: number
  created_at?: string
  updated_at?: string
  file_path?: string
  [key: string]: unknown
}

export interface PipelineStatus {
  busy: boolean
  destructive_busy?: boolean
  scanning?: boolean
  pending_enqueues?: number
}

export interface StatusCounts {
  total?: number
  [status: string]: number | undefined
}

export const documentsApi = {
  uploadFile: async (file: File): Promise<{ task_id?: string; [k: string]: unknown }> => {
    const form = new FormData()
    form.append('file', file)
    const res = await apiClient.post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  insertText: async (body: { text: string; [k: string]: unknown }): Promise<unknown> => {
    const res = await apiClient.post('/documents/text', body)
    return res.data
  },

  scan: async (): Promise<unknown> => {
    const res = await apiClient.post('/documents/scan')
    return res.data
  },

  pipelineStatus: async (): Promise<PipelineStatus> => {
    const res = await apiClient.get<PipelineStatus>('/documents/pipeline_status')
    return res.data
  },

  listPaginated: async (body: {
    page: number
    page_size: number
    [k: string]: unknown
  }): Promise<{ documents: DocumentItem[]; total_count?: number; total_pages?: number }> => {
    const res = await apiClient.post('/documents/paginated', body)
    return res.data
  },

  deleteDocument: async (docId: string): Promise<unknown> => {
    const res = await apiClient.delete('/documents/delete_document', {
      data: { doc_id: docId },
    })
    return res.data
  },
}
