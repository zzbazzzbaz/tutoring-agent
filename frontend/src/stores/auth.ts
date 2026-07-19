import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Role = 'student' | 'teacher'

interface AuthState {
  isAuthenticated: boolean
  username: string | null
  role: Role | null
  mockToken: string | null

  login: (username: string, role: Role) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    set => ({
      isAuthenticated: false,
      username: null,
      role: null,
      mockToken: null,

      login: (username, role) =>
        set({
          isAuthenticated: true,
          username,
          role,
          mockToken: `mock-${username}`,
        }),
      logout: () =>
        set({
          isAuthenticated: false,
          username: null,
          role: null,
          mockToken: null,
        }),
    }),
    { name: 'tutoring-auth' },
  ),
)
