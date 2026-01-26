// TypeScript type definitions for the Electric RAG application
// These types match the backend FastAPI schemas exactly

// ============================================
// Project Types
// ============================================

export interface Project {
  id: number
  name: string
  description: string | null
  system_type: string | null
  facility_name: string | null
  status: string
  cover_image_path: string | null
  notes: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface ProjectStats {
  document_count: number
  equipment_count: number
  conversation_count: number
  page_count: number
}

export interface ProjectDetail extends Project {
  stats: ProjectStats
}

export interface ProjectCreate {
  name: string
  description?: string | null
  system_type?: string | null
  facility_name?: string | null
  status?: string
  notes?: string | null
  tags?: string[]
}

export interface ProjectUpdate {
  name?: string
  description?: string | null
  system_type?: string | null
  facility_name?: string | null
  status?: string
  notes?: string | null
  tags?: string[]
}

// ============================================
// Conversation Types
// ============================================

export interface Conversation {
  id: number
  project_id: number
  title: string | null
  created_at: string
  updated_at: string
}

export interface SourceReference {
  document_id: number
  document_name: string
  page_number: number
  snippet: string | null
  bbox: { x_min: number; y_min: number; x_max: number; y_max: number } | null
  equipment_tag: string | null
}

export interface Message {
  id: number
  conversation_id: number
  role: 'user' | 'assistant'
  content: string
  sources: SourceReference[] | null
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

export interface ConversationCreate {
  title?: string | null
}

export interface MessageCreate {
  content: string
}

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
  drawing_type: string | null
}

export interface DocumentDetail extends Document {
  equipment_count: number
  pages: PageSummary[]
}

export interface DocumentProjectAssign {
  project_id: number | null  // null means unassign from project
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
  document_id: number
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
