#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions
import lancedb
import pyarrow as pa
import numpy as np
import os
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ChromaDB_to_LanceDB_Converter")

def convert_chromadb_to_lancedb(
    chroma_db_path: str,
    chroma_collection_name: str,
    lance_db_path: str,
    lance_table_name: str,
    embedding_model: str = "nomic-embed-text:latest",
    ollama_url: str = "http://127.0.0.1:11434"
):
    """Convert ChromaDB to LanceDB format"""
    
    logger.info(f" Converting ChromaDB to LanceDB")
    logger.info(f"Source: {chroma_db_path}/{chroma_collection_name}")
    logger.info(f"Target: {lance_db_path}/{lance_table_name}")
    
    try:
        # Connect to ChromaDB
        logger.info(" Reading from ChromaDB...")
        chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        chroma_collection = chroma_client.get_collection(
            name=chroma_collection_name,
            embedding_function=embedding_functions.OllamaEmbeddingFunction(
                model_name=embedding_model,
                url=ollama_url
            )
        )
        
        # Get all data from ChromaDB
        logger.info("📊 Fetching all data from ChromaDB...")
        results = chroma_collection.get(include=['embeddings', 'documents', 'metadatas'])
        
        total_docs = len(results['documents'])
        logger.info(f"Found {total_docs} documents to convert")
        
        if total_docs == 0:
            logger.warning("No documents found in ChromaDB collection")
            return False
        
        # Prepare data for LanceDB
        logger.info("🔧 Preparing data for LanceDB...")
        
        # Extract data
        documents = results['documents']
        embeddings = results['embeddings']
        metadatas = results['metadatas']
        ids = results['ids']
        
        # Convert embeddings to numpy array if needed
        if embeddings is not None and len(embeddings) > 0:
            if isinstance(embeddings[0], list):
                embeddings = np.array(embeddings, dtype=np.float32)
            elif not isinstance(embeddings, np.ndarray):
                embeddings = np.array(embeddings, dtype=np.float32)
        
        # Prepare metadata fields for LanceDB schema
        # LanceDB requires consistent types, so we'll extract common fields
        languages = []
        authorities = []
        doc_types = []
        sources = []
        chunk_indices = []
        
        for meta in metadatas:
            languages.append(meta.get('language', 'unknown'))
            authorities.append(meta.get('authority', 'unknown'))
            doc_types.append(meta.get('doc_type', 'unknown'))
            sources.append(meta.get('source', 'unknown'))
            chunk_indices.append(meta.get('chunk_index', 0))
        
        # Create LanceDB table data (list of dictionaries)
        table_data = []
        for i in range(len(documents)):
            table_data.append({
                'id': ids[i],
                'text': documents[i],
                'vector': embeddings[i].tolist(),  # LanceDB expects list format
                'language': languages[i],
                'authority': authorities[i],
                'doc_type': doc_types[i],
                'source': sources[i],
                'chunk_index': chunk_indices[i]
            })
        
        # Create LanceDB database and table
        logger.info("💾 Creating LanceDB table...")
        
        # Ensure output directory exists
        os.makedirs(lance_db_path, exist_ok=True)
        
        # Connect to LanceDB
        lance_db = lancedb.connect(lance_db_path)
        
        # Create table (this will overwrite if exists)
        lance_table = lance_db.create_table(lance_table_name, data=table_data, mode="overwrite")
        
        # Verify the conversion
        logger.info(" Verifying conversion...")
        lance_count = len(lance_table)
        
        logger.info(f"Original ChromaDB documents: {total_docs}")
        logger.info(f"Converted LanceDB documents: {lance_count}")
        
        if lance_count == total_docs:
            logger.info(" Conversion successful!")
            
            # Show sample data
            logger.info("📋 Sample converted data:")
            sample = lance_table.head(3).to_pandas()
            for i, row in sample.iterrows():
                logger.info(f"  Doc {i+1}: {row['language']} - {row['text'][:100]}...")
            
            return True
        else:
            logger.error(f" Conversion failed: count mismatch")
            return False
            
    except Exception as e:
        logger.error(f" Conversion failed: {e}", exc_info=True)
        return False

def convert_all_databases():
    """Convert all ChromaDB databases to LanceDB"""
    
    databases_to_convert = [
        {
            'name': 'Mixed Python + Flutter Database',
            'chroma_path': './rag_db_final',
            'chroma_collection': 'expert_py_flutter_dart_final',
            'lance_path': '../lancedb_data',
            'lance_table': 'expert_py_flutter_dart_final'
        },
        {
            'name': 'Flutter-Only Database',
            'chroma_path': './flutter_only_db',
            'chroma_collection': 'flutter_dart_knowledge',
            'lance_path': '../lancedb_data',
            'lance_table': 'flutter_dart_knowledge'
        }
    ]
    
    logger.info(" Starting bulk conversion of ChromaDB databases to LanceDB")
    
    for db_config in databases_to_convert:
        logger.info(f"\n{'='*60}")
        logger.info(f"Converting: {db_config['name']}")
        logger.info(f"{'='*60}")
        
        success = convert_chromadb_to_lancedb(
            chroma_db_path=db_config['chroma_path'],
            chroma_collection_name=db_config['chroma_collection'],
            lance_db_path=db_config['lance_path'],
            lance_table_name=db_config['lance_table']
        )
        
        if success:
            logger.info(f" {db_config['name']} converted successfully")
        else:
            logger.error(f" {db_config['name']} conversion failed")
    
    logger.info(f"\n🏁 Conversion process completed!")

def main():
    """Main conversion function"""
    
    print(" ChromaDB to LanceDB Converter")
    print("=" * 50)
    
    # Check if required packages are available
    try:
        import lancedb
        import pyarrow
        logger.info(" Required packages available")
    except ImportError as e:
        logger.error(f" Missing required package: {e}")
        logger.error("Install with: pip install lancedb pyarrow")
        return
    
    # Run conversion
    convert_all_databases()
    
    print("\n💡 Next steps:")
    print("1. Verify LanceDB data in ../lancedb_data/")
    print("2. Test the optimal_server.py with converted data")
    print("3. Keep your original ChromaDB as backup")

if __name__ == "__main__":
    main()