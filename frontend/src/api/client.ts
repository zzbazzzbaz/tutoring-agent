import axios from 'axios'
import { toast } from 'sonner'
import { useAuthStore } from '@/stores/auth'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 30000,
})

apiClient.interceptors.request.use(config => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.hash = '#/login'
    }
    const detail = err.response?.data?.detail?.error
    if (detail) {
      toast.error(detail.message)
    } else if (err.response) {
      toast.error(`HTTP ${err.response.status}`)
    } else {
      toast.error(err.message || '网络错误')
    }
    return Promise.reject(err)
  },
)

export function getAuthToken(): string | null {
  return useAuthStore.getState().token
}
