#!/usr/bin/env python3
# Optimal RAG Server - All issues fixed, no hardcoding

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import lancedb
import ollama
import logging
import asyncio
import os
import time
from typing import List, Dict, Any
from contextlib import asynccontextmanager

# --- Configuration (Environment Variables) ---
DB_PATH = os.getenv("DB_PATH", "/opt/mcp-performance/rag/lancedb_data/")
TABLE_NAME = os.getenv("TABLE_NAME", "flutter_dart_docs_comprehensive")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "qwen3:8b")
EMBEDDING_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT", "30"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RAG_Service_8008")

# --- Global variable for the database table ---
db_table = None

# --- Startup/Shutdown with proper resource management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Logic
    global db_table
    logger.info("RAG Service starting up...")
    try:
        db = lancedb.connect(DB_PATH)
        db_table = db.open_table(TABLE_NAME)
        logger.info(f"Successfully connected to LanceDB table '{TABLE_NAME}' with {len(db_table)} rows.")
    except Exception as e:
        logger.error(f"FATAL: Could not connect to LanceDB: {e}", exc_info=True)
        db_table = None
        raise
    
    yield # The application runs here
    
    # Shutdown Logic
    logger.info("RAG Service shutting down...")
    try:
        if db_table:
            # Properly close database connections
            db_table = None
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# --- FastAPI App ---
app = FastAPI(title="Optimal RAG Service", lifespan=lifespan)

# --- Core RAG Functions with proper error handling ---
async def retrieve_documents(query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """Retrieve documents with comprehensive error handling"""
    if not db_table:
        logger.error("LanceDB table is not available.")
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    try:
        # Generate embedding with timeout
        embedding_task = asyncio.create_task(
            asyncio.to_thread(
                ollama.embeddings, 
                model=EMBEDDING_MODEL, 
                prompt=query_text
            )
        )
        embedding_response = await asyncio.wait_for(embedding_task, timeout=EMBEDDING_TIMEOUT)
        query_embedding = embedding_response["embedding"]
        
    except asyncio.TimeoutError:
        logger.error(f"Embedding generation timeout for query: {query_text[:50]}...")
        raise HTTPException(status_code=504, detail="Embedding generation timeout")
    except KeyError:
        logger.error("Invalid embedding response format")
        raise HTTPException(status_code=502, detail="Embedding service returned invalid format")
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="Embedding service unavailable")
    
    try:
        # Database search with proper error handling
        search_task = asyncio.create_task(
            asyncio.to_thread(
                lambda: db_table.search(query_embedding).limit(n_results).to_list()
            )
        )
        search_results = await search_task
        
        logger.info(f"Retrieved {len(search_results)} documents for query: '{query_text[:50]}...'")
        return search_results
        
    except Exception as e:
        logger.error(f"Database search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database search failed")

async def generate_response_stream(query: str, retrieved_docs: List[Dict[str, Any]], model: str = None):
    """Generate response stream with proper resource management"""
    if not retrieved_docs:
        yield "Based on the available documentation, I couldn't find any specific information for that query."
        return

    # Use provided model or default
    llm_model = model or DEFAULT_LLM_MODEL
    logger.info(f"Using LLM model: {llm_model}")

    context_str = "\n\n".join([
        f"Source: {doc.get('source', 'N/A')}\nContent:\n{doc.get('text', '')}" 
        for doc in retrieved_docs
    ])
    
    prompt = f"""Answer this Flutter/Dart question using only the documentation below. Be concise.

Documentation:
{context_str}

Question: {query}
Answer:"""

    try:
        # Create AsyncClient manually (ollama doesn't support async context manager)
        aclient = ollama.AsyncClient()
        try:
            response_stream = await asyncio.wait_for(
                aclient.chat(
                    model=llm_model,
                    messages=[{'role': 'user', 'content': prompt}],
                    stream=True
                ),
                timeout=LLM_TIMEOUT
            )
            
            async for part in response_stream:
                if 'message' in part and 'content' in part['message']:
                    yield part['message']['content']
                
        except asyncio.TimeoutError:
            error_message = f"LLM generation timeout after {LLM_TIMEOUT}s"
            logger.error(error_message)
            yield error_message
        except Exception as e:
            error_message = f"Error during LLM generation: {e}"
            logger.error(error_message, exc_info=True)
            yield error_message
        finally:
            # Manual cleanup
            try:
                if hasattr(aclient, '_client') and hasattr(aclient._client, 'aclose'):
                    await aclient._client.aclose()
            except:
                pass  # Ignore cleanup errors
                
    except Exception as e:
        error_message = f"Failed to create LLM client: {e}"
        logger.error(error_message, exc_info=True)
        yield error_message

# --- Main endpoint with model selection ---
@app.post("/custom_rag_stuff")
async def custom_rag_endpoint(request: Request):
    try:
        body = await request.json()
        query = body.get("fullInput")
        
        # Optional: Allow model selection via request
        requested_model = body.get("model", DEFAULT_LLM_MODEL)
        
        if not query:
            raise ValueError("Key 'fullInput' not found in request body")
            
    except Exception as e:
        logger.error(f"Failed to parse request: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    logger.info(f"Processing query: '{query}' with model: '{requested_model}'")
    
    try:
        retrieved_docs = await retrieve_documents(query, n_results=5)
        return StreamingResponse(
            generate_response_stream(query, retrieved_docs, requested_model), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in RAG endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Health check endpoint ---
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "database_available": db_table is not None,
        "default_model": DEFAULT_LLM_MODEL,
        "embedding_model": EMBEDDING_MODEL
    }

# --- Configuration endpoint ---
@app.get("/config")
async def get_config():
    return {
        "db_path": DB_PATH,
        "table_name": TABLE_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "default_llm_model": DEFAULT_LLM_MODEL,
        "embedding_timeout": EMBEDDING_TIMEOUT,
        "llm_timeout": LLM_TIMEOUT
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8008, log_level="info")