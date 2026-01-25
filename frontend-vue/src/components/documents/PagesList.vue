<script setup lang="ts">
import { useRouter } from 'vue-router'
import { DocumentTextIcon, ChevronRightIcon, CpuChipIcon } from '@heroicons/vue/24/outline'
import type { PageSummary } from '@/types'

const props = defineProps<{
  pages: PageSummary[]
  documentId: number
}>()

const router = useRouter()

function navigateToPage(page: PageSummary) {
  router.push({
    name: 'viewer',
    params: {
      docId: props.documentId,
      pageNum: page.page_number
    }
  })
}
</script>

<template>
  <div class="pages-list">
    <h4 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
      <DocumentTextIcon class="h-4 w-4" />
      Pages ({{ pages.length }})
    </h4>

    <div v-if="pages.length === 0" class="text-sm text-gray-500 italic">
      No pages available.
    </div>

    <div v-else class="space-y-2 max-h-64 overflow-y-auto">
      <button
        v-for="page in pages"
        :key="page.id"
        type="button"
        class="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors group"
        @click="navigateToPage(page)"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="text-sm font-medium text-gray-900">
              Page {{ page.page_number }}
            </span>
            <span
              v-if="page.equipment_count > 0"
              class="inline-flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full"
            >
              <CpuChipIcon class="h-3 w-3" />
              {{ page.equipment_count }} equipment
            </span>
            <span
              v-else
              class="text-xs text-gray-400"
            >
              No equipment
            </span>
          </div>
          <ChevronRightIcon
            class="h-4 w-4 text-gray-400 group-hover:text-gray-600 flex-shrink-0"
          />
        </div>
      </button>
    </div>
  </div>
</template>
