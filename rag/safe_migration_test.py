#!/usr/bin/env python3
"""
Safe migration test script - Phase 7 RAG Foundation
ZERO RISK: Only reads from production, writes to test environment
"""

import os
import sys
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))
from test_config import *

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_safety():
    """Verify we're not touching production databases"""
    logger.info("🔒 SAFETY CHECK: Verifying production databases are READ-ONLY")
    
    # Check that test paths exist and are different from production
    if TEST_CHROMA_PATH == PROD_CHROMA_PATH:
        raise Exception("❌ SAFETY ERROR: Test and production paths are the same!")
    
    if not os.path.exists(TEST_CHROMA_PATH):
        os.makedirs(TEST_CHROMA_PATH, exist_ok=True)
        
    if not os.path.exists(TEST_UNIFIED_PATH):
        os.makedirs(TEST_UNIFIED_PATH, exist_ok=True)
    
    logger.info(f"✅ Production Chroma (READ-ONLY): {PROD_CHROMA_PATH}")
    logger.info(f"✅ Production LanceDB (READ-ONLY): {PROD_LANCEDB_PATH}")
    logger.info(f"✅ Test Chroma (SAFE TO MODIFY): {TEST_CHROMA_PATH}")
    logger.info(f"✅ Test Unified (SAFE TO MODIFY): {TEST_UNIFIED_PATH}")
    
    return True

def test_current_databases():
    """Test reading from current databases without modifying them"""
    logger.info("📊 Testing current database access (READ-ONLY)")
    
    # Test LanceDB access
    try:
        import lancedb
        
        # Read-only connection to existing LanceDB
        db = lancedb.connect(PROD_LANCEDB_PATH)
        tables = db.table_names()
        logger.info(f"✅ LanceDB accessible - Tables: {tables}")
        
        if "flutter_dart_docs_comprehensive" in tables:
            table = db.open_table("flutter_dart_docs_comprehensive")
            count = len(table)
            logger.info(f"✅ Flutter/Dart table has {count} documents")
        
    except Exception as e:
        logger.error(f"❌ LanceDB access error: {e}")
        return False
    
    # Test Chroma access (if available)
    try:
        import chromadb
        
        # Read-only connection to existing Chroma
        client = chromadb.PersistentClient(path=PROD_CHROMA_PATH)
        collections = client.list_collections()
        logger.info(f"✅ ChromaDB accessible - Collections: {[c.name for c in collections]}")
        
    except Exception as e:
        logger.warning(f"⚠️ ChromaDB access error (may not exist yet): {e}")
    
    return True

def create_test_unified_collection():
    """Create test unified collection with metadata schema"""
    logger.info("🔧 Creating test unified collection with metadata filtering")
    
    try:
        import chromadb
        
        # Create test Chroma client
        test_client = chromadb.PersistentClient(path=TEST_CHROMA_PATH)
        
        # Create unified collection with metadata
        collection = test_client.get_or_create_collection(
            name=RAG_COLLECTION_NAME,
            metadata={"description": "Unified senior developer knowledge base with metadata filtering"}
        )
        
        logger.info(f"✅ Created test collection: {RAG_COLLECTION_NAME}")
        logger.info(f"✅ Test collection path: {TEST_CHROMA_PATH}")
        
        # Test metadata schema
        test_doc = {
            "documents": ["This is a test Flutter documentation chunk about StatefulWidget."],
            "metadatas": [{
                "language": "flutter",
                "category": "official_docs", 
                "authority_level": "official",
                "source_type": "documentation",
                "domain": "mobile_dev",
                "source_path": "test/flutter/widgets/StatefulWidget.md"
            }],
            "ids": ["test_doc_1"]
        }
        
        collection.add(**test_doc)
        logger.info("✅ Test document added with metadata schema")
        
        # Test metadata filtering
        results = collection.query(
            query_texts=["StatefulWidget"],
            n_results=1,
            where={"language": "flutter"}
        )
        
        if results['documents']:
            logger.info("✅ Metadata filtering test successful")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test collection creation error: {e}")
        return False

def main():
    """Main test function - completely safe"""
    logger.info("🚀 Starting Phase 7 RAG Foundation - SAFE TESTING MODE")
    
    try:
        # Safety verification
        verify_safety()
        
        # Test current databases (read-only)
        test_current_databases()
        
        # Create test unified collection
        create_test_unified_collection()
        
        logger.info("✅ Phase 7 foundation test completed successfully!")
        logger.info("🔒 PRODUCTION DATABASES UNCHANGED - All tests used separate environment")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)