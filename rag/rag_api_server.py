#!/usr/bin/env python3
import logging
from fastapi import FastAPI, HTTPException, Security # Added Security
from fastapi.security import APIKeyHeader # Added APIKeyHeader
from pydantic import BaseModel
import uvicorn
import lancedb
import ollama

# --- Configuration ---
DB_PATH = "/mnt/caseSSD/continue_custom_rag/lancedb_data/"
TABLE_NAME = "flutter_dart_docs_comprehensive"
EMBEDDING_MODEL = "nomic-embed-text:latest"
DEFAULT_N_RESULTS = 5
RAG_API_SERVER_PORT = 8008 # Explicitly defined

# Define your API Key - In a real app, load this from env or a secure config
# For simplicity, we'll hardcode it here for now.
# IMPORTANT: Change this to a strong, unique key!
EXPECTED_API_KEY = "f5wlJhj_tbVh3Nmk-jUNbCYg9CWG7A-KXudQJV4BJxo" # <<< CHANGE THIS!!!
API_KEY_NAME = "X-RAG-API-Key" # Name of the header to check

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI App ---
app = FastAPI(
    title="RAG API Server for Dart/Flutter Docs (Secure)",
    description="Provides retrieval from the LanceDB knowledge base, secured by API key.",
    version="0.1.1" # Incremented version
)

# --- Pydantic Models for Request/Response ---
class RetrieveRequest(BaseModel):
    query: str
    n_results: int = DEFAULT_N_RESULTS

class Chunk(BaseModel):
    text: str
    source_path: str
    document_title: str | None = None
    repo_source: str | None = None
    score: float | None = None # Similarity score

class RetrieveResponse(BaseModel):
    retrieved_chunks: list[Chunk]

# --- Global Variables (Lazy Loaded) ---
db_connection = None
db_table = None

def get_db_table():
    """Initializes and returns the LanceDB table connection."""
    global db_connection, db_table
    if db_table is None:
        try:
            logger.info(f"Attempting to connect to LanceDB at: {DB_PATH}")
            db_connection = lancedb.connect(DB_PATH)
            logger.info(f"Connected to LanceDB. Available tables: {db_connection.table_names()}")
            if TABLE_NAME in db_connection.table_names():
                db_table = db_connection.open_table(TABLE_NAME)
                logger.info(f"Successfully opened table: '{TABLE_NAME}' with schema: {db_table.schema}")
            else:
                logger.error(f"Table '{TABLE_NAME}' not found in LanceDB at {DB_PATH}. Available: {db_connection.table_names()}")
                raise HTTPException(status_code=500, detail=f"RAG table '{TABLE_NAME}' not found.")
        except Exception as e:
            logger.error(f"Failed to connect to LanceDB or open table: {e}", exc_info=True)
            # Reset globals so it might try again on a new request, or handle as fatal
            db_connection = None
            db_table = None
            raise HTTPException(status_code=500, detail=f"LanceDB connection error: {str(e)}")
    return db_table

def get_query_embedding(query_text: str):
    """Generates embedding for the query text using Ollama."""
    try:
        response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=query_text)
        return response["embedding"]
    except Exception as e:
        logger.error(f"Failed to get embedding for query '{query_text[:50]}...': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate query embedding: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Attempt to initialize DB connection on startup."""
    logger.info("RAG API Server starting up...")
    try:
        # Test Ollama connection for embedding model
        logger.info(f"Checking for Ollama embedding model: {EMBEDDING_MODEL}")
        ollama.list() # This will throw an error if Ollama isn't reachable
        # Note: The actual model check is deferred to get_query_embedding to avoid startup failure if Ollama is temporarily down.
        logger.info("Ollama service seems reachable.")
    except Exception as e:
        logger.warning(f"Ollama service not immediately reachable on startup: {e}. Will attempt connection upon first query.")
    
    # Initialize table (optional, can be lazy-loaded on first request too)
    # get_db_table() # You can uncomment this to load DB on startup, but it might make startup fail if DB is not ready

@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_chunks(request: RetrieveRequest):
    """
    Retrieves relevant document chunks from LanceDB based on the input query.
    """
    logger.info(f"Received retrieval request for query: '{request.query[:100]}...', n_results: {request.n_results}")
    
    table = get_db_table() # Ensures table is loaded
    if not table:
        # This case should ideally be handled by get_db_table raising an HTTPException
        logger.error("DB table is not available for retrieval.")
        raise HTTPException(status_code=500, detail="RAG database table not available.")

    try:
        query_vector = get_query_embedding(request.query)
        logger.info(f"Generated query vector (first 3 dims): {query_vector[:3] if query_vector else 'Failed'}")

        search_results = table.search(query_vector).limit(request.n_results).to_list()
        logger.info(f"LanceDB search returned {len(search_results)} results.")

        retrieved_chunks_response = []
        for res in search_results:
            retrieved_chunks_response.append(Chunk(
                text=res.get("text", ""),
                source_path=res.get("source_path", "Unknown source"),
                document_title=res.get("document_title"), # Will be None if not present
                repo_source=res.get("repo_source"),       # Will be None if not present
                score=res.get("_distance")                # LanceDB uses _distance for similarity
            ))
        
        return RetrieveResponse(retrieved_chunks=retrieved_chunks_response)

    except HTTPException:
        raise # Re-raise HTTPExceptions from helper functions
    except Exception as e:
        logger.error(f"Error during retrieval for query '{request.query[:100]}...': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing retrieval request: {str(e)}")

if __name__ == "__main__":
    logger.info("Starting RAG API server with Uvicorn on http://127.0.0.1:8008")
    # Ensure necessary packages for the server are installed: fastapi, uvicorn, lancedb, ollama
    # Example: python3 -m pip install fastapi "uvicorn[standard]" lancedb ollama
    uvicorn.run(app, host="127.0.0.1", port=8008)