# Supplementary Documents Feature Design

**Date:** 2026-01-26
**Status:** Approved
**Goal:** Enable Excel and Word document uploads to enhance RAG system answers with structured data, specifications, IO lists, sequences of operation, and other project documentation.

---

## Overview

The current system processes PDF drawings with OCR and AI analysis. This feature adds support for Excel (.xlsx, .xls, .csv) and Word (.docx) documents that contain complementary project information.

**Key Design Decisions:**
- **Hybrid storage**: Structured data for Excel (queryable) + text chunks with embeddings (semantic search)
- **Fuzzy matching**: Auto-link equipment tags across documents with confidence scores
- **Multi-source RAG**: Search PDFs, supplementary chunks, and structured data in parallel

---

## Data Model

### New Tables

**supplementary_documents**

| Column | Type | Purpose |
|--------|------|---------|
| id | int | Primary key |
| project_id | int | FK to projects |
| filename | string(255) | Storage filename |
| original_filename | string(255) | User's filename |
| document_type | string(20) | EXCEL, WORD |
| content_category | string(50) | IO_LIST, EQUIPMENT_SCHEDULE, SEQUENCE_OF_OPERATION, COMMISSIONING, SUBMITTAL, OTHER |
| file_path | string(500) | Storage path |
| file_size | int | File size in bytes |
| processed | int | 0=pending, 1=processing, 2=done, -1=error |
| processing_error | text | Error message if failed |
| created_at | datetime | Upload time |

**supplementary_chunks**

| Column | Type | Purpose |
|--------|------|---------|
| id | int | Primary key |
| document_id | int | FK to supplementary_documents |
| chunk_index | int | Order in document |
| content | text | The text content |
| source_location | string(200) | "Sheet1:A1-F20" or "Section 3.2" |
| equipment_tags | text | JSON array of tags found in chunk |
| embedding | vector(384) | For semantic search |

**equipment_data**

| Column | Type | Purpose |
|--------|------|---------|
| id | int | Primary key |
| document_id | int | FK to supplementary_documents |
| equipment_tag | string(100) | The equipment tag found |
| equipment_id | int | FK to equipment (fuzzy matched), nullable |
| match_confidence | float | How confident the fuzzy match is |
| data_type | string(50) | IO_POINT, SPECIFICATION, ALARM, SCHEDULE_ENTRY, SEQUENCE |
| data_json | text | The structured data as JSON |
| source_location | string(200) | "Sheet1:Row 15" |
| created_at | datetime | Extraction time |

**equipment_aliases**

| Column | Type | Purpose |
|--------|------|---------|
| id | int | Primary key |
| equipment_id | int | FK to equipment |
| alias | string(100) | Alternate name |
| source | string(255) | Which document introduced this alias |
| confidence | float | Match confidence |
| created_at | datetime | Creation time |

**equipment_profiles**

| Column | Type | Purpose |
|--------|------|---------|
| id | int | Primary key |
| equipment_id | int | FK to equipment, unique |
| profile_json | text | Aggregated data from all sources |
| last_updated | datetime | Last rebuild time |

---

## Processing Pipeline

### Excel Processor

```
Upload .xlsx/.xls/.csv
       ↓
Parse sheets with openpyxl/pandas
       ↓
AI detects schema (header row, equipment column, column mapping)
       ↓
Extract rows as structured data
       ↓
Fuzzy match equipment tags to existing records
       ↓
Generate text version for embedding
       ↓
Store in equipment_data + supplementary_chunks
```

**Schema Detection Prompt:**
```
Analyze this spreadsheet header and sample rows:
[header and 3 sample rows]

Identify:
1. Which column contains equipment tags?
2. What type of data is this? (IO_LIST, EQUIPMENT_SCHEDULE, etc.)
3. Map columns to standard fields (point_name, io_type, alarm_category, setpoint, hp, voltage, etc.)
```

### Word Processor

```
Upload .docx
       ↓
Parse with python-docx
       ↓
Split by section headings (H1, H2)
       ↓
Extract tables as separate chunks
       ↓
Target ~500 tokens per chunk with overlap
       ↓
Preserve heading path ("3.0 RTU > 3.2 Alarms")
       ↓
Extract equipment references via regex
       ↓
Fuzzy match and generate embeddings
       ↓
Store in supplementary_chunks + equipment_data
```

### Fuzzy Matching Algorithm

