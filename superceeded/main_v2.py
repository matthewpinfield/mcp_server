#!/usr/bin/env python3
"""
Main entry point for MCP Server - Version 2
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
from api.chat_v2 import router as chat_router

# Global executor for async tool operations
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_ollama_service():
    """Check if Ollama service is running and has the default model"""
    try:
        # Check if Ollama API is responding
        response = requests.get(f"{OLLAMA_API_BASE}/api/tags", timeout=5)
        if response.status_code != 200:
            logger.error(f"❌ Ollama API not responding at {OLLAMA_API_BASE}")
            return False
        
        # Check if the default model is available
        models_data = response.json()
        available_models = [model['name'] for model in models_data.get('models', [])]
        
        if DEFAULT_MODEL not in available_models:
            logger.error(f"❌ Default model '{DEFAULT_MODEL}' not found in Ollama")
            logger.info(f"Available models: {available_models}")
            return False
        
        logger.info(f"✅ Ollama service ready with model '{DEFAULT_MODEL}'")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to connect to Ollama at {OLLAMA_API_BASE}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error checking Ollama service: {e}")
        return False

async def check_rag_service():
    """Check if RAG service is running"""
    try:
        rag_url = "http://localhost:8008/search/docs"
        response = requests.get(f"{rag_url.replace('/search/docs', '')}/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ RAG service is running")
            return True
        else:
            logger.warning(f"⚠️ RAG service health check failed (status: {response.status_code})")
            return False
    except requests.exceptions.RequestException:
        logger.warning("⚠️ RAG service not available - will continue without RAG")
        return False
    except Exception as e:
        logger.warning(f"⚠️ RAG service check error: {e}")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    # Startup
    logger.info("🚀 Starting MCP Server v2...")
    
    # Check Ollama dependency (required)
    if not await check_ollama_service():
        logger.error("❌ Ollama service check failed - this is required for operation")
        sys.exit(1)
    
    # Check RAG dependency (optional)
    await check_rag_service()
    
    logger.info(f"🎯 MCP Server v2 ready on {MCP_SERVER_HOST}:{MCP_SERVER_PORT}")
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down MCP Server v2...")
    executor.shutdown(wait=True)

# Create FastAPI app
app = FastAPI(
    title="Advanced MCP Server v2",
    description="Model Context Protocol Server with intelligent agent capabilities - Simplified Version",
    version="2.0.0",
    lifespan=lifespan
)

# Include API routes
app.include_router(chat_router)

@app.get("/")
async def root():
    """Root endpoint with server info"""
    return {
        "name": "Advanced MCP Server v2",
        "version": "2.0.0",
        "status": "operational",
        "model": DEFAULT_MODEL,
        "endpoints": {
            "chat": "/api/chat",
            "openai_compatible": "/v1/chat/completions",
            "models": "/v1/models"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Basic health check - could be enhanced with dependency checks
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "version": "2.0.0"}
    )

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the server
    try:
        uvicorn.run(
            "main_v2:app",  # Updated to use main_v2
            host=MCP_SERVER_HOST,
            port=MCP_SERVER_PORT,
            reload=False,  # Disable reload for production
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)