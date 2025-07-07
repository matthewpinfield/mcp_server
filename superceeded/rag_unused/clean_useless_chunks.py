#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions

def clean_useless_chunks():
    """Remove the 7 truly useless chunks from the database"""
    
    DATABASE_CONFIG = {
        "path": "./rag_db_final",
        "collection_name": "expert_py_flutter_dart_final",
        "embedding_model": "nomic-embed-text:latest"
    }
    OLLAMA_CONFIG = {"base_url": "http://127.0.0.1:11434"}
    
    print(f"\n=== Cleaning Useless Chunks ===")
    
    try:
        # Connect to database
        client = chromadb.PersistentClient(path=DATABASE_CONFIG["path"])
        collection = client.get_collection(
            name=DATABASE_CONFIG["collection_name"],
            embedding_function=embedding_functions.OllamaEmbeddingFunction(
                model_name=DATABASE_CONFIG["embedding_model"], 
                url=OLLAMA_CONFIG["base_url"]
            )
        )
        
        # Get current count
        initial_count = collection.count()
        print(f"Initial chunk count: {initial_count}")
        
        # Get all data
        results = collection.get()
        documents = results['documents']
        metadatas = results['metadatas'] 
        ids = results['ids']
        
        # Identify truly useless chunks
        useless_ids = []
        useless_chunks = []
        
        for i, doc in enumerate(documents):
            if len(doc) < 50:  # Only check short chunks
                text = doc.strip()
                
                # Define truly useless patterns
                is_useless = False
                reason = ""
                
                if not text:
                    is_useless = True
                    reason = "empty after strip"
                elif text in ['{', '}', '(', ')', '[', ']', ';', ':', ',']:
                    is_useless = True
                    reason = "single bracket/punctuation"
                elif len(text.split()) <= 2 and not any(keyword in text.lower() for keyword in ['import', 'from', 'class', 'def', 'return']):
                    # Only 1-2 words and not containing code keywords
                    if not text.startswith('//') and not text.startswith('#'):  # Keep short comments for now
                        is_useless = True
                        reason = "1-2 meaningless words"
                
                if is_useless:
                    useless_ids.append(ids[i])
                    useless_chunks.append({
                        'id': ids[i],
                        'text': repr(doc),  # Use repr to show whitespace
                        'length': len(doc),
                        'reason': reason,
                        'source': metadatas[i].get('source', 'N/A')[:60] + '...'
                    })
        
        print(f"\nFound {len(useless_ids)} truly useless chunks:")
        
        # Show what we're about to delete
        for chunk in useless_chunks:
            print(f"  ID: {chunk['id']}")
            print(f"  Text: {chunk['text']}")
            print(f"  Length: {chunk['length']}")
            print(f"  Reason: {chunk['reason']}")
            print(f"  Source: {chunk['source']}")
            print()
        
        if useless_ids:
            # Auto-delete truly useless chunks (they're clearly not valuable)
            print(f"Auto-deleting {len(useless_ids)} truly useless chunks...")
            
            if True:  # Always proceed with deletion
                # Delete the useless chunks
                collection.delete(ids=useless_ids)
                
                # Force persistence
                if hasattr(client, 'persist'):
                    client.persist()
                
                # Verify deletion
                final_count = collection.count()
                deleted_count = initial_count - final_count
                
                print(f"\n Successfully deleted {deleted_count} chunks")
                print(f"Final chunk count: {final_count}")
                print(f"Database quality improved: {(final_count/initial_count)*100:.3f}% of original size")
                
                # Calculate new quality score
                quality_improvement = (deleted_count / initial_count) * 100
                print(f"Quality improvement: +{quality_improvement:.3f}%")
                
                return {
                    'deleted': deleted_count,
                    'final_count': final_count,
                    'quality_improvement': quality_improvement
                }
            else:
                print("Deletion cancelled.")
                return None
        else:
            print("No truly useless chunks found to delete.")
            return {'deleted': 0, 'final_count': initial_count}
        
    except Exception as e:
        print(f" Error cleaning chunks: {e}")
        return None

if __name__ == "__main__":
    result = clean_useless_chunks()
    if result:
        print(f"\n Database cleaning completed.")
    else:
        print(f"\n Database cleaning failed or cancelled.")