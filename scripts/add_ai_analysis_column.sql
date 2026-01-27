-- Add AI analysis column to supplementary_documents table
-- This column stores the JSON output from AI analysis of Excel/Word files

ALTER TABLE supplementary_documents
ADD COLUMN IF NOT EXISTS ai_analysis TEXT;

-- Add comment for documentation
COMMENT ON COLUMN supplementary_documents.ai_analysis IS 'JSON storing AI analysis results from LLM processing';
