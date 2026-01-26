import api from './index'
import type { Equipment, EquipmentDetail } from '@/types'

// Document Appearances Types
export interface PageAppearance {
  page_number: number
  context_text: string | null
  drawing_type: string | null
}

export interface DocumentAppearance {
  document_id: number
  document_filename: string
  document_title: string | null
  pages: PageAppearance[]
}

export interface DocumentAppearancesResponse {
  equipment_tag: string
  total_documents: number
  total_pages: number
  documents: DocumentAppearance[]
}

// Power Flow Types
export interface PowerFlowNode {
  tag: string
  depth: number
  breaker: string | null
  voltage: string | null
  wire_size: string | null
  load: string | null
  document_id: number | null
  page_number: number | null
  feeds?: string | null
  fed_by?: string | null
}

export interface PowerFlowResponse {
  equipment_tag: string
  upstream_tree: PowerFlowNode[]
  downstream_tree: PowerFlowNode[]
  total_upstream: number
  total_downstream: number
}

export interface GraphNode {
  id: string
  label: string
  type: string
  isCenter: boolean
}

export interface GraphEdge {
  from: string
  to: string
  type: string
  label: string
  details: Record<string, unknown>
}

export interface EquipmentGraphData {
  center_tag: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  equipment_info?: {
    tag: string
    type: string
    description?: string
  }
}

export interface EquipmentListParams {
  skip?: number
  limit?: number
  equipment_type?: string
  search?: string
  project_id?: number
  document_id?: number
}

/**
 * List equipment with optional filters and pagination
 * Note: Backend returns Equipment[] directly, not a pagination wrapper
 */
export async function list(params: EquipmentListParams = {}): Promise<Equipment[]> {
  const { skip = 0, limit = 20, equipment_type, search, project_id, document_id } = params

  const queryParams: Record<string, string | number> = { skip, limit }
  if (equipment_type) queryParams.equipment_type = equipment_type
  if (search) queryParams.search = search
  if (project_id) queryParams.project_id = project_id
  if (document_id) queryParams.document_id = document_id

  const response = await api.get<Equipment[]>('/api/equipment', {
    params: queryParams,
  })
  return response.data
}

/**
 * List equipment for a specific document
 */
export async function listByDocument(documentId: number, params: Omit<EquipmentListParams, 'document_id'> = {}): Promise<Equipment[]> {
  const { skip = 0, limit = 200, equipment_type, search } = params

  const queryParams: Record<string, string | number> = { skip, limit }
  if (equipment_type) queryParams.equipment_type = equipment_type
  if (search) queryParams.search = search

  const response = await api.get<Equipment[]>(`/api/equipment/by-document/${documentId}`, {
    params: queryParams,
  })
  return response.data
}

/**
 * List equipment for a specific project
 */
export async function listByProject(projectId: number, params: Omit<EquipmentListParams, 'project_id'> = {}): Promise<Equipment[]> {
  const { skip = 0, limit = 200, equipment_type, search } = params

  const queryParams: Record<string, string | number> = { skip, limit }
  if (equipment_type) queryParams.equipment_type = equipment_type
  if (search) queryParams.search = search

  const response = await api.get<Equipment[]>(`/api/equipment/by-project/${projectId}`, {
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

/**
 * Get graph visualization data for an equipment tag
 */
export async function getGraph(tag: string, depth: number = 1): Promise<EquipmentGraphData> {
  const encodedTag = encodeURIComponent(tag)
  const response = await api.get<EquipmentGraphData>(`/api/equipment/${encodedTag}/graph`, {
    params: { depth }
  })
  return response.data
}

/**
 * Get all documents where equipment appears, grouped by document with page details
 */
export async function getDocumentAppearances(tag: string): Promise<DocumentAppearancesResponse> {
  const encodedTag = encodeURIComponent(tag)
  const response = await api.get<DocumentAppearancesResponse>(`/api/equipment/${encodedTag}/documents`)
  return response.data
}

/**
 * Get power flow (upstream and downstream power hierarchy) for an equipment tag
 */
export async function getPowerFlow(tag: string, maxDepth: number = 10): Promise<PowerFlowResponse> {
  const encodedTag = encodeURIComponent(tag)
  const response = await api.get<PowerFlowResponse>(`/api/equipment/${encodedTag}/power-flow`, {
    params: { max_depth: maxDepth }
  })
  return response.data
}

// Export all functions as a module
export const equipmentApi = {
  list,
  listByDocument,
  listByProject,
  getTypes,
  getByTag,
  getGraph,
  getDocumentAppearances,
  getPowerFlow,
}

export default equipmentApi
