<script setup lang="ts">
import { useDocumentsStore } from '@/stores/documents'

const documentsStore = useDocumentsStore()
</script>

<template>
  <div class="documents-view">
    <div class="container mx-auto px-4 py-8">
      <h1 class="text-3xl font-bold text-gray-900 mb-6">Documents</h1>
      <p class="text-gray-600">
        Manage uploaded documents. {{ documentsStore.totalCount }} documents.
      </p>
      <!-- Documents list will be implemented in Task 8 -->
    </div>
  </div>
</template>

<style scoped>
.documents-view {
  min-height: 100vh;
}
</style>
