#!/usr/bin/env python3
"""
Test configuration for Phase 7 RAG integration - ZERO RISK
Uses completely separate databases for testing
"""

import os

# TEST ENVIRONMENT PATHS (Never touches production)
TEST_CHROMA_PATH = "/mnt/caseSSD/mcp_server_project/rag/test_chroma"
TEST_UNIFIED_PATH = "/mnt/caseSSD/mcp_server_project/rag/test_unified"

# PRODUCTION PATHS (READ-ONLY for migration)
PROD_CHROMA_PATH = "/mnt/caseSSD/mcp_server_data/vector_db"
PROD_LANCEDB_PATH = "/mnt/caseSSD/mcp_server_project/rag/lancedb_data"

# RAG CONFIGURATION
RAG_COLLECTION_NAME = "senior_dev_knowledge"
EMBEDDING_MODEL = "nomic-embed-text:latest"

# METADATA SCHEMA FOR UNIFIED COLLECTION
METADATA_SCHEMA = {
    "language": ["flutter", "dart", "python", "javascript", "typescript", "rust", "go", "java"],
    "category": ["official_docs", "best_practices", "code_examples", "tutorials", "style_guides"],
    "authority_level": ["official", "industry_standard", "expert_article", "community"],
    "source_type": ["documentation", "sample_code", "style_guide", "tutorial"],
    "domain": ["mobile_dev", "web_dev", "backend", "general"]
}

# AUTHORITY WEIGHTS (for retrieval scoring)
AUTHORITY_WEIGHTS = {
    "official": 0.9,
    "industry_standard": 0.8, 
    "expert_article": 0.7,
    "community": 0.6
}

print("✅ Test configuration loaded - NO PRODUCTION DATABASES WILL BE MODIFIED")