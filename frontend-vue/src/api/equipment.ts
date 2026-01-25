import api from './index'
import type { Equipment, EquipmentDetail } from '@/types'

export interface EquipmentListParams {
  skip?: number
  limit?: number
  equipment_type?: string
  search?: string
}

/**
 * List equipment with optional filters and pagination
 * Note: Backend returns Equipment[] directly, not a pagination wrapper
 */
export async function list(params: EquipmentListParams = {}): Promise<Equipment[]> {
  const { skip = 0, limit = 20, equipment_type, search } = params

  const queryParams: Record<string, string | number> = { skip, limit }
  if (equipment_type) queryParams.equipment_type = equipment_type
  if (search) queryParams.search = search

  const response = await api.get<Equipment[]>('/api/equipment', {
    params: queryParams,
  })
  return response.data
}

/**
 * Get all available equipment types
 * Note: Backend returns string[] directly, not a wrapper object
 */
export async function getTypes(): Promise<string[]> {
  const response = await api.get<string[]>('/api/equipment/types')
  return response.data
}

/**
 * Get equipment details by tag
 */
export async function getByTag(tag: string): Promise<EquipmentDetail> {
  // URL encode the tag in case it contains special characters
  const encodedTag = encodeURIComponent(tag)
  const response = await api.get<EquipmentDetail>(`/api/equipment/${encodedTag}`)
  return response.data
}

// Export all functions as a module
export const equipmentApi = {
  list,
  getTypes,
  getByTag,
}

export default equipmentApi
