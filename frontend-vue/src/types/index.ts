// TypeScript type definitions for the Electric RAG application
// These types match the backend FastAPI schemas exactly

// ============================================
// Document Types
// ============================================

export interface Document {
  id: number
  filename: string
  original_filename: string
  file_size: number
  page_count: number
  upload_date: string
  processed: number  // 0=pending, 1=processing, 2=done, -1=error
  pages_processed: number
  processing_error: string | null
  title: string | null
  drawing_number: string | null
  revision: string | null
  system: string | null
  area: string | null
}

export interface PageSummary {
  id: number
  page_number: number
  equipment_count: number
}

export interface DocumentDetail extends Document {
  equipment_count: number
  pages: PageSummary[]
}

// ============================================
// Equipment Types
// ============================================

export interface Equipment {
  id: number
  tag: string
  equipment_type: string
  description: string | null
  manufacturer: string | null
  model_number: string | null
  document_id: number
  primary_page: number
}

export interface EquipmentLocation {
  document_filename: string
  document_title: string | null
  page_number: number
  context_text: string | null
}

export interface Relationship {
  id: number
  source_tag: string
  target_tag: string
  relationship_type: string
  confidence: number
}

export interface EquipmentDetail extends Equipment {
  locations: EquipmentLocation[]
  controls: Relationship[]
  controlled_by: Relationship[]
}

// ============================================
// Search Types
// ============================================

export interface SearchResultEquipment {
  id: number
  tag: string
  equipment_type: string
}

export interface SearchResult {
  equipment: SearchResultEquipment | null
  document: Document
  page_number: number
  relevance_score: number
  snippet: string | null
  match_type: string
}

export interface SearchResponse {
  query: string
  query_type: string
  results: SearchResult[]
  total_count: number
  response_time_ms: number
}

export interface RAGResponse {
  query: string
  answer: string
  sources: SearchResult[]
  query_type: string
  confidence: number
}

// ============================================
// API Response Types
// ============================================

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

// Note: EquipmentListResponse removed - backend returns Equipment[] directly
// Note: EquipmentTypesResponse removed - backend returns string[] directly

// ============================================
// Upload Types (frontend-specific)
// ============================================

export interface UploadProgress {
  filename: string
  progress: number
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error'
  error?: string
}

// ============================================
// Viewer Types (frontend-specific)
// ============================================

export interface ViewerDocument {
  id: number
  filename: string
  page_count: number
}

export interface PanPosition {
  x: number
  y: number
}

// ============================================
// Search Mode Types (frontend-specific)
// ============================================

export type SearchMode = 'search' | 'ai'
