<script setup lang="ts">
import { ref } from 'vue'
import { DocumentArrowUpIcon } from '@heroicons/vue/24/outline'

const emit = defineEmits<{
  upload: [file: File]
}>()

const isDragOver = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

// Supported file extensions
const SUPPORTED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif', '.webp', '.heic', '.heif']

function isSupportedFile(file: File): boolean {
  const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))
  return SUPPORTED_EXTENSIONS.includes(ext) || file.type.startsWith('image/')
}

function handleDragEnter(event: DragEvent) {
  event.preventDefault()
  isDragOver.value = true
}

function handleDragLeave(event: DragEvent) {
  event.preventDefault()
  isDragOver.value = false
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  isDragOver.value = false

  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    processFiles(files)
  }
}

function handleClick() {
  fileInput.value?.click()
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    processFiles(files)
  }
  // Reset input so the same file can be selected again
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

function processFiles(files: FileList) {
  for (let i = 0; i < files.length; i++) {
    const file = files.item(i)
    if (file && isSupportedFile(file)) {
      emit('upload', file)
    }
  }
}
</script>

<template>
  <div
    class="file-uploader relative rounded-lg border-2 border-dashed transition-all duration-200 cursor-pointer"
    :class="[
      isDragOver
        ? 'border-blue-500 bg-blue-50'
        : 'border-gray-300 bg-gray-50 hover:border-gray-400 hover:bg-gray-100'
    ]"
    @dragenter="handleDragEnter"
    @dragleave="handleDragLeave"
    @dragover="handleDragOver"
    @drop="handleDrop"
    @click="handleClick"
  >
    <input
      ref="fileInput"
      type="file"
      accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.gif,.webp,.heic,.heif,image/*"
      class="hidden"
      multiple
      @change="handleFileSelect"
    />

    <div class="flex flex-col items-center justify-center py-12 px-6">
      <DocumentArrowUpIcon
        class="h-12 w-12 mb-4 transition-colors duration-200"
        :class="isDragOver ? 'text-blue-500' : 'text-gray-400'"
      />

      <p class="text-lg font-medium text-gray-700 mb-1">
        <span v-if="isDragOver">Drop files here</span>
        <span v-else>Drag and drop files here</span>
      </p>

      <p class="text-sm text-gray-500 mb-4">
        or click to browse
      </p>

      <p class="text-xs text-gray-400">
        PDF and image files (PNG, JPG, TIFF, etc.)
      </p>
    </div>
  </div>
</template>

<style scoped>
.file-uploader {
  min-height: 200px;
}
</style>
