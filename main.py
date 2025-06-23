#!/usr/bin/env python3
"""
Main entry point for MCP Server
Contains the FastAPI app instance, dependency checks, and Uvicorn startup
"""

import uvicorn
import asyncio
import signal
import sys
import logging
import requests # Added for dependency checks
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Import all necessary configuration from config.py
from config import (
    MCP_SERVER_HOST, 
    MCP_SERVER_PORT, 
    LOG_LEVEL,
    MAX_WORKERS,
    OLLAMA_API_BASE,
    DEFAULT_MODEL
)
from api.chat import router as chat_router

# Global executor for async tool operations
executor = None

def check_ollama_status():
    """
    Verifies that the Ollama server is running and has the required model.
    Exits the application if checks fail.
    """
    print("--- Verifying Ollama Service ---")

    # Step 1: Check if the Ollama server is running at all
    try:
        response = requests.get(OLLAMA_API_BASE, timeout=10) 
        response.raise_for_status() # Raises an exception for bad status codes (4xx or 5xx)
        print("[ OK ] Ollama server responding")
    except requests.RequestException as e:
        print("[FAIL] Ollama server not reachable")
        print(f"       Please ensure 'ollama serve' is active at {OLLAMA_API_BASE}")
        sys.exit(1)

    # Step 2: If the server is running, check if it has the required model
    try:
        tags_response = requests.get(f"{OLLAMA_API_BASE}/api/tags", timeout=15)
        tags_response.raise_for_status()
        
        models = tags_response.json().get("models", [])
        model_found = any(m.get("name", "").startswith(DEFAULT_MODEL) for m in models)

        if model_found:
            print(f"[ OK ] Model '{DEFAULT_MODEL}' available")
        else:
            available_models = [m.get("name") for m in models]
            print(f"[FAIL] Model '{DEFAULT_MODEL}' not found")
            print(f"       Please run 'ollama pull {DEFAULT_MODEL}' to download it")
            sys.exit(1)

    except requests.RequestException as e:
        print("[FAIL] Could not get model list from Ollama server")
        sys.exit(1)
        
    print("[ OK ] Ollama Service Ready")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global executor
    
    # Startup
    logging.basicConfig(
        level=LOG_LEVEL, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Initialize ThreadPoolExecutor for tool operations
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    logger.info(f"Started ThreadPoolExecutor with {MAX_WORKERS} workers")
    
    # Check RAG system status
    try:
        import requests
        rag_response = requests.get("http://localhost:8008/health", timeout=5)
        if rag_response.status_code == 200:
            logger.info("--- RAG System ---")
            logger.info("[ OK ] Dual endpoint server accessible")
        else:
            logger.warning("[WARN] RAG system not responding")
    except Exception as e:
        logger.warning(f"[FAIL] RAG system check failed: {e}")
    
    # Check memory system status  
    try:
        from tools.knowledge import mcp_get_memory_stats
        memory_stats = mcp_get_memory_stats()
        if memory_stats.get('status') == 'success':
            stats = memory_stats['stats']
            logger.info("--- Memory System ---")
            logger.info(f"[ OK ] Tier 1 Redis: {stats.get('redis_status', 'unknown')} ({stats.get('redis_keys', 0)} keys) | Tier 2 MongoDB: {stats.get('mongodb_status', 'unknown')} ({stats.get('mongodb_rules', 0)} rules) | Tier 3 ChromaDB: {stats.get('chromadb_status', 'unknown')} ({stats.get('chromadb_documents', 0)} docs)")
        else:
            logger.warning(f"[WARN] Memory system check failed: {memory_stats.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to check memory system status: {e}")
    
    logger.info("--- MCP Server startup complete ---")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MCP Server...")
    if executor:
        executor.shutdown(wait=True)
    logger.info("Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Orchestrated Toolkit with Memory Integration",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(chat_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "MCP Server",
        "version": "1.0.0"
    })

def main():
    """Main entry point"""
    # Run the check at the very beginning of the script
    check_ollama_status()
    
    uvicorn.run(
        "main:app",
        host=MCP_SERVER_HOST,
        port=MCP_SERVER_PORT,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
