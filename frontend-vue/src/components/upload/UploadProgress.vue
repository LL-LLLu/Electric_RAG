<script setup lang="ts">
import { computed } from 'vue'
import type { UploadProgress } from '@/types'
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  CloudArrowUpIcon
} from '@heroicons/vue/24/solid'

const props = defineProps<{
  uploads: Map<string, UploadProgress>
}>()

const uploadList = computed(() => {
  return Array.from(props.uploads.values())
})

function getStatusColor(status: UploadProgress['status']) {
  switch (status) {
    case 'uploading':
      return 'bg-blue-500'
    case 'processing':
      return 'bg-yellow-500'
    case 'completed':
      return 'bg-green-500'
    case 'error':
      return 'bg-red-500'
    default:
      return 'bg-gray-400'
  }
}

function getStatusText(status: UploadProgress['status']) {
  switch (status) {
    case 'pending':
      return 'Pending'
    case 'uploading':
      return 'Uploading'
    case 'processing':
      return 'Processing'
    case 'completed':
      return 'Complete'
    case 'error':
      return 'Error'
    default:
      return status
  }
}

function getStatusTextColor(status: UploadProgress['status']) {
  switch (status) {
    case 'uploading':
      return 'text-blue-600'
    case 'processing':
      return 'text-yellow-600'
    case 'completed':
      return 'text-green-600'
    case 'error':
      return 'text-red-600'
    default:
      return 'text-gray-500'
  }
}
</script>

<template>
  <div v-if="uploadList.length > 0" class="upload-progress space-y-3">
    <h3 class="text-sm font-medium text-gray-700 mb-2">Upload Progress</h3>

    <div
      v-for="upload in uploadList"
      :key="upload.filename"
      class="bg-white rounded-lg border border-gray-200 p-4 shadow-sm"
    >
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center space-x-2 min-w-0 flex-1">
          <!-- Status Icon -->
          <div class="flex-shrink-0">
            <CloudArrowUpIcon
              v-if="upload.status === 'uploading'"
              class="h-5 w-5 text-blue-500 animate-pulse"
            />
            <ArrowPathIcon
              v-else-if="upload.status === 'processing'"
              class="h-5 w-5 text-yellow-500 animate-spin"
            />
            <CheckCircleIcon
              v-else-if="upload.status === 'completed'"
              class="h-5 w-5 text-green-500"
            />
            <ExclamationCircleIcon
              v-else-if="upload.status === 'error'"
              class="h-5 w-5 text-red-500"
            />
            <div
              v-else
              class="h-5 w-5 rounded-full bg-gray-300"
            />
          </div>

          <!-- Filename -->
          <span class="text-sm font-medium text-gray-900 truncate">
            {{ upload.filename }}
          </span>
        </div>

        <!-- Status Text -->
        <span
          class="text-xs font-medium ml-2 flex-shrink-0"
          :class="getStatusTextColor(upload.status)"
        >
          {{ getStatusText(upload.status) }}
          <template v-if="upload.status === 'uploading'">
            ({{ upload.progress }}%)
          </template>
        </span>
      </div>

      <!-- Progress Bar -->
      <div class="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-300 ease-out"
          :class="getStatusColor(upload.status)"
          :style="{ width: `${upload.progress}%` }"
        />
      </div>

      <!-- Error Message -->
      <p
        v-if="upload.status === 'error' && upload.error"
        class="mt-2 text-xs text-red-600"
      >
        {{ upload.error }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.upload-progress {
  /* Component styles */
}
</style>
