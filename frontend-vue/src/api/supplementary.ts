import api from './index'

// Types
export type ContentCategory =
  | 'IO_LIST'
  | 'EQUIPMENT_SCHEDULE'
  | 'SEQUENCE_OF_OPERATION'
  | 'COMMISSIONING'
  | 'SUBMITTAL'
  | 'OTHER'

export interface SupplementaryDocument {
  id: number
  project_id: number
  filename: string
  original_filename: string
  document_type: 'EXCEL' | 'WORD'
  content_category: ContentCategory | null
  file_size: number | null
  processed: number  // 0=pending, 1=processing, 2=done, -1=error
  processing_error: string | null
  created_at: string
}

export interface EquipmentAlias {
  id: number
  equipment_id: number
  alias: string
  source: string | null
  confidence: number | null
  created_at: string
}

export interface EquipmentProfile {
  id: number
  equipment_id: number
  profile_json: string
  last_updated: string
}

// API Functions

export async function uploadSupplementary(
  projectId: number,
  file: File,
  contentCategory?: ContentCategory
): Promise<SupplementaryDocument> {
  const formData = new FormData()
  formData.append('file', file)
  if (contentCategory) {
    formData.append('content_category', contentCategory)
  }

  const response = await api.post<SupplementaryDocument>(
    `/api/projects/${projectId}/supplementary`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    }
  )
  return response.data
}

export async function getSupplementaryDocuments(
  projectId: number
): Promise<SupplementaryDocument[]> {
  const response = await api.get<SupplementaryDocument[]>(
    `/api/projects/${projectId}/supplementary`
  )
  return response.data
}

export async function getSupplementaryDocument(
  documentId: number
): Promise<SupplementaryDocument> {
  const response = await api.get<SupplementaryDocument>(
    `/api/supplementary/${documentId}`
  )
  return response.data
}

export async function deleteSupplementary(
  documentId: number
): Promise<void> {
  await api.delete(`/api/supplementary/${documentId}`)
}

export async function reprocessSupplementary(
  documentId: number
): Promise<{ message: string }> {
  const response = await api.post<{ message: string }>(
    `/api/supplementary/${documentId}/reprocess`
  )
  return response.data
}

export async function getEquipmentProfile(
  tag: string
): Promise<EquipmentProfile> {
  const response = await api.get<EquipmentProfile>(
    `/api/equipment/${encodeURIComponent(tag)}/profile`
  )
  return response.data
}

export async function getEquipmentAliases(
  tag: string
): Promise<EquipmentAlias[]> {
  const response = await api.get<EquipmentAlias[]>(
    `/api/equipment/${encodeURIComponent(tag)}/aliases`
  )
  return response.data
}

export async function addEquipmentAlias(
  tag: string,
  alias: string,
  source?: string,
  confidence?: number
): Promise<EquipmentAlias> {
  const response = await api.post<EquipmentAlias>(
    `/api/equipment/${encodeURIComponent(tag)}/aliases`,
    { alias, source, confidence }
  )
  return response.data
}

// Helper to get processing status text
export function getProcessingStatus(processed: number): string {
  switch (processed) {
    case 0: return 'Pending'
    case 1: return 'Processing'
    case 2: return 'Done'
    case -1: return 'Error'
    default: return 'Unknown'
  }
}

// Helper to get document type icon
export function getDocumentTypeIcon(documentType: string): string {
  switch (documentType) {
    case 'EXCEL': return '📊'
    case 'WORD': return '📝'
    default: return '📄'
  }
}
