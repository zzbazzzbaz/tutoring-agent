import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { createSelectors } from '@/lib/utils'

interface User {
  id: string
  username: string
  role: 'student' | 'teacher'
  name: string
}

interface AuthState {
  token: string | null
  user: User | null
  login: (token: string, user: User) => void
  logout: () => void
}

const useAuthStore = create<AuthState>()(
  persist(
    set => ({
      token: null,
      user: null,
      login: (token, user) => set({ token, user }),
      logout: () => set({ token: null, user: null }),
    }),
    { name: 'tutoring-auth' },
  ),
)

export const useAuth = createSelectors(useAuthStore)
export { useAuthStore }
