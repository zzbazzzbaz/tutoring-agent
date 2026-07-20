import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { useSettingsStore } from '@/stores/settings'
import zh from './locales/zh.json'
import en from './locales/en.json'

const getStoredLanguage = () => {
  try {
    const settingsString = localStorage.getItem('tutoring-settings')
    if (settingsString) {
      const settings = JSON.parse(settingsString)
      return settings.state?.language || 'zh'
    }
  } catch {
    // ignore
  }
  return 'zh'
}

i18n.use(initReactI18next).init({
  resources: {
    zh: { translation: zh },
    en: { translation: en },
  },
  lng: getStoredLanguage(),
  fallbackLng: 'zh',
  interpolation: { escapeValue: false },
})

useSettingsStore.subscribe(state => {
  if (i18n.language !== state.language) {
    i18n.changeLanguage(state.language)
  }
})

export default i18n
