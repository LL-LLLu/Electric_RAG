import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Equipment } from '@/types'

export const useEquipmentStore = defineStore('equipment', () => {
  // Equipment list
  const equipment = ref<Equipment[]>([])
  const totalCount = ref(0)
  const loading = ref(false)

  // Filters
  const searchQuery = ref('')
  const typeFilters = ref<string[]>([])
  const availableTypes = ref<string[]>([])

  // Computed
  const hasEquipment = computed(() => equipment.value.length > 0)
  const hasActiveFilters = computed(() =>
    searchQuery.value !== '' || typeFilters.value.length > 0
  )
  const filteredEquipment = computed(() => {
    let result = equipment.value

    // Filter by search query
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      result = result.filter(e =>
        e.tag.toLowerCase().includes(query) ||
        e.equipment_type.toLowerCase().includes(query) ||
        (e.description && e.description.toLowerCase().includes(query))
      )
    }

    // Filter by type
    if (typeFilters.value.length > 0) {
      result = result.filter(e => typeFilters.value.includes(e.equipment_type))
    }

    return result
  })

  // Actions
  function setEquipment(items: Equipment[]) {
    equipment.value = items
  }

  function setTotalCount(count: number) {
    totalCount.value = count
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function setSearchQuery(query: string) {
    searchQuery.value = query
  }

  function setTypeFilters(types: string[]) {
    typeFilters.value = types
  }

  function addTypeFilter(type: string) {
    if (!typeFilters.value.includes(type)) {
      typeFilters.value.push(type)
    }
  }

  function removeTypeFilter(type: string) {
    const index = typeFilters.value.indexOf(type)
    if (index !== -1) {
      typeFilters.value.splice(index, 1)
    }
  }

  function toggleTypeFilter(type: string) {
    if (typeFilters.value.includes(type)) {
      removeTypeFilter(type)
    } else {
      addTypeFilter(type)
    }
  }

  function clearFilters() {
    searchQuery.value = ''
    typeFilters.value = []
  }

  function setAvailableTypes(types: string[]) {
    availableTypes.value = types
  }

  return {
    equipment,
    totalCount,
    loading,
    searchQuery,
    typeFilters,
    availableTypes,
    hasEquipment,
    hasActiveFilters,
    filteredEquipment,
    setEquipment,
    setTotalCount,
    setLoading,
    setSearchQuery,
    setTypeFilters,
    addTypeFilter,
    removeTypeFilter,
    toggleTypeFilter,
    clearFilters,
    setAvailableTypes
  }
})
