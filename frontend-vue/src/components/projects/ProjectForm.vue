<script setup lang="ts">
import { ref, computed } from 'vue'
import { XMarkIcon } from '@heroicons/vue/24/outline'
import type { ProjectCreate, Project } from '@/types'

const props = defineProps<{
  project?: Project
}>()

const emit = defineEmits<{
  (e: 'submit', data: ProjectCreate): void
  (e: 'cancel'): void
}>()

// Form data
const name = ref(props.project?.name || '')
const description = ref(props.project?.description || '')
const systemType = ref(props.project?.system_type || '')
const facilityName = ref(props.project?.facility_name || '')
const status = ref(props.project?.status || 'active')
const notes = ref(props.project?.notes || '')
const tagsInput = ref(props.project?.tags?.join(', ') || '')

const loading = ref(false)
const error = ref<string | null>(null)

// Validation
const isValid = computed(() => name.value.trim().length > 0)
const isEditing = computed(() => !!props.project)

// System type options
const systemTypes = [
  'Electrical',
  'Mechanical',
  'HVAC',
  'Plumbing',
  'Fire Protection',
  'Controls',
  'Other',
]

// Status options
const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'archived', label: 'Archived' },
  { value: 'completed', label: 'Completed' },
]

// Parse tags from comma-separated string
function parseTags(input: string): string[] {
  return input
    .split(',')
    .map(tag => tag.trim())
    .filter(tag => tag.length > 0)
}

// Handle form submission
async function handleSubmit() {
  if (!isValid.value) return

  loading.value = true
  error.value = null

  try {
    const data: ProjectCreate = {
      name: name.value.trim(),
      description: description.value.trim() || undefined,
      system_type: systemType.value || undefined,
      facility_name: facilityName.value.trim() || undefined,
      status: status.value,
      notes: notes.value.trim() || undefined,
      tags: parseTags(tagsInput.value),
    }

    emit('submit', data)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save project'
  } finally {
    loading.value = false
  }
}

// Handle cancel
function handleCancel() {
  emit('cancel')
}

// Close on escape key
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    handleCancel()
  }
}
</script>

<template>
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
    @click.self="handleCancel"
    @keydown="handleKeydown"
  >
    <div class="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-gray-200">
        <h2 class="text-xl font-semibold text-gray-900">
          {{ isEditing ? 'Edit Project' : 'Create New Project' }}
        </h2>
        <button
          type="button"
          class="p-1 text-gray-400 hover:text-gray-600 transition-colors"
          @click="handleCancel"
        >
          <XMarkIcon class="h-6 w-6" />
        </button>
      </div>

      <!-- Form -->
      <form class="p-4 space-y-4" @submit.prevent="handleSubmit">
        <!-- Error -->
        <div v-if="error" class="bg-red-50 text-red-700 px-3 py-2 rounded-lg text-sm">
          {{ error }}
        </div>

        <!-- Name -->
        <div>
          <label for="name" class="block text-sm font-medium text-gray-700 mb-1">
            Project Name *
          </label>
          <input
            id="name"
            v-model="name"
            type="text"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Enter project name"
          />
        </div>

        <!-- Description -->
        <div>
          <label for="description" class="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <textarea
            id="description"
            v-model="description"
            rows="3"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Describe the project"
          ></textarea>
        </div>

        <!-- Two Column Layout -->
        <div class="grid grid-cols-2 gap-4">
          <!-- System Type -->
          <div>
            <label for="systemType" class="block text-sm font-medium text-gray-700 mb-1">
              System Type
            </label>
            <select
              id="systemType"
              v-model="systemType"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select type</option>
              <option v-for="type in systemTypes" :key="type" :value="type">
                {{ type }}
              </option>
            </select>
          </div>

          <!-- Facility Name -->
          <div>
            <label for="facilityName" class="block text-sm font-medium text-gray-700 mb-1">
              Facility Name
            </label>
            <input
              id="facilityName"
              v-model="facilityName"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Plant or building name"
            />
          </div>
        </div>

        <!-- Status -->
        <div>
          <label for="status" class="block text-sm font-medium text-gray-700 mb-1">
            Status
          </label>
          <div class="flex gap-4">
            <label
              v-for="option in statusOptions"
              :key="option.value"
              class="flex items-center"
            >
              <input
                v-model="status"
                type="radio"
                :value="option.value"
                class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
              />
              <span class="ml-2 text-sm text-gray-700">{{ option.label }}</span>
            </label>
          </div>
        </div>

        <!-- Tags -->
        <div>
          <label for="tags" class="block text-sm font-medium text-gray-700 mb-1">
            Tags
          </label>
          <input
            id="tags"
            v-model="tagsInput"
            type="text"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Comma-separated tags (e.g., urgent, phase-1)"
          />
          <p class="mt-1 text-xs text-gray-500">Separate multiple tags with commas</p>
        </div>

        <!-- Notes -->
        <div>
          <label for="notes" class="block text-sm font-medium text-gray-700 mb-1">
            Notes
          </label>
          <textarea
            id="notes"
            v-model="notes"
            rows="2"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Additional notes"
          ></textarea>
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button
            type="button"
            class="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            :disabled="loading"
            @click="handleCancel"
          >
            Cancel
          </button>
          <button
            type="submit"
            class="px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="!isValid || loading"
          >
            {{ loading ? 'Saving...' : (isEditing ? 'Save Changes' : 'Create Project') }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
