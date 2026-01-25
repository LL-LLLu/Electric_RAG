<script setup lang="ts">
import { computed } from 'vue'
import { SparklesIcon, DocumentTextIcon, InboxIcon } from '@heroicons/vue/24/outline'
import SearchResultCard from './SearchResultCard.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import type { SearchResult } from '@/types'

const props = defineProps<{
  results: SearchResult[]
  loading: boolean
  answer?: string | null
  showEmptyState?: boolean
}>()

const hasResults = computed(() => props.results.length > 0)
const hasAnswer = computed(() => !!props.answer)
const showEmpty = computed(() => props.showEmptyState && !props.loading && !hasResults.value && !hasAnswer.value)
</script>

<template>
  <div class="search-results">
    <!-- Loading State -->
    <div v-if="loading" class="flex flex-col items-center justify-center py-16">
      <LoadingSpinner size="large" text="Searching documents..." />
    </div>

    <!-- Results Content -->
    <div v-else-if="hasResults || hasAnswer">
      <!-- AI Answer Section -->
      <div v-if="hasAnswer" class="mb-6">
        <div class="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-6">
          <div class="flex items-start gap-3">
            <div class="flex-shrink-0">
              <div class="p-2 bg-purple-100 rounded-full">
                <SparklesIcon class="h-6 w-6 text-purple-600" />
              </div>
            </div>
            <div class="flex-1">
              <h3 class="text-lg font-semibold text-gray-900 mb-2">AI Answer</h3>
              <div class="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">{{ answer }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Source Results Section -->
      <div v-if="hasResults">
        <div class="flex items-center gap-2 mb-4">
          <DocumentTextIcon class="h-5 w-5 text-gray-400" />
          <h3 class="text-lg font-semibold text-gray-900">
            {{ hasAnswer ? 'Sources' : 'Search Results' }}
          </h3>
          <span class="text-sm text-gray-500">({{ results.length }} results)</span>
        </div>

        <div class="space-y-4">
          <SearchResultCard
            v-for="(result, index) in results"
            :key="index"
            :result="result"
          />
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="showEmpty" class="text-center py-16">
      <InboxIcon class="mx-auto h-12 w-12 text-gray-400" />
      <h3 class="mt-4 text-lg font-medium text-gray-900">No results found</h3>
      <p class="mt-2 text-sm text-gray-500">
        Try adjusting your search query or use different keywords.
      </p>
    </div>
  </div>
</template>

<style scoped>
.search-results {
  width: 100%;
}

.prose {
  line-height: 1.7;
}
</style>
