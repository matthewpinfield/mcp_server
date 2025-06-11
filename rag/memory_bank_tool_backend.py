#!/usr/bin/env python3
import logging
import chromadb
from chromadb.utils import embedding_functions # For Ollama integration with ChromaDB
import uuid # For generating unique IDs for memory entries
import datetime
import time # For the example usage block

# --- Configuration ---
MEMORY_DB_PATH = "/mnt/caseSSD/mcp_server_data/vector_db/" # Your ChromaDB path
MEMORY_COLLECTION_NAME = "knowledge_base" # Your collection name for memories

# Embedding model for ChromaDB's OllamaEmbeddingFunction
# This should be the same model used if you want semantic search over memories
# to be consistent with other embeddings (like your RAG system).
EMBEDDING_MODEL_NAME_OLLAMA = "nomic-embed-text:latest" 
OLLAMA_BASE_URL = "http://127.0.0.1:11434" # Default Ollama URL

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MemoryBankBackend")
logging.getLogger("chromadb").setLevel(logging.WARNING) # ChromaDB can be verbose

# --- ChromaDB Client and Collection (Lazy Loaded) ---
persistent_client = None
memory_collection = None
ollama_ef = None # Ollama Embedding Function instance

def get_memory_collection():
    """
    Initializes and returns the ChromaDB collection for memories.
    Handles creation of the collection if it doesn't exist.
    Initializes the Ollama embedding function for ChromaDB.
    """
    global persistent_client, memory_collection, ollama_ef
    if memory_collection is None:
        try:
            logger.info(f"Attempting to initialize ChromaDB client at path: {MEMORY_DB_PATH}")
            persistent_client = chromadb.PersistentClient(path=MEMORY_DB_PATH)
            logger.info(f"ChromaDB client initialized. Existing collections: {persistent_client.list_collections()}")

            if ollama_ef is None:
                logger.info(f"Initializing OllamaEmbeddingFunction with model '{EMBEDDING_MODEL_NAME_OLLAMA}' and URL '{OLLAMA_BASE_URL}'")
                # Ensure your Ollama server is running and has the EMBEDDING_MODEL_NAME_OLLAMA
                # This might make an initial call to Ollama, so it needs to be available.
                ollama_ef = embedding_functions.OllamaEmbeddingFunction(
                    model_name=EMBEDDING_MODEL_NAME_OLLAMA,
                    url=OLLAMA_BASE_URL,
                )
                logger.info("OllamaEmbeddingFunction initialized.")

            logger.info(f"Getting or creating ChromaDB collection: '{MEMORY_COLLECTION_NAME}'")
            memory_collection = persistent_client.get_or_create_collection(
                name=MEMORY_COLLECTION_NAME,
                embedding_function=ollama_ef # Pass the embedding function instance
            )
            logger.info(f"Successfully connected to/created ChromaDB collection '{MEMORY_COLLECTION_NAME}'. Current count: {memory_collection.count()}")
        
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB or get/create collection '{MEMORY_COLLECTION_NAME}': {e}", exc_info=True)
            # Reset globals on failure to allow re-try or indicate failure
            persistent_client = None
            memory_collection = None
            ollama_ef = None
            raise # Re-raise the exception so the caller knows initialization failed
            
    return memory_collection

