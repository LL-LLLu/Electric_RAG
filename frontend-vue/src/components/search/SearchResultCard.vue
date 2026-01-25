<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { DocumentTextIcon, CpuChipIcon, EyeIcon } from '@heroicons/vue/24/outline'
import type { SearchResult } from '@/types'

const props = defineProps<{
  result: SearchResult
}>()

const router = useRouter()

const hasEquipment = computed(() => props.result.equipment !== null)
const hasDocument = computed(() => props.result.document !== null)

const relevancePercentage = computed(() => {
  return Math.round(props.result.relevance_score * 100)
})

const relevanceColor = computed(() => {
  const score = props.result.relevance_score
  if (score >= 0.8) return 'text-green-600 bg-green-100'
  if (score >= 0.6) return 'text-yellow-600 bg-yellow-100'
  return 'text-gray-600 bg-gray-100'
})

function viewPage() {
  if (props.result.document) {
    router.push({
      name: 'viewer',
      params: {
        docId: props.result.document.id,
        pageNum: props.result.page_number
      }
    })
  }
}
</script>

<template>
  <div class="search-result-card bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow">
    <div class="p-4">
      <!-- Header with Equipment Tag and Relevance -->
      <div class="flex items-start justify-between mb-3">
        <div class="flex items-center gap-2 flex-wrap">
          <!-- Equipment Tag -->
          <span
            v-if="hasEquipment"
            class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
          >
            <CpuChipIcon class="h-3 w-3 mr-1" />
            {{ result.equipment!.tag }}
          </span>

          <!-- Equipment Type -->
          <span
            v-if="hasEquipment && result.equipment!.equipment_type"
            class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600"
          >
            {{ result.equipment!.equipment_type }}
          </span>

          <!-- Match Type -->
          <span
            class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700"
          >
            {{ result.match_type }}
          </span>
        </div>

        <!-- Relevance Score -->
        <span
          class="inline-flex items-center px-2 py-1 rounded text-xs font-medium"
          :class="relevanceColor"
        >
          {{ relevancePercentage }}% match
        </span>
      </div>

      <!-- Document Info -->
      <div v-if="hasDocument" class="mb-3">
        <div class="flex items-center text-sm text-gray-700">
          <DocumentTextIcon class="h-4 w-4 mr-2 text-gray-400" />
          <span class="font-medium">{{ result.document!.original_filename || result.document!.filename }}</span>
          <span class="mx-2 text-gray-300">|</span>
          <span class="text-gray-500">Page {{ result.page_number }}</span>
        </div>
      </div>

      <!-- Snippet -->
      <div v-if="result.snippet" class="mb-4">
        <p class="text-sm text-gray-600 line-clamp-3 bg-gray-50 p-3 rounded border-l-2 border-blue-400">
          {{ result.snippet }}
        </p>
      </div>

      <!-- Actions -->
      <div class="flex justify-end">
        <button
          v-if="hasDocument"
          type="button"
          class="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
          @click="viewPage"
        >
          <EyeIcon class="h-4 w-4 mr-1.5" />
          View Page
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
