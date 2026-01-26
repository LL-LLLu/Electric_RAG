import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark' | 'system'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<ThemeMode>('system')

  const effectiveTheme = computed(() => {
    if (theme.value === 'system') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }
    return theme.value
  })

  const isDark = computed(() => effectiveTheme.value === 'dark')

  function init() {
    // Load saved theme from localStorage
    const saved = localStorage.getItem('theme') as ThemeMode | null
    if (saved && ['light', 'dark', 'system'].includes(saved)) {
      theme.value = saved
    }
    updateDocument()

    // Listen for system preference changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (theme.value === 'system') {
        updateDocument()
      }
    })
  }

  function setTheme(newTheme: ThemeMode) {
    theme.value = newTheme
    localStorage.setItem('theme', newTheme)
    updateDocument()
  }

  function updateDocument() {
    const effective = theme.value === 'system'
      ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme.value

    if (effective === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  return {
    theme,
    effectiveTheme,
    isDark,
    init,
    setTheme,
  }
})
