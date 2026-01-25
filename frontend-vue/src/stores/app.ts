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

  return {
    loading,
    stats,
    setLoading,
    updateStats,
    resetStats
  }
})
