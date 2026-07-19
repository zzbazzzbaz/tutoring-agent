import { create } from 'zustand'
import { documentsApi, type DocumentItem, type PipelineStatus } from '@/api/documents'

interface DocumentsState {
  documents: DocumentItem[]
  total: number
  page: number
  pageSize: number
  pipelineStatus: PipelineStatus | null
  loading: boolean
  pollTimer: ReturnType<typeof setInterval> | null

  fetchPage: (page?: number) => Promise<void>
  startPolling: () => void
  stopPolling: () => void
  uploadFile: (file: File) => Promise<void>
  insertText: (text: string) => Promise<void>
  scan: () => Promise<void>
  deleteDoc: (docId: string) => Promise<void>
}

export const useDocumentsStore = create<DocumentsState>((set, get) => ({
  documents: [],
  total: 0,
  page: 1,
  pageSize: 20,
  pipelineStatus: null,
  loading: false,
  pollTimer: null,

  fetchPage: async page => {
    const p = page ?? get().page
    set({ loading: true })
    try {
      const res = await documentsApi.listPaginated({ page: p, page_size: get().pageSize })
      set({ documents: res.documents || [], total: res.total_count || 0, page: p })
    } finally {
      set({ loading: false })
    }
  },

  startPolling: () => {
    if (get().pollTimer) return
    const tick = async () => {
      try {
        const status = await documentsApi.pipelineStatus()
        set({ pipelineStatus: status })
        if (status.busy) {
          get().fetchPage()
        }
      } catch {
        // 忽略轮询错误
      }
    }
    tick()
    const timer = setInterval(tick, 5000)
    set({ pollTimer: timer })
  },

  stopPolling: () => {
    const timer = get().pollTimer
    if (timer) clearInterval(timer)
    set({ pollTimer: null })
  },

  uploadFile: async file => {
    await documentsApi.uploadFile(file)
    await get().fetchPage()
  },

  insertText: async text => {
    await documentsApi.insertText({ text })
    await get().fetchPage()
  },

  scan: async () => {
    await documentsApi.scan()
    await get().fetchPage()
  },

  deleteDoc: async docId => {
    await documentsApi.deleteDocument(docId)
    await get().fetchPage()
  },
}))
