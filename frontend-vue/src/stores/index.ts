// Re-export all stores for convenient imports
export { useAppStore, type AppStats } from './app'
export { useDocumentsStore } from './documents'
export { useEquipmentStore } from './equipment'
export { useSearchStore } from './search'
export { useViewerStore } from './viewer'

// Re-export types from the centralized types module
export type {
  // Document types
  Document,
  DocumentDetail,
  PageSummary,
  UploadProgress,
  // Equipment types
  Equipment,
  EquipmentDetail,
  EquipmentLocation,
  Relationship,
  // Search types
  SearchResult,
  SearchResponse,
  RAGResponse,
  SearchMode,
  // Viewer types
  ViewerDocument,
  PanPosition,
} from '@/types'
