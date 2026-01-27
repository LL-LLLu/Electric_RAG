-- Add progress tracking columns to documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS pages_processed INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_error TEXT;

-- Add AI analysis columns to pages table
ALTER TABLE pages ADD COLUMN IF NOT EXISTS ai_analysis TEXT;
ALTER TABLE pages ADD COLUMN IF NOT EXISTS ai_equipment_list TEXT;
