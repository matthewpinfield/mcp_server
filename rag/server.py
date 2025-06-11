#!/usr/bin/env python3
# /mnt/caseSSD/continue_custom_rag/server.py (Final Recommended Version)

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import lancedb
import ollama
import logging
import asyncio
from typing import List
from contextlib import asynccontextmanager

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RAG_Service_8008")

DB_PATH = "/mnt/caseSSD/continue_custom_rag/lancedb_data/"
TABLE_NAME = "flutter_dart_docs_comprehensive"
EMBEDDING_MODEL_FOR_QUERY = "nomic-embed-text:latest"
LLM_MODEL_FOR_SYNTHESIS = "mistral:7b"

# --- Global variable for the database table ---
db_table = None

# --- BEST OF BOTH: Using the modern 'lifespan' manager for startup/shutdown ---
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
    
    yield # The application runs here
    
    # Shutdown Logic
    logger.info("RAG Service shutting down.")


# --- FastAPI App Initialization with the new lifespan manager ---
app = FastAPI(title="Standalone RAG Service", lifespan=lifespan)


# --- Core RAG Functions ---
async def retrieve_documents(query_text: str, n_results: int = 5) -> List[dict]:
    if not db_table:
        logger.error("LanceDB table is not available.")
        return []
    try:
        query_embedding = ollama.embeddings(model=EMBEDDING_MODEL_FOR_QUERY, prompt=query_text)["embedding"]
        search_results = db_table.search(query_embedding).limit(n_results).to_list()
        logger.info(f"Retrieved {len(search_results)} documents for query: '{query_text[:50]}...'")
        return search_results
    except Exception as e:
        logger.error(f"Error during document retrieval: {e}", exc_info=True)
        return []

# --- BEST OF BOTH: Using the safer manual client management ---
async def generate_response_stream(query: str, retrieved_docs: List[dict]):
    if not retrieved_docs:
        yield "Based on the available documentation, I couldn't find any specific information for that query."
        return

    context_str = "\n\n".join([f"Source: {doc.get('source', 'N/A')}\nContent:\n{doc.get('text', '')}" for doc in retrieved_docs])
    prompt = f"""You are an expert Flutter/Dart AI assistant. Use the following documentation to answer the user's query. Base your answer only on the provided documentation.

Retrieved Documentation:
---
{context_str}
---

User Query: {query}

Answer:"""

    aclient = None
    try:
        aclient = ollama.AsyncClient()
        response_stream = await aclient.chat(
            model=LLM_MODEL_FOR_SYNTHESIS,
            messages=[{'role': 'user', 'content': prompt}],
            stream=True
        )
        async for part in response_stream:
            yield part['message']['content']
    except Exception as e:
        error_message = f"Error during LLM generation: {e}"
        logger.error(error_message, exc_info=True)
        yield error_message
    finally:
        if aclient and hasattr(aclient, '_client') and hasattr(aclient._client, 'aclose'):
             if asyncio.iscoroutinefunction(aclient._client.aclose):
                await aclient._client.aclose()


@app.post("/custom_rag_stuff")
async def custom_rag_endpoint(request: Request):
    try:
        body = await request.json()
        query = body.get("fullInput")
        if not query:
            raise ValueError("Key 'fullInput' not found in request body")
    except Exception as e:
        logger.error(f"Failed to parse request: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    logger.info(f"Processing query: '{query}'")
    retrieved_docs = await retrieve_documents(query, n_results=5)
    return StreamingResponse(generate_response_stream(query, retrieved_docs), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8008, log_level="info")