```python
def normalize_tag(tag: str) -> str:
    """Normalize for comparison: RTU-F04 → rtuf04"""
    return re.sub(r'[-_\s]', '', tag.lower())

def fuzzy_match(tag: str, equipment_list: list) -> tuple[int, float]:
    """Find best match with confidence score"""
    normalized = normalize_tag(tag)

    best_match = None
    best_score = 0

    for eq in equipment_list:
        # Compare normalized versions
        score = fuzz.ratio(normalized, normalize_tag(eq.tag))

        # Also check existing aliases
        for alias in eq.aliases:
            alias_score = fuzz.ratio(normalized, normalize_tag(alias))
            score = max(score, alias_score)

        if score > best_score:
            best_score = score
            best_match = eq

    # Return match if confidence >= 85%
    if best_score >= 85:
        return (best_match.id, best_score / 100)
    return (None, best_score / 100)
```

---

## Enhanced Search & RAG

### Multi-Source Search

```
User Query
    ↓
Query Classification (ALARM_LOOKUP, SPECIFICATION, SEQUENCE, LOCATION, etc.)
    ↓
Equipment Resolution (check aliases)
    ↓
┌───────────────────────────────────────────────────┐
│              Parallel Search                       │
├─────────────────┬─────────────────┬───────────────┤
│  PDF Pages      │  Supplementary  │  Equipment    │
│  (drawings)     │  Chunks         │  Data         │
│                 │  (text)         │  (structured) │
│  Semantic       │  Semantic       │  Tag + Type   │
│  Search         │  Search         │  Query        │
└─────────────────┴─────────────────┴───────────────┘
    ↓
Merge & Rank by source confidence
    ↓
Build context with source citations
    ↓
LLM generates answer
```

### Query Classification Priority

| Query Type | Primary Source | Secondary Sources |
|------------|----------------|-------------------|
| ALARM_LOOKUP | equipment_data (ALARM, IO_POINT) | SOO chunks, drawings |
| SPECIFICATION | equipment_data (SPECIFICATION) | schedules, submittals |
| IO_LOOKUP | equipment_data (IO_POINT) | control drawings |
| SEQUENCE | supplementary_chunks (SOO) | commissioning, drawings |
| LOCATION | PDF pages | schedules |
| POWER_TRACE | drawings (one-line) | schedules |

### Source Confidence Scoring

| Source Type | Confidence | Reasoning |
|-------------|------------|-----------|
| Equipment Schedule (Excel) | 0.95 | Structured, authoritative |
| IO List (Excel) | 0.95 | Structured, authoritative |
| Sequence of Operation | 0.90 | Written spec |
| Submittal/Cut Sheet | 0.85 | Manufacturer data |
| Drawing (PDF) | 0.80 | AI extraction may miss details |
| Commissioning Guide | 0.75 | Procedures, not equipment data |

### Equipment Profile Structure

```json
{
  "tag": "RTU-F04",
  "aliases": ["Rooftop Unit 4", "RF-4"],
  "type": "Rooftop Unit",
  "specs": {
    "hp": "10",
    "voltage": "480V/3Ph",
    "manufacturer": "Carrier",
    "model": "50XC"
  },
  "io_points": [
    {"name": "SAT", "type": "AI", "description": "Supply Air Temp"},
    {"name": "SAT-H", "type": "AI", "description": "SAT High Alarm", "alarm": "CRITICAL", "setpoint": "85°F"}
  ],
  "alarms": [
    {"name": "SAT-H Alarm", "category": "CRITICAL", "setpoint": "85°F", "description": "High supply air temperature"}
  ],
  "power_source": "Panel MCC-2, Breaker 15",
  "documents": [
    {"type": "DRAWING", "name": "E-101.pdf", "pages": [3, 7]},
    {"type": "IO_LIST", "name": "IO List.xlsx", "location": "Sheet 'RTU Points', Rows 45-47"},
    {"type": "SOO", "name": "Sequence.docx", "location": "Section 4.2"}
  ]
}
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/projects/{id}/supplementary` | POST | Upload Excel/Word file |
| `/api/projects/{id}/supplementary` | GET | List supplementary docs |
| `/api/supplementary/{id}` | GET | Get document details + extracted data |
| `/api/supplementary/{id}` | DELETE | Remove document |
| `/api/supplementary/{id}/reprocess` | POST | Re-run extraction |
| `/api/equipment/{tag}/profile` | GET | Get pre-computed equipment profile |
| `/api/equipment/{tag}/aliases` | GET | List equipment aliases |
| `/api/equipment/{tag}/aliases` | POST | Add manual alias |

---

## Frontend Changes

### Project Documents View

