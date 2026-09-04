#!/usr/bin/env python3
# Dual Endpoint RAG Server - Flutter Docs + Mixed Code Database
# Keeps original optimal_server.py as fallback

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
import lancedb
import ollama
import logging
import asyncio
import os
import time
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

# --- Configuration ---
DB_PATH = os.getenv("DB_PATH", "/opt/mcp/rag/")
FLUTTER_TABLE = os.getenv("FLUTTER_TABLE", "flutter_dart_knowledge")
MIXED_TABLE = os.getenv("MIXED_TABLE", "expert_py_flutter_dart_final")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gemma4:26b")
EMBEDDING_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT", "30"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Dual_RAG_Service")

# Global database connections
flutter_table = None
mixed_table = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Logic
    global flutter_table, mixed_table
    logger.info("Dual Endpoint RAG Service starting up...")
    
    try:
        db = lancedb.connect(DB_PATH)
        
        # Connect to Flutter documentation database (5,098 docs - 39.8% official docs)
        flutter_table = db.open_table(FLUTTER_TABLE)
        logger.info(f" Flutter Docs DB: {len(flutter_table)} docs (official docs + Firebase)")
        
        # Connect to mixed database (11,663 docs - Python + Flutter code)
        mixed_table = db.open_table(MIXED_TABLE)
        logger.info(f" Mixed Code DB: {len(mixed_table)} docs (Python + Flutter code)")
        
        logger.info(f"Total: {len(flutter_table) + len(mixed_table)} documents")
        logger.info("Flutter/Dart + Python + Firebase coverage ready")
        
    except Exception as e:
        logger.error(f" FATAL: Database connection failed: {e}")
        raise
    
    yield # Application runs
    
    # Shutdown
    logger.info("Dual RAG Service shutting down...")

app = FastAPI(
    title="Dual Endpoint RAG Service",
    description="Specialized Flutter docs + comprehensive Python/Flutter code examples",
    version="2.0.0",
    lifespan=lifespan
)

async def search_database(table, query: str, limit: int = 5) -> List[Dict]:
    """Search a database table with embeddings"""
    
    try:
        # Get query embeddings
        embed_response = await asyncio.wait_for(
            asyncio.to_thread(ollama.embeddings, model=EMBEDDING_MODEL, prompt=query),
            timeout=EMBEDDING_TIMEOUT
        )
        query_embedding = embed_response['embedding']
        
        # Search the table
        results = table.search(query_embedding).limit(limit).to_list()
        
        # Convert to consistent format
        formatted_results = []
        for result in results:
            formatted_result = {
                'text': result.get('text', ''),
                'metadata': {k: v for k, v in result.items() if k not in ['text', '_distance', 'vector']},
                'distance': result.get('_distance', 0.0),
                'db_source': 'flutter_docs' if table == flutter_table else 'mixed_code'
            }
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Database search error: {e}")
        return []

@app.post("/search/docs")
async def search_flutter_docs(
    request: Request,
    query: str = Query(..., description="Search query for Flutter documentation"),
    limit: int = Query(5, ge=1, le=20, description="Number of results")
):
    """
    Search Flutter Documentation Database
    
    Best for:
    - Official Flutter/Dart documentation
    - Firebase integration guides  
    - API references and widget docs
    - Flutter concepts and architecture
    - Package documentation from pub.dev
    
    Contains: 5,098 docs (39.8% official docs, 60.1% Firebase/Flutter repos)
    """
    
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    logger.info(f"DOCS Search: '{query}' | Limit: {limit}")
    start_time = time.time()
    
    try:
        results = await search_database(flutter_table, query, limit)
        search_time = time.time() - start_time
        
        response = {
            "query": query,
            "database": "flutter_docs",
            "description": "Flutter documentation and Firebase guides",
            "total_results": len(results),
            "search_time": search_time,
            "results": results
        }
        
        logger.info(f" DOCS: {len(results)} results in {search_time:.3f}s")
        return response
        
    except Exception as e:
        logger.error(f" Docs search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Documentation search failed: {str(e)}")

