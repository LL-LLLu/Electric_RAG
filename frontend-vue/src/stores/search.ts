import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface SearchResult {
  id: string
  document_id: string
  document_name: string
  page_number: number
  content: string
  score: number
  equipment_tags?: string[]
}

export interface RAGAnswer {
  answer: string
  sources: SearchResult[]
}

export type SearchMode = 'search' | 'ai'

export const useSearchStore = defineStore('search', () => {
  // Search state
  const query = ref('')
  const results = ref<SearchResult[]>([])
  const mode = ref<SearchMode>('search')
  const loading = ref(false)

  // RAG answer (for AI mode)
  const ragAnswer = ref<RAGAnswer | null>(null)

  // Search history
  const recentQueries = ref<string[]>([])

  // Computed
  const hasResults = computed(() => results.value.length > 0)
  const hasQuery = computed(() => query.value.trim().length > 0)
  const isAIMode = computed(() => mode.value === 'ai')
  const resultCount = computed(() => results.value.length)

  // Actions
  function setQuery(q: string) {
    query.value = q
  }

  function setResults(res: SearchResult[]) {
    results.value = res
  }

  function setMode(m: SearchMode) {
    mode.value = m
  }

  function toggleMode() {
    mode.value = mode.value === 'search' ? 'ai' : 'search'
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function setRAGAnswer(answer: RAGAnswer | null) {
    ragAnswer.value = answer
  }

  function clearResults() {
    results.value = []
    ragAnswer.value = null
  }

  function addToHistory(q: string) {
    // Remove if already exists
    const index = recentQueries.value.indexOf(q)
    if (index !== -1) {
      recentQueries.value.splice(index, 1)
    }
    // Add to front
    recentQueries.value.unshift(q)
    // Keep only last 10
    if (recentQueries.value.length > 10) {
      recentQueries.value.pop()
    }
  }

  function clearHistory() {
    recentQueries.value = []
  }

  function reset() {
    query.value = ''
    results.value = []
    ragAnswer.value = null
    loading.value = false
  }

  return {
    query,
    results,
    mode,
    loading,
    ragAnswer,
    recentQueries,
    hasResults,
    hasQuery,
    isAIMode,
    resultCount,
    setQuery,
    setResults,
    setMode,
    toggleMode,
    setLoading,
    setRAGAnswer,
    clearResults,
    addToHistory,
    clearHistory,
    reset
  }
})
