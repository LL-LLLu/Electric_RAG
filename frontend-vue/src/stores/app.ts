import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export interface AppStats {
  documents: number
  equipment: number
  pages: number
}

export const useAppStore = defineStore('app', () => {
  // Global loading state
  const loading = ref(false)

  // UI state
  const sidebarCollapsed = ref(false)
  const chatExpanded = ref(false)

  // Application statistics
  const stats = reactive<AppStats>({
    documents: 0,
    equipment: 0,
    pages: 0
  })

  // Actions
  function setLoading(value: boolean) {
    loading.value = value
  }

  function updateStats(newStats: Partial<AppStats>) {
    if (newStats.documents !== undefined) stats.documents = newStats.documents
    if (newStats.equipment !== undefined) stats.equipment = newStats.equipment
    if (newStats.pages !== undefined) stats.pages = newStats.pages
  }

  function resetStats() {
    stats.documents = 0
    stats.equipment = 0
    stats.pages = 0
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function toggleChatExpanded() {
    chatExpanded.value = !chatExpanded.value
  }

  function setSidebarCollapsed(value: boolean) {
    sidebarCollapsed.value = value
  }

  function setChatExpanded(value: boolean) {
    chatExpanded.value = value
  }

  return {
    loading,
    stats,
    sidebarCollapsed,
    chatExpanded,
    setLoading,
    updateStats,
    resetStats,
    toggleSidebar,
    toggleChatExpanded,
    setSidebarCollapsed,
    setChatExpanded
  }
})
