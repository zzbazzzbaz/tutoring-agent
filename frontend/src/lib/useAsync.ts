import { useEffect, useState, useCallback } from 'react'

interface UseAsyncResult<T> {
  data: T | null
  error: Error | null
  loading: boolean
  refetch: () => void
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): UseAsyncResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)
  const [nonce, setNonce] = useState(0)

  const refetch = useCallback(() => setNonce(n => n + 1), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fn()
      .then(d => { if (!cancelled) { setData(d); setError(null) } })
      .catch(e => { if (!cancelled) setError(e) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { data, error, loading, refetch }
}
