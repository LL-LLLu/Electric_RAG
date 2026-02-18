import api, { apiBaseURL } from "./index";
import type { Document, DocumentDetail, DocumentProjectAssign } from "@/types";

// Response type for document upload
export interface UploadResponse {
  document_id: number;
  filename: string;
  message: string;
  pages_detected: number;
}

// Response type for retry processing
export interface RetryResponse {
  message: string;
}

// Response type for getting document pages
export interface DocumentPagesResponse {
  document_id: number;
  original_filename: string;
  page_count: number;
  pages: Array<{
    page_number: number;
    equipment_count: number;
    ai_analysis: string;
  }>;
}

// Bulk operation types
export interface BulkOperationResponse {
  success_count: number;
  failed_count: number;
  failed_ids: number[];
  message: string;
}

/**
 * List documents with pagination
 * Note: Backend returns Document[] directly, not a pagination wrapper
 */
export async function list(skip = 0, limit = 20): Promise<Document[]> {
  const response = await api.get<Document[]>("/api/documents", {
    params: { skip, limit },
  });
  return response.data;
}

/**
 * List documents for a specific project
 */
export async function listByProject(
  projectId: number,
  skip = 0,
  limit = 50,
): Promise<Document[]> {
  const response = await api.get<Document[]>(
    `/api/documents/project/${projectId}`,
    {
      params: { skip, limit },
    },
  );
  return response.data;
}

/**
 * List documents not assigned to any project
 */
export async function listUnassigned(
  skip = 0,
  limit = 50,
): Promise<Document[]> {
  const response = await api.get<Document[]>("/api/documents/unassigned", {
    params: { skip, limit },
  });
  return response.data;
}

/**
 * Get a single document by ID
 */
export async function get(id: number): Promise<DocumentDetail> {
  const response = await api.get<DocumentDetail>(`/api/documents/${id}`);
  return response.data;
}

/**
 * Upload a document file with optional progress tracking
 * Note: Backend returns UploadResponse, not Document
 */
export async function upload(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post<UploadResponse>(
    "/api/documents/upload",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total,
          );
          onProgress(percent);
        }
      },
    },
  );

  return response.data;
}

/**
 * Delete a document by ID
 */
export async function deleteDocument(id: number): Promise<void> {
  await api.delete(`/api/documents/${id}`);
}

/**
 * Retry processing a failed document
 * Note: Backend returns { message: string }, not Document
 */
export async function retry(id: number): Promise<RetryResponse> {
  const response = await api.post<RetryResponse>(`/api/documents/${id}/retry`);
  return response.data;
}

/**
 * Assign or reassign a document to a project
 * Pass null for project_id to unassign from all projects
 */
export async function assignToProject(
  documentId: number,
  data: DocumentProjectAssign,
): Promise<Document> {
  const response = await api.patch<Document>(
    `/api/documents/${documentId}/project`,
    data,
  );
  return response.data;
}

/**
 * Get the URL for a page image
 * Note: This returns a URL string, not the actual image data
 */
export function getPageImageUrl(docId: number, pageNum: number): string {
  return `${apiBaseURL}/api/documents/${docId}/page/${pageNum}/image`;
}

/**
 * Get pages for a document
 * Note: Returns full DocumentPagesResponse with document metadata and pages array
 */
export async function getPages(id: number): Promise<DocumentPagesResponse> {
  const response = await api.get<DocumentPagesResponse>(
    `/api/documents/${id}/pages`,
  );
  return response.data;
}

/**
 * Bulk assign documents to a project
 */
export async function bulkAssign(
  documentIds: number[],
  projectId: number | null,
): Promise<BulkOperationResponse> {
  const response = await api.post<BulkOperationResponse>(
    "/api/documents/bulk/assign",
    {
      document_ids: documentIds,
      project_id: projectId,
    },
  );
  return response.data;
}

/**
 * Bulk delete documents
 */
export async function bulkDelete(
  documentIds: number[],
): Promise<BulkOperationResponse> {
  const response = await api.post<BulkOperationResponse>(
    "/api/documents/bulk/delete",
    {
      document_ids: documentIds,
    },
  );
  return response.data;
}

/**
 * Bulk reprocess documents
 */
export async function bulkReprocess(
  documentIds: number[],
): Promise<BulkOperationResponse> {
  const response = await api.post<BulkOperationResponse>(
    "/api/documents/bulk/reprocess",
    {
      document_ids: documentIds,
    },
  );
  return response.data;
}

// Export all functions as a module
export const documentsApi = {
  list,
  listByProject,
  listUnassigned,
  get,
  upload,
  delete: deleteDocument,
  retry,
  assignToProject,
  getPageImageUrl,
  getPages,
  bulkAssign,
  bulkDelete,
  bulkReprocess,
};

export default documentsApi;
