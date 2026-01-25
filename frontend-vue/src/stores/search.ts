import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SearchResult, RAGResponse, SearchMode } from '@/types'

export const useSearchStore = defineStore('search', () => {
  // Search state
  const query = ref('')
  const results = ref<SearchResult[]>([])
  const mode = ref<SearchMode>('search')
  const loading = ref(false)

  // Response metadata
  const queryType = ref<string>('')
  const totalCount = ref(0)
  const responseTimeMs = ref(0)

  // RAG answer (for AI mode)
  const ragAnswer = ref<RAGResponse | null>(null)

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

  function setQueryType(type: string) {
    queryType.value = type
  }

  function setTotalCount(count: number) {
    totalCount.value = count
  }

  function setResponseTimeMs(ms: number) {
    responseTimeMs.value = ms
  }

  function setRAGAnswer(answer: RAGResponse | null) {
    ragAnswer.value = answer
  }

  function clearResults() {
    results.value = []
    ragAnswer.value = null
    queryType.value = ''
    totalCount.value = 0
    responseTimeMs.value = 0
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
    queryType.value = ''
    totalCount.value = 0
    responseTimeMs.value = 0
  }

  return {
    query,
    results,
    mode,
    loading,
    queryType,
    totalCount,
    responseTimeMs,
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
    setQueryType,
    setTotalCount,
    setResponseTimeMs,
    setRAGAnswer,
    clearResults,
    addToHistory,
    clearHistory,
    reset
  }
})