Add tab for supplementary documents:

```
┌─────────────────────────────────────────────┐
│ Project Documents                           │
├──────────────┬──────────────────────────────┤
│ Drawings (10)│ Supplementary (5)            │
├──────────────┴──────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│ │ IO List │ │ Schedule│ │  SOO    │        │
│ │  .xlsx  │ │  .xlsx  │ │  .docx  │        │
│ │ ✓ Done  │ │ ✓ Done  │ │ ✓ Done  │        │
│ └─────────┘ └─────────┘ └─────────┘        │
└─────────────────────────────────────────────┘
```

### Upload Modal

Extended with document type and category selection.

### Equipment Detail Panel

Show aggregated data from all sources with source citations.

### Chat Sources

Include supplementary document references:
```
Sources:
📄 E-101.pdf, Page 3
📊 IO List.xlsx, Sheet "RTU Points", Row 45
📝 Sequence.docx, Section 4.2
```

---

## File Structure

### New Files

| File | Purpose |
|------|---------|
| `backend/app/services/excel_processor.py` | Parse Excel, extract structured data |
| `backend/app/services/word_processor.py` | Parse Word, chunk text |
| `backend/app/services/supplementary_processor.py` | Orchestrate processing pipeline |
| `backend/app/services/alias_service.py` | Fuzzy matching, alias management |
| `backend/app/services/profile_service.py` | Build/update equipment profiles |
| `backend/app/api/routes/supplementary.py` | API endpoints |
| `scripts/migrations/002_supplementary_documents.sql` | Database migration |
| `frontend-vue/src/api/supplementary.ts` | API client |
| `frontend-vue/src/components/documents/SupplementaryList.vue` | List view |
| `frontend-vue/src/components/documents/SupplementaryUpload.vue` | Upload modal |
| `frontend-vue/src/components/equipment/EquipmentProfile.vue` | Enhanced detail |

### Modified Files

| File | Changes |
|------|---------|
| `backend/app/models/database.py` | Add new tables |
| `backend/app/services/search_service.py` | Query all three sources |
| `backend/app/services/rag_service.py` | Enhanced context building, query classification |
| `backend/requirements.txt` | Add openpyxl, python-docx, fuzzywuzzy |
| `frontend-vue/src/views/ProjectDocumentsView.vue` | Add supplementary tab |
| `frontend-vue/src/components/equipment/EquipmentDetail.vue` | Show profile data |

---

## Implementation Order

### Phase 1: Foundation
- Database migration (new tables)
- Excel processor service
- Word processor service
- Supplementary document API (upload, list, delete)

### Phase 2: Intelligence
- Fuzzy matching / alias service
- Equipment profile builder
- Query classification
- Enhanced search (3-source merge)

### Phase 3: Frontend
- Supplementary upload UI
- Supplementary list view
- Enhanced equipment detail with profile
- Chat source citations for supplementary docs

### Phase 4: Polish
- Source confidence scoring
- Alias review UI (optional)
- Profile rebuild triggers
- Error handling and edge cases

---

## Edge Cases & Limits

### Error Handling

| Scenario | Handling |
|----------|----------|
| Password-protected file | Reject with clear error message |
| Word doc with only images | Fall back to OCR, flag for review |
| No equipment tags found | Store as general knowledge, searchable but not equipment-linked |
| Fuzzy match confidence < 50% | Store with equipment_id=NULL, surface for manual review |
| Duplicate upload | Detect by filename + hash, prompt to replace or skip |

### File Limits

| Limit | Value |
|-------|-------|
| Max file size | 50 MB |
| Max Excel rows | 10,000 |
| Max Word pages | 500 |
| Supported formats | .xlsx, .xls, .docx, .csv |

### Profile Rebuild Triggers

Rebuild equipment profiles when:
- New supplementary document processed
- Document deleted
- Equipment alias added/modified
- Manual "refresh" requested

---

## Dependencies

### Python Packages
```
openpyxl>=3.1.0      # Excel parsing
python-docx>=1.1.0   # Word parsing
fuzzywuzzy>=0.18.0   # Fuzzy string matching
python-Levenshtein   # Fast fuzzy matching
pandas>=2.0.0        # CSV and data manipulation
```

---

## Success Criteria

1. User can upload Excel/Word files to a project
2. System extracts and links equipment data automatically
3. RAG answers include information from all document types
4. Equipment detail shows aggregated data with source citations
5. Search finds relevant content across PDFs, Excel, and Word
6. Fuzzy matching correctly links 85%+ of equipment references