def add_memory_entry(text_content: str, metadata: dict = None) -> str | None:
    """
    Adds a new memory entry to the ChromaDB collection.
    The text_content will be automatically embedded by ChromaDB using the collection's embedding function.
    """
    try:
        collection = get_memory_collection() # Ensures collection is initialized
        if not collection:
            logger.error("Memory collection not available. Cannot add memory entry.")
            return None

        entry_id = str(uuid.uuid4())
        doc_metadata = metadata if metadata is not None else {}
        # Ensure basic metadata is present
        doc_metadata.setdefault("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat())
        doc_metadata.setdefault("source", "unknown") # e.g., "user_query_summary", "llm_response_summary", "manual_note"
        
        collection.add(
            documents=[text_content],
            metadatas=[doc_metadata],
            ids=[entry_id]
        )
        logger.info(f"Added memory entry with ID: {entry_id}, source: '{doc_metadata['source']}', text: '{text_content[:60]}...'")
        return entry_id
    except Exception as e:
        logger.error(f"Failed to add memory entry: {e}", exc_info=True)
        return None

def retrieve_relevant_memory_entries(query_text: str, n_results: int = 3, filter_metadata: dict = None) -> list[dict]:
    """
    Retrieves relevant memory entries from ChromaDB based on semantic similarity to the query_text.
    The query_text will be automatically embedded by ChromaDB using the collection's embedding function.
    """
    results_list = []
    try:
        collection = get_memory_collection() # Ensures collection is initialized
        if not collection:
            logger.error("Memory collection not available. Cannot retrieve memories.")
            return []

        # query_embeddings can be explicitly provided if pre-computed, 
        # but if query_texts is used, the collection's embedding_function handles it.
        query_results = collection.query(
            query_texts=[query_text], # Text(s) to find similar documents for
            n_results=min(n_results, collection.count()) if collection.count() > 0 else n_results, # Avoid error if n_results > count
            where=filter_metadata # Optional: filter by metadata, e.g., {"source": "user_decision"}
            # include=['metadatas', 'documents', 'distances'] # Specify what to return
        )
        
        # Process results if any are found
        # ChromaDB query_results structure:
        # {'ids': [[]], 'distances': [[]], 'metadatas': [[]], 'documents': [[]], 'uris': None, 'data': None}
        # Each inner list corresponds to a query_text (we only have one query_text here)
        if query_results and query_results.get("documents") and query_results["documents"][0] is not None:
            num_retrieved = len(query_results["documents"][0])
            for i in range(num_retrieved):
                entry = {
                    "id": query_results["ids"][0][i],
                    "text": query_results["documents"][0][i],
                    "metadata": query_results["metadatas"][0][i] if query_results.get("metadatas") and query_results["metadatas"][0] else {},
                    "distance": query_results["distances"][0][i] if query_results.get("distances") and query_results["distances"][0] else None,
                }
                results_list.append(entry)
            logger.info(f"Retrieved {len(results_list)} relevant memories for query: '{query_text[:60]}...'")
        else:
            logger.info(f"No relevant memories found or empty result for query: '{query_text[:60]}...'")
            
    except Exception as e:
        logger.error(f"Failed to retrieve memory entries: {e}", exc_info=True)
    return results_list

# Example usage block for direct testing of this script
if __name__ == "__main__":
    logger.info("--- Testing Memory Bank Backend Directly ---")
    # This test assumes Ollama server is running with the nomic-embed-text model.
    
    # Test 1: Initialize collection (should happen on first call)
    print("\n[Test 1: Initializing memory collection...]")
    try:
        col = get_memory_collection()
        if col:
            print(f"Collection '{col.name}' initialized/accessed. Current count: {col.count()}")
        else:
            print("Failed to initialize collection for Test 1.")
            exit() # Stop test if collection fails
    except Exception as e:
        print(f"Error initializing collection in Test 1: {e}")
        exit()

    # Test 2: Adding some memory entries
    print("\n[Test 2: Adding memory entries...]")
    memory_id1 = add_memory_entry("User prefers Python for scripting tasks.", {"source": "user_preference", "project": "general"})
    memory_id2 = add_memory_entry("The RAG API server is running on port 8008.", {"source": "system_fact", "service": "rag_api"})
    memory_id3 = add_memory_entry("Project 'Alpha' requires Dart and Flutter for the mobile app.", {"source": "project_requirement", "project": "Alpha"})
    
    if memory_id1: print(f"Added memory 1: {memory_id1}")
    if memory_id2: print(f"Added memory 2: {memory_id2}")
    if memory_id3: print(f"Added memory 3: {memory_id3}")

    time.sleep(1) # Give ChromaDB a moment to process additions if there's any async behavior
    print(f"Collection count after additions: {col.count() if col else 'N/A'}")

    # Test 3: Retrieving relevant memories
    print("\n[Test 3: Retrieving memories for 'Python scripting'...]")
    retrieved_for_python = retrieve_relevant_memory_entries("Tell me about Python scripting preferences", n_results=2)
    if retrieved_for_python:
        for mem in retrieved_for_python:
            print(f"  Retrieved: ID={mem['id']}, Dist={mem.get('distance', -1.0):.4f}, Text='{mem['text'][:50]}...', Meta={mem['metadata']}")
    else:
        print("  No memories found for 'Python scripting'.")

    print("\n[Test 4: Retrieving memories for 'Project Alpha mobile app'...]")
    retrieved_for_alpha = retrieve_relevant_memory_entries("What are the tech requirements for Alpha's mobile app?", n_results=2)
    if retrieved_for_alpha:
        for mem in retrieved_for_alpha:
            print(f"  Retrieved: ID={mem['id']}, Dist={mem.get('distance', -1.0):.4f}, Text='{mem['text'][:50]}...', Meta={mem['metadata']}")
    else:
        print("  No memories found for 'Project Alpha mobile app'.")

    # Test 5: Retrieving with metadata filter (if ChromaDB and EF support it well)
    # Note: Metadata filtering capabilities can vary based on ChromaDB version and setup.
    # This is a more advanced query.
    print("\n[Test 5: Retrieving memories for 'port 8008' with source 'system_fact'...]")
    # Note: ChromaDB's `where` filter syntax can be specific.
    # Simple equality filter:
    retrieved_with_filter = retrieve_relevant_memory_entries(
        "What runs on port 8008?", 
        n_results=2, 
        filter_metadata={"source": "system_fact"} # Example filter
    )
    if retrieved_with_filter:
        for mem in retrieved_with_filter:
            print(f"  Retrieved (filtered): ID={mem['id']}, Dist={mem.get('distance', -1.0):.4f}, Text='{mem['text'][:50]}...', Meta={mem['metadata']}")
    else:
        print("  No memories found for 'port 8008' with the specified filter, or filter not effective.")
    
    logger.info("--- Memory Bank Backend Test Finished ---")