import axios from 'axios'
import { toast } from 'sonner'
import { useAuthStore } from '@/stores/auth'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 30000,
})

// 请求拦截器：注入 X-User-Id（与后端 get_current_user 一致）
apiClient.interceptors.request.use(config => {
  const username = useAuthStore.getState().username
  if (username) {
    config.headers['X-User-Id'] = username
  }
  return config
})

// 响应拦截器：统一错误 toast
apiClient.interceptors.response.use(
  res => res,
  err => {
    const detail = err.response?.data?.detail?.error
    if (detail) {
      toast.error(`${detail.code}: ${detail.message}`)
    } else if (err.response) {
      toast.error(`HTTP ${err.response.status}: ${err.message}`)
    } else {
      toast.error(err.message || '网络错误')
    }
    return Promise.reject(err)
  },
)

// SSE 流式请求用的 header 注入（fetch 不走 axios 拦截器）
export function getAuthHeaders(): Record<string, string> {
  const username = useAuthStore.getState().username
  return username ? { 'X-User-Id': username } : {}
}
