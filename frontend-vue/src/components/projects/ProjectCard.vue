<script setup lang="ts">
import {
  FolderIcon,
  EllipsisVerticalIcon,
  TrashIcon,
  PencilIcon,
} from '@heroicons/vue/24/outline'
import { ref } from 'vue'
import type { Project } from '@/types'

const props = defineProps<{
  project: Project
}>()

const emit = defineEmits<{
  (e: 'click'): void
  (e: 'delete'): void
  (e: 'edit'): void
}>()

const showMenu = ref(false)

function handleClick() {
  if (!showMenu.value) {
    emit('click')
  }
}

function handleDelete(event: Event) {
  event.stopPropagation()
  showMenu.value = false
  emit('delete')
}

function handleEdit(event: Event) {
  event.stopPropagation()
  showMenu.value = false
  emit('edit')
}

function toggleMenu(event: Event) {
  event.stopPropagation()
  showMenu.value = !showMenu.value
}

function closeMenu() {
  showMenu.value = false
}

// Status badge colors
const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  archived: 'bg-gray-100 text-gray-800',
  completed: 'bg-blue-100 text-blue-800',
}
</script>

<template>
  <div
    class="project-card bg-white rounded-lg shadow-sm border border-gray-200 hover:shadow-md hover:border-blue-300 transition-all cursor-pointer overflow-hidden"
    @click="handleClick"
    @mouseleave="closeMenu"
  >
    <!-- Cover Image or Placeholder -->
    <div class="h-32 bg-gradient-to-br from-blue-500 to-blue-600 relative">
      <img
        v-if="project.cover_image_path"
        :src="project.cover_image_path"
        :alt="project.name"
        class="w-full h-full object-cover"
      />
      <div v-else class="w-full h-full flex items-center justify-center">
        <FolderIcon class="h-16 w-16 text-white/50" />
      </div>

      <!-- Status Badge -->
      <span
        :class="[
          'absolute top-2 left-2 px-2 py-1 text-xs font-medium rounded-full',
          statusColors[project.status] || statusColors.active
        ]"
      >
        {{ project.status }}
      </span>

      <!-- Menu Button -->
      <div class="absolute top-2 right-2">
        <button
          type="button"
          class="p-1 bg-white/20 hover:bg-white/40 rounded-full transition-colors"
          @click="toggleMenu"
        >
          <EllipsisVerticalIcon class="h-5 w-5 text-white" />
        </button>

        <!-- Dropdown Menu -->
        <div
          v-if="showMenu"
          class="absolute right-0 mt-1 w-32 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10"
        >
          <button
            type="button"
            class="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center"
            @click="handleEdit"
          >
            <PencilIcon class="h-4 w-4 mr-2" />
            Edit
          </button>
          <button
            type="button"
            class="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center"
            @click="handleDelete"
          >
            <TrashIcon class="h-4 w-4 mr-2" />
            Delete
          </button>
        </div>
      </div>
    </div>

    <!-- Content -->
    <div class="p-4">
      <h3 class="font-semibold text-gray-900 truncate mb-1">
        {{ project.name }}
      </h3>
      <p v-if="project.description" class="text-sm text-gray-500 line-clamp-2 mb-3">
        {{ project.description }}
      </p>

      <!-- Metadata -->
      <div class="flex flex-wrap gap-2 text-xs text-gray-500">
        <span v-if="project.facility_name" class="bg-gray-100 px-2 py-1 rounded">
          {{ project.facility_name }}
        </span>
        <span v-if="project.system_type" class="bg-gray-100 px-2 py-1 rounded">
          {{ project.system_type }}
        </span>
      </div>

      <!-- Tags -->
      <div v-if="project.tags && project.tags.length > 0" class="mt-2 flex flex-wrap gap-1">
        <span
          v-for="tag in project.tags.slice(0, 3)"
          :key="tag"
          class="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded"
        >
          {{ tag }}
        </span>
        <span
          v-if="project.tags.length > 3"
          class="text-xs text-gray-400"
        >
          +{{ project.tags.length - 3 }} more
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