@app.post("/search/code")
async def search_code_examples(
    request: Request,
    query: str = Query(..., description="Search query for code examples"),
    limit: int = Query(5, ge=1, le=20, description="Number of results")
):
    """
    Search Code Examples Database
    
    Best for:
    - Python code examples (FastAPI, pandas, Django)
    - Flutter/Dart code implementations
    - Real-world patterns and solutions
    - Algorithm implementations
    - Framework-specific examples
    
    Contains: 11,663 docs (77.9% Python, 22.1% Flutter code from elite repos)
    """
    
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    logger.info(f"CODE Search: '{query}' | Limit: {limit}")
    start_time = time.time()
    
    try:
        results = await search_database(mixed_table, query, limit)
        search_time = time.time() - start_time
        
        response = {
            "query": query,
            "database": "mixed_code", 
            "description": "Python and Flutter code examples from elite repositories",
            "total_results": len(results),
            "search_time": search_time,
            "results": results
        }
        
        logger.info(f" CODE: {len(results)} results in {search_time:.3f}s")
        return response
        
    except Exception as e:
        logger.error(f" Code search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Code search failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check with database statistics"""
    
    flutter_count = len(flutter_table) if flutter_table else 0
    mixed_count = len(mixed_table) if mixed_table else 0
    
    return {
        "status": "healthy",
        "databases": {
            "flutter_docs": {
                "connected": flutter_table is not None,
                "documents": flutter_count,
                "description": "Flutter documentation + Firebase guides (LanceDB)"
            },
            "mixed_code": {
                "connected": mixed_table is not None, 
                "documents": mixed_count,
                "description": "Python + Flutter code examples (LanceDB)"
            }
        },
        "total_documents": flutter_count + mixed_count,
        "coverage": ["Flutter/Dart", "Python", "Firebase"]
    }

@app.get("/usage-guide")
async def get_usage_guide():
    """Usage guide for MCP agents with 50+ examples"""
    
    return {
        "endpoints": {
            "/search/docs": "Flutter documentation, API refs, Firebase guides",
            "/search/code": "Python and Flutter code examples"
        },
        
        "use_docs_for": [
            # Documentation & Learning (1-15)
            "What is Flutter?",
            "How does Firebase integrate with Flutter?", 
            "What are Flutter widgets?",
            "Explain StatefulWidget vs StatelessWidget",
            "What is the Flutter widget tree?",
            "How does Flutter state management work?",
            "What are Flutter lifecycle methods?",
            "How to handle navigation in Flutter?",
            "What is the difference between Material and Cupertino?",
            "How does Flutter theming work?",
            "What are Flutter animations?",
            "How to handle user input in Flutter?",
            "What is Flutter's rendering pipeline?",
            "How does Flutter handle accessibility?",
            "What are Flutter platform channels?",
            
            # API References (16-25)
            "StatefulWidget API documentation",
            "Firebase Auth API reference", 
            "Navigator class methods",
            "TextEditingController properties",
            "MediaQuery API details",
            "Theme class documentation",
            "GestureDetector API reference",
            "AnimationController methods",
            "CustomScrollView API",
            "Provider package documentation",
            
            # Official Guides (26-35)
            "Flutter installation guide",
            "Getting started with Flutter",
            "Flutter best practices",
            "Flutter performance optimization", 
            "Flutter testing guidelines",
            "Flutter deployment guide",
            "Flutter web development",
            "Flutter desktop development",
            "Flutter accessibility guidelines",
            "Flutter internationalization"
        ],
        
        "use_code_for": [
            # Flutter Code Examples (36-50)
            "Show me a StatefulWidget example",
            "Give me a ListView implementation", 
            "How to implement a custom widget",
            "Show authentication code with Firebase",
            "Example of using Provider for state management",
            "HTTP request implementation in Flutter",
            "Form validation code example",
            "Custom animation implementation",
            "Database integration code",
            "File upload implementation",
            "Push notification handling code", 
            "Camera integration example",
            "Maps implementation in Flutter",
            "Custom painter example",
            "WebSocket implementation in Flutter",
            
            # Python Examples (51-65)
            "FastAPI dependency injection example",
            "Pandas DataFrame operations code",
            "Async function implementation",
            "SQLAlchemy model example", 
            "Django view implementation",
            "Error handling in Python",
            "API endpoint code example",
            "Database query optimization",
            "Authentication middleware code",
            "File processing in Python",
            "WebSocket server implementation",
            "Background task processing",
            "Data validation with Pydantic", 
            "Testing with pytest examples",
            "Docker configuration for Python apps"
        ],
        
        "decision_tree": {
            "asking_what_or_how_concept": "Use /search/docs",
            "asking_for_implementation": "Use /search/code", 
            "api_reference_needed": "Use /search/docs",
            "code_example_needed": "Use /search/code",
            "python_specific": "Use /search/code",
            "flutter_concept": "Use /search/docs",
            "flutter_implementation": "Use /search/code"
        }
    }

if __name__ == "__main__":
    print("Starting Dual Endpoint RAG Server")
    print("/search/docs - Flutter Documentation + Firebase")  
    print("/search/code - Python + Flutter Code Examples")
    print("Server: http://0.0.0.0:8008")
    print("Usage guide: http://0.0.0.0:8008/usage-guide") 
    print("Replaces optimal_server.py with dual endpoints")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8008,
        log_level="info"
    )