<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useViewerStore } from '@/stores/viewer'

const route = useRoute()
const viewerStore = useViewerStore()

// Route params
const docId = route.params.docId as string | undefined
const pageNum = route.params.pageNum as string | undefined
</script>

<template>
  <div class="viewer-view">
    <div class="container mx-auto px-4 py-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-6">Document Viewer</h1>
      <p class="text-gray-600">
        View document pages with zoom and pan controls.
        Zoom: {{ viewerStore.zoomPercentage }}%
      </p>
      <p v-if="docId" class="text-gray-500 mt-2">
        Document ID: {{ docId }}{{ pageNum ? `, Page: ${pageNum}` : '' }}
      </p>
      <p v-else class="text-gray-500 mt-2">
        No document selected. Navigate from documents or search results.
      </p>
      <!-- PDF viewer will be implemented in Task 9 -->
    </div>
  </div>
</template>

<style scoped>
.viewer-view {
  min-height: 100vh;
}
</style>
