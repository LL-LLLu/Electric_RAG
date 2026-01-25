<script setup lang="ts">
import { ref, computed } from 'vue'
import { useSearchStore } from '@/stores/search'
import * as searchApi from '@/api/search'
import SearchBox from '@/components/search/SearchBox.vue'
import SearchResults from '@/components/search/SearchResults.vue'
import ExampleQueries from '@/components/search/ExampleQueries.vue'
import ErrorAlert from '@/components/common/ErrorAlert.vue'
import type { SearchMode } from '@/types'

const searchStore = useSearchStore()

// Local state
const error = ref<string | null>(null)
const hasSearched = ref(false)

// Computed
const query = computed({
  get: () => searchStore.query,
  set: (value: string) => searchStore.setQuery(value)
})

const mode = computed({
  get: () => searchStore.mode,
  set: (value: SearchMode) => searchStore.setMode(value)
})

const showExamples = computed(() => {
  return !hasSearched.value && !searchStore.loading && !searchStore.hasResults && !searchStore.ragAnswer
})

const showNoResults = computed(() => {
  return hasSearched.value && !searchStore.loading && !searchStore.hasResults && !searchStore.ragAnswer
})

const aiAnswer = computed(() => {
  return searchStore.ragAnswer?.answer || null
})

// Methods
async function handleSearch() {
  if (!query.value.trim()) return

  error.value = null
  searchStore.setLoading(true)
  searchStore.clearResults()

  try {
    if (mode.value === 'ai') {
      // AI mode - use ask endpoint
      const response = await searchApi.ask(query.value, 10, true)
      searchStore.setResults(response.sources)
      searchStore.setRAGAnswer(response)
      searchStore.setQueryType(response.query_type)
    } else {
      // Search mode - use search endpoint
      const response = await searchApi.search(query.value, 10)
      searchStore.setResults(response.results)
      searchStore.setRAGAnswer(null)
      searchStore.setQueryType(response.query_type)
      searchStore.setTotalCount(response.total_count)
      searchStore.setResponseTimeMs(response.response_time_ms)
    }

    // Add to search history
    searchStore.addToHistory(query.value)
    hasSearched.value = true
  } catch (err: any) {
    hasSearched.value = true
    console.error('Search error:', err)
    error.value = err.response?.data?.detail || err.message || 'Search failed. Please try again.'
  } finally {
    searchStore.setLoading(false)
  }
}

function handleExampleSelect(exampleQuery: string) {
  query.value = exampleQuery
  handleSearch()
}

function dismissError() {
  error.value = null
}
</script>

<template>
  <div class="search-view">
    <div class="container mx-auto px-4 py-8 max-w-4xl">
      <!-- Header -->
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">Search Documents</h1>
        <p class="text-gray-600">
          Search across all documents and equipment or ask questions using AI.
        </p>
      </div>

      <!-- Search Box -->
      <div class="mb-6">
        <SearchBox
          v-model="query"
          :mode="mode"
          @update:mode="mode = $event"
          @submit="handleSearch"
        />
      </div>

      <!-- Example Queries -->
      <div v-if="showExamples" class="mb-8">
        <ExampleQueries @select="handleExampleSelect" />
      </div>

      <!-- Error Alert -->
      <div v-if="error" class="mb-6">
        <ErrorAlert
          :message="error"
          :dismissable="true"
          @dismiss="dismissError"
        />
      </div>

      <!-- Search Metadata -->
      <div
        v-if="!searchStore.loading && searchStore.hasResults && mode === 'search'"
        class="mb-4 text-sm text-gray-500"
      >
        Found {{ searchStore.totalCount }} results in {{ searchStore.responseTimeMs }}ms
      </div>

      <!-- Search Results -->
      <SearchResults
        :results="searchStore.results"
        :loading="searchStore.loading"
        :answer="aiAnswer"
        :show-empty-state="showNoResults"
      />
    </div>
  </div>
</template>

<style scoped>
.search-view {
  min-height: 100vh;
  background-color: #f9fafb;
}
</style>
