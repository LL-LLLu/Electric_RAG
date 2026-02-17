import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { EquipmentDetail } from '@/types'
import * as equipmentApi from '@/api/equipment'

export const useEquipmentQuickView = defineStore('equipmentQuickView', () => {
  const isOpen = ref(false)
  const currentTag = ref<string | null>(null)
  const equipment = ref<EquipmentDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const history = ref<string[]>([])

  async function open(tag: string) {
    if (currentTag.value && currentTag.value !== tag) {
      history.value.push(currentTag.value)
    }
    currentTag.value = tag
    isOpen.value = true
    loading.value = true
    error.value = null
    try {
      equipment.value = await equipmentApi.getByTag(tag)
    } catch {
      error.value = `Failed to load equipment "${tag}"`
      equipment.value = null
    } finally {
      loading.value = false
    }
  }

  function close() {
    isOpen.value = false
    currentTag.value = null
    equipment.value = null
    history.value = []
  }

  async function goBack() {
    const prev = history.value.pop()
    if (prev) {
      currentTag.value = prev
      loading.value = true
      error.value = null
      try {
        equipment.value = await equipmentApi.getByTag(prev)
      } catch {
        error.value = `Failed to load equipment "${prev}"`
      } finally {
        loading.value = false
      }
    }
  }

  return { isOpen, currentTag, equipment, loading, error, history, open, close, goBack }
})
