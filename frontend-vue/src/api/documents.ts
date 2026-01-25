import api from './index'
import type { Document, DocumentDetail } from '@/types'

// Response type for document upload
export interface UploadResponse {
  document_id: number
  filename: string
  message: string
  pages_detected: number
}

// Response type for retry processing
export interface RetryResponse {
  message: string
}

// Response type for getting document pages
export interface DocumentPagesResponse {
  document_id: number
  original_filename: string
  page_count: number
  pages: Array<{
    page_number: number
    equipment_count: number
    ai_analysis: string
  }>
}

/**
 * List documents with pagination
 * Note: Backend returns Document[] directly, not a pagination wrapper
 */
export async function list(skip = 0, limit = 20): Promise<Document[]> {
  const response = await api.get<Document[]>('/api/documents', {
    params: { skip, limit },
  })
  return response.data
}

/**
 * Get a single document by ID
 */
export async function get(id: number): Promise<DocumentDetail> {
  const response = await api.get<DocumentDetail>(`/api/documents/${id}`)
  return response.data
}

/**
 * Upload a document file with optional progress tracking
 * Note: Backend returns UploadResponse, not Document
 */
export async function upload(
  file: File,
  onProgress?: (percent: number) => void
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post<UploadResponse>('/api/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(percent)
      }
    },
  })

  return response.data
}

/**
 * Delete a document by ID
 */
export async function deleteDocument(id: number): Promise<void> {
  await api.delete(`/api/documents/${id}`)
}

/**
 * Retry processing a failed document
 * Note: Backend returns { message: string }, not Document
 */
export async function retry(id: number): Promise<RetryResponse> {
  const response = await api.post<RetryResponse>(`/api/documents/${id}/retry`)
  return response.data
}

/**
 * Get the URL for a page image
 * Note: This returns a URL string, not the actual image data
 */
export function getPageImageUrl(docId: number, pageNum: number): string {
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  return `${baseUrl}/api/documents/${docId}/page/${pageNum}/image`
}

/**
 * Get pages for a document
 * Note: Returns full DocumentPagesResponse with document metadata and pages array
 */
export async function getPages(id: number): Promise<DocumentPagesResponse> {
  const response = await api.get<DocumentPagesResponse>(`/api/documents/${id}/pages`)
  return response.data
}

// Export all functions as a module
export const documentsApi = {
  list,
  get,
  upload,
  delete: deleteDocument,
  retry,
  getPageImageUrl,
  getPages,
}

export default documentsApi
