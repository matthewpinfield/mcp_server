# DATABASE INVENTORY - MCP SERVER PROJECT

## RAG SYSTEM DATABASES (M.2 SSD)

### 1. MAIN_RAG_DB (Primary RAG) ✅
- **LOCATION**: `/opt/mcp/rag/main_rag.db`
- **SIZE**: 45.84 MB (48,070,656 bytes)
- **TYPE**: ChromaDB (SQLite3)
- **PURPOSE**: Flutter/Dart RAG documentation (7,412 embeddings)
- **TABLES**: 20 tables including embeddings, embedding_metadata, collections
- **SAMPLE DATA**: Contains Flutter Riverpod docs, Dart API documentation, StateProvider examples
- **STATUS**: Active - Used by RAG system for code documentation queries

### 2. FLUTTER_DOCS_DB (Secondary RAG) ✅
- **LOCATION**: `/opt/mcp/rag/flutter_docs.db`
- **SIZE**: 79.50 MB (83,357,696 bytes)
- **TYPE**: ChromaDB (SQLite3)
- **PURPOSE**: Flutter-only RAG database
- **EMBEDDINGS**: 5,098 records
- **STATUS**: Active RAG system

## MEMORY SYSTEM DATABASES

### TIER 1 (Redis - Short-term Memory) ✅
- **LOCATION**: `/opt/mcp/tier1/memory.rdb` (M.2 SSD)
- **SIZE**: Minimal
- **TYPE**: Redis in-memory store with persistence
- **PURPOSE**: Fast short-term conversation context
- **STATUS**: **WORKING** - Proper MCP location with clean naming

### TIER 2 (MongoDB - Permanent Memory) ✅
- **LOCATION**: `/mnt/caseSSD/mcp_server_data/tier2_mongodb/`
- **TYPE**: MongoDB
- **PURPOSE**: Permanent rules/preferences storage
- **PREVIOUS CONTENT**: Originally contained 36 rules including Bishop identity
- **STATUS**: **PURGED** - Database dropped during testing

### TIER 3a (ChromaDB - SSD Archive) ✅
- **LOCATION**: `/mnt/caseSSD/mcp_server_data/tier3_memory_db/`
- **TYPE**: ChromaDB (SQLite3)
- **PURPOSE**: Recent archived conversations (14+ days from Tier 1)
- **STATUS**: **READY** - Directory created, awaiting initialization

### TIER 3b (ChromaDB - NAS Archive) ✅
- **LOCATION**: `/mnt/my_nas_mcp_share/archives/memory_vector_db/chroma.sqlite3`
- **SIZE**: 0.16 MB
- **TYPE**: ChromaDB (SQLite3)
- **PURPOSE**: Long-term archived conversations (30+ days from Tier 3a)
- **COLLECTIONS**: 2 (`long_term_memory`, `nas_archive`)
- **EMBEDDINGS**: 0 records
- **STATUS**: Empty - No stored memories

## UNKNOWN PURPOSE DATABASES

### 3. OPERATIONAL_DB 
- **LOCATION**: `/mnt/caseSSD/mcp_server_data/operational_db.sqlite`
- **SIZE**: 0.06 MB (65,536 bytes)
- **TYPE**: SQLite3
- **PURPOSE**: Activity logging and operational metrics
- **TABLES**: 3 tables (project_context, activity_log, sqlite_sequence)
- **RECORDS**: 424 activity log entries
- **SAMPLE DATA**: `'add_to_my_knowledge'` operations, document count tracking
- **STATUS**: Active - Logs system operations

## SUMMARY STATISTICS

- **Total Databases Found**: 7
- **RAG Databases**: 2 (active, on M.2 SSD)
- **Memory System Databases**: 4 (Tier 1: minimal data, Tier 2: purged, Tier 3: empty)
- **Unknown Purpose**: 1
- **Archived Databases**: 2
- **Total Storage Used**: ~316 MB (excluding MongoDB)
- **Largest Database**: OLD_RAG_FINAL (109.21 MB)
- **Most Records**: MAIN_RAG_DB (7,412 embeddings) & FLUTTER_DOCS_DB (5,098 embeddings)

## CRITICAL FINDINGS

### 🚨 MYSTERY: Bishop Identity Source Unknown
After comprehensive purging of all known memory storage:
- **Tier 1 (Redis)**: Completely flushed ✓
- **Tier 2 (MongoDB)**: Database dropped ✓  
- **Tier 3 (NAS ChromaDB)**: Found but empty (0 embeddings) ✓
- **RAG Databases**: Contain only Flutter/Dart documentation ✓
- **Code Search**: No hardcoded Bishop references found ✓

**Result**: System STILL responds "My name is Bishop" despite all memory purges!

**Conclusion**: Bishop identity is stored in an unknown location not documented in this inventory.

### Configuration vs Reality Mismatches

1. **Tier 3 Memory System**: 
   - Config: `/mnt/caseSSD/mcp_server_data/tier3_memory_db` (non-existent)
   - Reality: `/mnt/my_nas_mcp_share/archives/memory_vector_db/` (empty)

2. **Memory Stats Reporting**: 
   - All database connections show "unknown" status
   - Indicates memory system initialization issues

## NEXT STEPS

1. **Locate Bishop Identity Source**: Must be stored outside these 8 catalogued databases
2. **Fix Memory System Configuration**: Align code paths with actual database locations  
3. **Investigate Alternative Storage**: Check for hidden caches, environment variables, or model fine-tuning
4. **Debug Memory System Status**: Fix "unknown" connection reporting

## ARCHIVED DATABASES

### 4. OLD_FLUTTER_RAG
- **LOCATION**: `/mnt/caseSSD/mcp_server_project/superceeded/rag_unused/flutter_only_db/chroma.sqlite3`
- **SIZE**: 79.50 MB (83,357,696 bytes)
- **TYPE**: ChromaDB (SQLite3)
- **PURPOSE**: Legacy Flutter-only RAG database
- **STATUS**: Archived/Unused

### 5. OLD_RAG_FINAL
- **LOCATION**: `/mnt/caseSSD/mcp_server_project/superceeded/rag_unused/rag_db_final/chroma.sqlite3`
- **SIZE**: 109.21 MB (114,511,872 bytes)
- **TYPE**: ChromaDB (SQLite3)
- **PURPOSE**: Legacy "final" RAG database
- **STATUS**: Archived/Unused

---
*Generated: 2025-06-22*
*Last Updated: After complete system-wide database inventory across M.2, caseSSD, and NAS*