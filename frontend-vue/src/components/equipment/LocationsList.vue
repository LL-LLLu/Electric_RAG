<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { DocumentTextIcon, ChevronRightIcon, ChevronDownIcon } from '@heroicons/vue/24/outline'
import type { EquipmentLocation } from '@/types'
import DrawingTypeBadge from '@/components/common/DrawingTypeBadge.vue'

const props = defineProps<{
  locations: EquipmentLocation[]
}>()

const router = useRouter()

// Track which documents are expanded
const expandedDocs = ref<Set<number>>(new Set())

// Group locations by document
interface GroupedDocument {
  document_id: number
  document_filename: string
  document_title: string | null
  pages: Array<{
    page_number: number
    context_text: string | null
    drawing_type?: string | null
  }>
}

const groupedDocuments = computed<GroupedDocument[]>(() => {
  const docMap = new Map<number, GroupedDocument>()

  for (const loc of props.locations) {
    if (!docMap.has(loc.document_id)) {
      docMap.set(loc.document_id, {
        document_id: loc.document_id,
        document_filename: loc.document_filename,
        document_title: loc.document_title,
        pages: []
      })
    }

    const doc = docMap.get(loc.document_id)!
    // Avoid duplicate pages
    if (!doc.pages.some(p => p.page_number === loc.page_number)) {
      doc.pages.push({
        page_number: loc.page_number,
        context_text: loc.context_text,
        drawing_type: (loc as { drawing_type?: string | null }).drawing_type
      })
    }
  }

  // Sort pages within each document
  for (const doc of docMap.values()) {
    doc.pages.sort((a, b) => a.page_number - b.page_number)
  }

  // Return sorted by filename
  return Array.from(docMap.values()).sort((a, b) =>
    a.document_filename.localeCompare(b.document_filename)
  )
})

// Expand first document by default
watch(groupedDocuments, (docs) => {
  const firstDoc = docs[0]
  if (firstDoc && expandedDocs.value.size === 0) {
    expandedDocs.value.add(firstDoc.document_id)
  }
}, { immediate: true })

function toggleDocument(docId: number) {
  if (expandedDocs.value.has(docId)) {
    expandedDocs.value.delete(docId)
  } else {
    expandedDocs.value.add(docId)
  }
}

function navigateToPage(docId: number, pageNum: number) {
  router.push({
    name: 'viewer',
    params: {
      docId: docId,
      pageNum: pageNum
    }
  })
}
</script>

<template>
  <div class="locations-list">
    <h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
      <DocumentTextIcon class="h-4 w-4" />
      Document Locations
      <span class="text-gray-500 dark:text-gray-400 font-normal">
        ({{ groupedDocuments.length }} {{ groupedDocuments.length === 1 ? 'document' : 'documents' }}, {{ locations.length }} {{ locations.length === 1 ? 'page' : 'pages' }})
      </span>
    </h4>

    <div v-if="groupedDocuments.length === 0" class="text-sm text-gray-500 dark:text-gray-400 italic">
      No document locations found.
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="doc in groupedDocuments"
        :key="doc.document_id"
        class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
      >
        <!-- Document Header -->
        <button
          type="button"
          class="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-left"
          @click="toggleDocument(doc.document_id)"
        >
          <div class="flex items-center gap-2 min-w-0 flex-1">
            <component
              :is="expandedDocs.has(doc.document_id) ? ChevronDownIcon : ChevronRightIcon"
              class="h-4 w-4 text-gray-500 dark:text-gray-400 flex-shrink-0"
            />
            <span class="text-sm font-medium text-gray-900 dark:text-white truncate">
              {{ doc.document_title || doc.document_filename }}
            </span>
            <span class="text-xs text-gray-500 dark:text-gray-400 bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded flex-shrink-0">
              {{ doc.pages.length }} {{ doc.pages.length === 1 ? 'page' : 'pages' }}
            </span>
          </div>
        </button>

        <!-- Pages List (Expandable) -->
        <div
          v-if="expandedDocs.has(doc.document_id)"
          class="border-t border-gray-200 dark:border-gray-700"
        >
          <button
            v-for="page in doc.pages"
            :key="page.page_number"
            type="button"
            class="w-full flex items-center justify-between p-3 pl-9 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors text-left border-b border-gray-100 dark:border-gray-700 last:border-b-0"
            @click="navigateToPage(doc.document_id, page.page_number)"
          >
            <div class="flex items-center gap-2 min-w-0 flex-1">
              <span class="text-sm text-gray-700 dark:text-gray-300">
                Page {{ page.page_number }}
              </span>
              <DrawingTypeBadge v-if="page.drawing_type" :type="page.drawing_type" size="sm" />
            </div>
            <ChevronRightIcon class="h-4 w-4 text-gray-400 flex-shrink-0" />
          </button>
        </div>
      </div>
    </div>

    <!-- Also appears in indicator for multiple documents -->
    <div
      v-if="groupedDocuments.length > 1"
      class="mt-3 text-xs text-gray-500 dark:text-gray-400 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-2"
    >
      This equipment appears in <strong>{{ groupedDocuments.length }} different documents</strong>
    </div>
  </div>
</template>
