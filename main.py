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
        print(f"Pinging Ollama server at {OLLAMA_API_BASE}...")
        # Use a longer timeout for the initial connection check
        response = requests.get(OLLAMA_API_BASE, timeout=10) 
        response.raise_for_status() # Raises an exception for bad status codes (4xx or 5xx)
        print("✅ Ollama server is responding.")
    except requests.RequestException as e:
        print("\n❌ CRITICAL ERROR: Ollama server is not running or not reachable.")
        print(f"   Please ensure 'ollama serve' is active and accessible at {OLLAMA_API_BASE}.")
        print(f"   Error details: {e}")
        sys.exit(1) # Exit the script with an error code

    # Step 2: If the server is running, check if it has the required model
    try:
        print(f"Checking for required model: '{DEFAULT_MODEL}'...")
        tags_response = requests.get(f"{OLLAMA_API_BASE}/api/tags", timeout=15)
        tags_response.raise_for_status()
        
        models = tags_response.json().get("models", [])
        # Model names in Ollama can include the tag, e.g., 'qwen3:30b-a3b:latest'
        # We check if our required model name is a prefix of any available model.
        model_found = any(m.get("name", "").startswith(DEFAULT_MODEL) for m in models)

        if model_found:
            print(f"✅ Required model '{DEFAULT_MODEL}' is available.")
        else:
            available_models = [m.get("name") for m in models]
            print(f"\n❌ CRITICAL ERROR: Ollama server is running, but the required model '{DEFAULT_MODEL}' was not found.")
            print(f"   Please run 'ollama pull {DEFAULT_MODEL}' to download it.")
            print(f"   Available models: {available_models if available_models else 'None'}")
            sys.exit(1)

    except requests.RequestException as e:
        print(f"\n❌ CRITICAL ERROR: Could not get model list from Ollama server.")
        print(f"   Error details: {e}")
        sys.exit(1)
        
    print("--- Ollama Service OK ---")

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
    
    logger.info("MCP Server startup complete.")
    
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
