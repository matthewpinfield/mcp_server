#!/usr/bin/env python3
"""
Main entry point for MCP Server
Contains the FastAPI app instance, dependency checks, and Uvicorn startup
"""

import os
# Suppress specific LanceDB nprobes warnings BEFORE any imports
os.environ["RUST_LOG"] = "lance::dataset::scanner=error"

import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import requests  # Added for dependency checks
import uvicorn
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.chat import router as chat_router

# Import all necessary configuration from config.py
from config import (
    DEFAULT_MODEL,
    LOG_LEVEL,
    MAX_WORKERS,
    MCP_SERVER_HOST,
    MCP_SERVER_PORT,
    OLLAMA_API_BASE,
)

# Global executor for async tool operations
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


# Configure logging with color coding
class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to different MCP phases"""

    COLORS = {
        "api.chat": "\033[94m",  # Blue for API
        "core.orchestrator": "\033[95m",  # Purple for Agent
        "tools.web": "\033[93m",  # Yellow for Web Search
        "tools.rag": "\033[92m",  # Green for RAG Tools
        "tools.sandbox": "\033[91m",  # Red for Sandbox
        "tools.git": "\033[96m",  # Cyan for Git
        "tools.github": "\033[97m",  # White for GitHub
        "tools.development": "\033[90m",  # Gray for Development tools
        "tools.code_analysis": "\033[35m",  # Magenta for Code Analysis
    }

    RESET = "\033[0m"

    def format(self, record):
        # Get color for this logger
        color = self.COLORS.get(record.name, "")

        # Format the message
        formatted = super().format(record)

        # Add color if available
        if color:
            return f"{color}{formatted}{self.RESET}"
        return formatted


# Set up colored logging
handler = logging.StreamHandler()
handler.setFormatter(
    ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

# Set up file logging
file_handler = logging.FileHandler('mcp_debug.log')
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVEL)
root_logger.handlers.clear()
root_logger.addHandler(handler)
root_logger.addHandler(file_handler)
logger = logging.getLogger(__name__)


async def check_ollama_service():
    """Check if Ollama service is running and has the default model"""
    try:
        # Check if Ollama API is responding
        response = requests.get(f"{OLLAMA_API_BASE}/api/tags", timeout=5)
        if response.status_code != 200:
            print(f"[FAIL] Ollama API not responding at {OLLAMA_API_BASE}")
            return False

        # Check if the default model is available
        models_data = response.json()
        available_models = [model["name"] for model in models_data.get("models", [])]

        if DEFAULT_MODEL not in available_models:
            print(f"[FAIL] Default model '{DEFAULT_MODEL}' not found in Ollama")
            print(f"       Available models: {available_models}")
            return False

        print(f"INFO:     [ OK ] Ollama service ready with model '{DEFAULT_MODEL}'")
        return True

    except requests.exceptions.RequestException as e:
        print(f"INFO:     [FAIL] Failed to connect to Ollama at {OLLAMA_API_BASE}: {e}")
        return False
    except Exception as e:
        print(f"INFO:     [FAIL] Error checking Ollama service: {e}")
        return False


async def check_rag_service():
    """Check if RAG service is running"""
    try:
        rag_url = "http://localhost:8008/search/docs"
        response = requests.get(
            f"{rag_url.replace('/search/docs', '')}/health", timeout=5
        )
        if response.status_code == 200:
            print("INFO:     [ OK ] RAG service is running")
            return True
        else:
            print(
                f"INFO:     [WARN] RAG service health check failed (status: {response.status_code})"
            )
            return False
    except requests.exceptions.RequestException:
        print("INFO:     [WARN] RAG service not available - will continue without RAG")
        return False
    except Exception as e:
        print(f"INFO:     [WARN] RAG service check error: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    # Startup

    # Check Ollama dependency (required)
    if not await check_ollama_service():
        print("[FAIL] Ollama service check failed - this is required for operation")
        sys.exit(1)

    # Check RAG dependency (optional)
    await check_rag_service()
    
    # Start background summary worker
    import subprocess
    import threading
    import os
    
    def start_summary_worker():
        try:
            subprocess.Popen([
                sys.executable, "summary_worker.py"
            ], cwd=os.getcwd())
            print("INFO:     Summary worker started automatically")
        except Exception as e:
            print(f"WARN:     Failed to start summary worker: {e}")
    
    # Start worker in background thread
    worker_thread = threading.Thread(target=start_summary_worker, daemon=True)
    worker_thread.start()

    # Check memory system with proper inventory
    try:
        # Suppress connection logs during startup
        import logging
        logging.getLogger("tools.memory").setLevel(logging.WARNING)
        logging.getLogger("tools.rules").setLevel(logging.WARNING)
        
        from tools.memory import get_memory_system
        from tools.rules import get_rules_manager
        import redis
        from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_TIMEOUT
        from datetime import datetime
        import json
        
        # Get Redis stats
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, 
                                 socket_timeout=REDIS_TIMEOUT, decode_responses=True)
        
        # Count today's memories
        today = datetime.now().strftime("%Y-%m-%d")
        today_memories = 0
        total_conversations = 0
        
        for key in redis_client.scan_iter(match="conversation:*"):
            total_conversations += 1
            try:
                data = json.loads(redis_client.get(key))
                if data.get("date") == today:
                    today_memories += 1
            except:
                continue
        
        # Get LanceDB stats
        memory_system = get_memory_system()
        ssd_count = len(memory_system.ssd_table) if memory_system.ssd_table else 0
        nas_count = len(memory_system.nas_table) if memory_system.nas_table else 0
        
        # Get Rules stats
        rules_manager = get_rules_manager()
        rules_result = rules_manager.get_rules_summary()
        rules_count = rules_result.get("count", 0)
        
        print(f"INFO:     [ OK ] Redis: {today_memories} today/{total_conversations} total | LanceDB SSD: {ssd_count} | NAS: {nas_count} | Rules: {rules_count}")
        
        # Restore normal logging level
        logging.getLogger("tools.memory").setLevel(LOG_LEVEL)
        logging.getLogger("tools.rules").setLevel(LOG_LEVEL)
        
    except Exception as e:
        print(f"INFO:     [WARN] Memory system check: {e}")

    # Start daily batch transfer scheduler
    scheduler = None
    try:
        from tools.memory import run_daily_maintenance
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=run_daily_maintenance,
            trigger=CronTrigger(hour=2, minute=0),
            id='daily_memory_transfer',
            replace_existing=True
        )
        scheduler.start()
        print("INFO:     [ OK ] Daily memory transfer scheduler started")
    except Exception as e:
        print(f"INFO:     [WARN] Scheduler setup failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down MCP Server...")
    if scheduler:
        scheduler.shutdown()
    executor.shutdown(wait=True)


# Create FastAPI app
app = FastAPI(
    title="Advanced MCP Server",
    description="Model Context Protocol Server with intelligent agent capabilities",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routes
app.include_router(chat_router)


@app.get("/")
async def root():
    """Root endpoint with server info"""
    return {
        "name": "Advanced MCP Server",
        "version": "1.0.0",
        "status": "operational",
        "model": DEFAULT_MODEL,
        "endpoints": {
            "chat": "/api/chat",
            "openai_compatible": "/v1/chat/completions",
            "models": "/v1/models",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Basic health check - could be enhanced with dependency checks
    return JSONResponse(
        status_code=200, content={"status": "healthy", "version": "1.0.0"}
    )


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Preload user rules at startup for caching
    try:
        from core.orchestrator import get_user_rules

        get_user_rules()
        print("INFO:     [ OK ] User rules cached at startup")
    except Exception as e:
        print(f"INFO:     [WARN] Failed to cache user rules: {e}")

    # Start the server
    try:
        uvicorn.run(
            "main:app",
            host=MCP_SERVER_HOST,
            port=MCP_SERVER_PORT,
            reload=False,  # Disable reload for production
            log_level="info",
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
