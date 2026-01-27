import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { SearchResult, RAGResponse, SearchMode } from '@/types'

const SEARCH_HISTORY_KEY = 'electric-rag-search-history'
const MAX_HISTORY_ITEMS = 20

// Load search history from localStorage
function loadSearchHistory(): string[] {
  try {
    const stored = localStorage.getItem(SEARCH_HISTORY_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      if (Array.isArray(parsed)) {
        return parsed.slice(0, MAX_HISTORY_ITEMS)
      }
    }
  } catch (e) {
    console.warn('Failed to load search history from localStorage:', e)
  }
  return []
}

// Save search history to localStorage
function saveSearchHistory(queries: string[]) {
  try {
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(queries.slice(0, MAX_HISTORY_ITEMS)))
  } catch (e) {
    console.warn('Failed to save search history to localStorage:', e)
  }
}

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

  // Search history - load from localStorage on init
  const recentQueries = ref<string[]>(loadSearchHistory())

  // Persist search history to localStorage whenever it changes
  watch(recentQueries, (newQueries) => {
    saveSearchHistory(newQueries)
  }, { deep: true })

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
    // Keep only last MAX_HISTORY_ITEMS
    if (recentQueries.value.length > MAX_HISTORY_ITEMS) {
      recentQueries.value.pop()
    }
  }

  function removeFromHistory(q: string) {
    const index = recentQueries.value.indexOf(q)
    if (index !== -1) {
      recentQueries.value.splice(index, 1)
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
    removeFromHistory,
    clearHistory,
    reset
  }
})
