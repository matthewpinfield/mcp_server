#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions
import os

def investigate_test_database():
    """Investigate what's in the test_rag_db"""
    
    db_path = "./test_rag_db"
    
    print(f"🔍 Investigating {db_path}")
    
    if not os.path.exists(db_path):
        print(" Database path does not exist")
        return
    
    try:
        # Connect without specifying collection name first
        client = chromadb.PersistentClient(path=db_path)
        
        # List all collections
        collections = client.list_collections()
        print(f"Found {len(collections)} collections:")
        
        for i, collection in enumerate(collections):
            print(f"\n{'='*50}")
            print(f"Collection {i+1}: {collection.name}")
            print(f"{'='*50}")
            
            try:
                # Get the collection
                coll = client.get_collection(
                    name=collection.name,
                    embedding_function=embedding_functions.OllamaEmbeddingFunction(
                        model_name="nomic-embed-text:latest",
                        url="http://127.0.0.1:11434"
                    )
                )
                
                # Get basic stats
                count = coll.count()
                print(f"Total chunks: {count}")
                
                if count > 0:
                    # Get a sample of data
                    sample_size = min(10, count)
                    results = coll.get(limit=sample_size)
                    
                    # Analyze sample
                    if results['metadatas']:
                        print(f"\nSample metadata analysis (first {len(results['metadatas'])} items):")
                        
                        # Check what metadata fields exist
                        sample_meta = results['metadatas'][0]
                        print(f"Metadata fields: {list(sample_meta.keys())}")
                        
                        # Show language distribution in sample
                        languages = {}
                        authorities = {}
                        doc_types = {}
                        
                        for meta in results['metadatas']:
                            lang = meta.get('language', 'MISSING')
                            auth = meta.get('authority', 'MISSING')
                            doc_type = meta.get('doc_type', 'MISSING')
                            
                            languages[lang] = languages.get(lang, 0) + 1
                            authorities[auth] = authorities.get(auth, 0) + 1
                            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                        
                        print(f"Sample languages: {languages}")
                        print(f"Sample authorities: {authorities}")
                        print(f"Sample doc types: {doc_types}")
                        
                        # Show a few sample documents
                        print(f"\nSample documents:")
                        for i, doc in enumerate(results['documents'][:3]):
                            print(f"\nDoc {i+1} ({len(doc)} chars):")
                            print(f"Preview: {doc[:200]}...")
                            if results['metadatas'][i].get('source'):
                                print(f"Source: {results['metadatas'][i]['source'][:80]}...")
                
                # Suggest what we can do with this collection
                print(f"\n💡 Possible actions for '{collection.name}':")
                
                if count == 0:
                    print("  • Delete empty collection")
                    print("  • Use for new test data")
                elif count < 100:
                    print("  • Use for small-scale experiments")
                    print("  • Clear and reuse for new tests")
                    print("  • Compare with main databases")
                elif count < 1000:
                    print("  • Use for medium-scale testing")
                    print("  • Evaluate against main databases")
                    print("  • Use as development environment")
                else:
                    print("  • Treat as production alternative")
                    print("  • Full evaluation needed")
                    print("  • Consider merging with main database")
                
            except Exception as e:
                print(f" Error accessing collection '{collection.name}': {e}")
        
        if not collections:
            print("No collections found in this database.")
            print("\n💡 This empty database could be used for:")
            print("  • Testing new ingestion scripts")
            print("  • Experimenting with different embedding models")
            print("  • Creating specialized datasets")
            print("  • Development and debugging")
        
    except Exception as e:
        print(f" Error investigating database: {e}")

def suggest_test_db_usage():
    """Suggest practical uses for the test database"""
    
    print(f"\n PRACTICAL USES FOR TEST DATABASE")
    print(f"{'='*60}")
    
    print(f"\n🧪 DEVELOPMENT & TESTING:")
    print(f"  • Test new ingestion scripts before running on main DB")
    print(f"  • Experiment with different chunking strategies") 
    print(f"  • Test different embedding models")
    print(f"  • Debug query performance issues")
    
    print(f"\n📊 EVALUATION & BENCHMARKING:")
    print(f"  • Create gold standard test sets")
    print(f"  • A/B test different database configurations")
    print(f"  • Measure query latency and accuracy")
    print(f"  • Test edge cases and error handling")
    
    print(f"\n🔬 SPECIALIZED EXPERIMENTS:")
    print(f"  • Test domain-specific knowledge (e.g., only UI/UX code)")
    print(f"  • Experiment with multilingual content")
    print(f"  • Test different authority weighting schemes")
    print(f"  • Create minimal datasets for specific use cases")
    
    print(f"\n PRODUCTION PREPARATION:")
    print(f"  • Staging environment for database changes")
    print(f"  • Test backup and restore procedures")
    print(f"  • Validate migration scripts")
    print(f"  • Load testing with synthetic data")

if __name__ == "__main__":
    investigate_test_database()
    suggest_test_db_usage()