import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { createSelectors } from '@/lib/utils'

type Theme = 'light' | 'dark' | 'system'
type Language = 'zh' | 'en'

interface SettingsState {
  theme: Theme
  language: Language
  activeTab: string
  setTheme: (theme: Theme) => void
  setLanguage: (language: Language) => void
  setActiveTab: (tab: string) => void
}

const useSettingsStore = create<SettingsState>()(
  persist(
    set => ({
      theme: 'system',
      language: 'zh',
      activeTab: 'chat',
      setTheme: theme => set({ theme }),
      setLanguage: language => set({ language }),
      setActiveTab: activeTab => set({ activeTab }),
    }),
    { name: 'tutoring-settings' },
  ),
)

export const useSettings = createSelectors(useSettingsStore)
export { useSettingsStore }
