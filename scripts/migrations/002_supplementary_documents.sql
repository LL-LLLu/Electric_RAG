-- Migration: Add supplementary documents support
-- Purpose: Enable Excel and Word document uploads to enhance RAG with structured data
-- Created: 2026-01-26

-- ============================================================================
-- TABLE 1: supplementary_documents
-- Stores metadata for uploaded Excel/Word files that supplement the drawings
-- These documents contain structured data like IO lists, equipment schedules,
-- sequences of operation, commissioning reports, and submittals
-- ============================================================================
CREATE TABLE IF NOT EXISTS supplementary_documents (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    document_type VARCHAR(20) NOT NULL,  -- EXCEL, WORD
    content_category VARCHAR(50),  -- IO_LIST, EQUIPMENT_SCHEDULE, SEQUENCE_OF_OPERATION, COMMISSIONING, SUBMITTAL, OTHER
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    processed INTEGER DEFAULT 0,  -- 0=pending, 1=processing, 2=done, -1=error
    processing_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient project-based queries
CREATE INDEX IF NOT EXISTS idx_supplementary_documents_project
    ON supplementary_documents(project_id);

-- ============================================================================
-- TABLE 2: supplementary_chunks
-- Stores text chunks extracted from supplementary documents for RAG retrieval
-- Each chunk includes source location and equipment tag references for linking
-- ============================================================================
CREATE TABLE IF NOT EXISTS supplementary_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES supplementary_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_location VARCHAR(200),  -- "Sheet1:A1-F20" or "Section 3.2"
    equipment_tags TEXT,  -- JSON array of tags found in this chunk
    embedding vector(384)  -- Same dimension as page embeddings for unified search
);

-- Index for efficient document-based queries
CREATE INDEX IF NOT EXISTS idx_supplementary_chunks_document
    ON supplementary_chunks(document_id);

-- ============================================================================
-- TABLE 3: equipment_data
-- Stores structured data extracted from supplementary documents linked to equipment
-- Captures IO points, specifications, alarms, schedules, and sequences
-- ============================================================================
CREATE TABLE IF NOT EXISTS equipment_data (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES supplementary_documents(id) ON DELETE CASCADE,
    equipment_tag VARCHAR(100) NOT NULL,
    equipment_id INTEGER REFERENCES equipment(id) ON DELETE SET NULL,
    match_confidence FLOAT,  -- Confidence score for tag-to-equipment matching
    data_type VARCHAR(50) NOT NULL,  -- IO_POINT, SPECIFICATION, ALARM, SCHEDULE_ENTRY, SEQUENCE
    data_json TEXT NOT NULL,  -- Structured data as JSON for flexibility
    source_location VARCHAR(200),  -- Source reference within document
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient tag-based lookups (e.g., "find all IO points for AHU-1")
CREATE INDEX IF NOT EXISTS idx_equipment_data_tag
    ON equipment_data(equipment_tag);

-- Index for efficient equipment-based lookups (e.g., "find all data for equipment #42")
CREATE INDEX IF NOT EXISTS idx_equipment_data_equipment
    ON equipment_data(equipment_id);

-- ============================================================================
-- TABLE 4: equipment_aliases
-- Stores alternative names/tags for equipment found in supplementary documents
-- Helps match equipment across different naming conventions in various documents
-- Example: "AHU-1" might be called "Air Handler 1" or "AHU1" in different docs
-- ============================================================================
CREATE TABLE IF NOT EXISTS equipment_aliases (
    id SERIAL PRIMARY KEY,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    alias VARCHAR(100) NOT NULL,
    source VARCHAR(255),  -- Document or source where this alias was found
    confidence FLOAT,  -- Confidence that this alias refers to the equipment
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(equipment_id, alias)  -- Prevent duplicate aliases for same equipment
);

-- Index for efficient alias lookups during document processing
CREATE INDEX IF NOT EXISTS idx_equipment_aliases_alias
    ON equipment_aliases(alias);

-- ============================================================================
-- TABLE 5: equipment_profiles
-- Stores aggregated equipment profiles combining data from all sources
-- Provides a unified view of equipment with all known information
-- Updated incrementally as new documents are processed
-- ============================================================================
CREATE TABLE IF NOT EXISTS equipment_profiles (
    id SERIAL PRIMARY KEY,
    equipment_id INTEGER NOT NULL UNIQUE REFERENCES equipment(id) ON DELETE CASCADE,
    profile_json TEXT NOT NULL,  -- Comprehensive equipment profile as JSON
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Note: equipment_id already has UNIQUE constraint which creates an implicit index
