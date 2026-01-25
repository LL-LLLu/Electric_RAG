<script setup lang="ts">
import { useDocumentsStore } from '@/stores/documents'

const documentsStore = useDocumentsStore()
</script>

<template>
  <div class="upload-view">
    <div class="container mx-auto px-4 py-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-6">Upload Documents</h1>
      <p class="text-gray-600">
        Upload PDF documents for processing and equipment extraction.
      </p>
      <p v-if="documentsStore.activeUploads.length > 0" class="text-blue-600 mt-2">
        {{ documentsStore.activeUploads.length }} upload(s) in progress
      </p>
      <!-- Upload interface will be implemented in Task 6 -->
    </div>
  </div>
</template>

<style scoped>
.upload-view {
  min-height: 100vh;
}
</style>
