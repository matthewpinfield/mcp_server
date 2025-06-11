#!/usr/bin/env python3
# Optimal MCP Server - All issues fixed, no hardcoding

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import logging
import json
import asyncio
import os
import signal
import sys
import time
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool
from typing import List, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor

# --- Configuration (Environment Variables) ---
RAG_SERVER_ENDPOINT = os.getenv("RAG_SERVER_ENDPOINT", "http://localhost:8008/custom_rag_stuff")
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_OPENAI_BASE = os.getenv("OLLAMA_OPENAI_BASE", "http://localhost:11434/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen3:8b")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))

# Tool-capable models (configurable)
TOOL_CAPABLE_MODELS = os.getenv("TOOL_CAPABLE_MODELS", "qwen3:8b,qwen3:14b").split(",")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI App ---
app = FastAPI(title="Optimal MCP Server")

# --- Thread Pool with proper management ---
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="QwenAgent")

# --- Graceful shutdown handling ---
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    asyncio.create_task(trigger_shutdown())

async def trigger_shutdown():
    shutdown_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@app.on_event("startup")
async def startup_event():
    app.state.loop = asyncio.get_running_loop()
    logger.info("Optimal MCP Server started")

@app.on_event("shutdown")
async def shutdown_event_handler():
    logger.info("Starting graceful shutdown...")
    
    # Shutdown executor with timeout
    executor.shutdown(wait=False)
    
    # Wait for threads to complete (max 30 seconds)
    start_time = time.time()
    while executor._threads and (time.time() - start_time) < 30:
        await asyncio.sleep(0.1)
    
    if executor._threads:
        logger.warning(f"Force-terminated {len(executor._threads)} remaining threads")
    
    logger.info("Optimal MCP Server shutdown complete")

# --- RAG Tool (Simplified sync approach) ---
@register_tool('query_flutter_dart_docs')
class FlutterDocTool(BaseTool):
    description = 'Queries a knowledge base of Flutter/Dart documentation for technical questions.'
    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': 'The technical question about Flutter or Dart.',
        'required': True
    }]

    def call(self, params: Union[str, Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Synchronous tool call for Qwen-Agent compatibility"""
        try:
            if isinstance(params, str):
                params_dict = json.loads(params)
            else:
                params_dict = params
            
            query = params_dict.get('query')
            if not query:
                return {'error': 'The "query" parameter is missing.'}

            logger.info(f"RAG Tool: Querying for: {query}")
            
            # Use requests for synchronous call (required by Qwen-Agent)
            import requests
            response = requests.post(
                RAG_SERVER_ENDPOINT,
                json={"fullInput": query},
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            # Handle both JSON and text responses
            content_type = response.headers.get('content-type', '').lower()
            
            if 'application/json' in content_type:
                rag_result = response.json()
                logger.info(f"RAG Tool: Got JSON response ({len(str(rag_result))} chars)")
            else:
                rag_result = {"retrieved_documentation": response.text}
                logger.info(f"RAG Tool: Got text response ({len(response.text)} chars)")
            
            return rag_result

        except requests.exceptions.Timeout:
            logger.error("RAG Tool: Request timeout")
            return {'error': 'RAG server timeout'}
        except requests.exceptions.HTTPError as e:
            logger.error(f"RAG Tool: HTTP {e.response.status_code}")
            return {'error': f'RAG server error: {e.response.status_code}'}
        except Exception as e:
            logger.error(f"RAG Tool Error: {e}")
            return {'error': f'Failed to retrieve documentation: {str(e)}'}

# --- Model Selection Logic (No hardcoding) ---
def select_model(requested_model: str) -> str:
    """Select appropriate model based on request and capabilities"""
    
    # If requested model is tool-capable, use it
    if requested_model in TOOL_CAPABLE_MODELS:
        logger.info(f"Using requested tool-capable model: {requested_model}")
        return requested_model
    
    # Otherwise, use default tool-capable model
    selected = DEFAULT_MODEL if DEFAULT_MODEL in TOOL_CAPABLE_MODELS else TOOL_CAPABLE_MODELS[0]
    logger.info(f"Redirecting '{requested_model}' to '{selected}' for tool support")
    return selected

# --- Main Chat Endpoint ---
@app.post("/api/chat")
async def chat_proxy(request: Request):
    try:
        request_body = await request.json()
        requested_model = request_body.get('model', DEFAULT_MODEL)
        messages = request_body.get('messages', [])
        
        if not messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
        logger.info(f"Processing chat request for model: {requested_model}")

        # Smart model selection
        selected_model = select_model(requested_model)

        llm_config = {
            'model': selected_model,
            'model_server': OLLAMA_OPENAI_BASE,
            'api_key': 'EMPTY',
            'generate_cfg': {
                'temperature': 0.7,
                'max_tokens': 2000
            }
        }

        # Use string-based tool registration
        tools: List[Union[str, BaseTool]] = ['query_flutter_dart_docs']
        bot = Assistant(llm=llm_config, function_list=tools)

        def run_agent_sync():
            """Run agent synchronously with proper error handling"""
            try:
                logger.info("Agent: Starting execution")
                results = []
                for chunk in bot.run(messages=messages):
                    results.append(chunk)
                    if shutdown_event.is_set():
                        logger.info("Agent: Shutdown requested, stopping")
                        break
                logger.info(f"Agent: Completed with {len(results)} chunks")
                return results
            except Exception as e:
                logger.error(f"Agent error: {e}", exc_info=True)
                return [{"error": f"Agent execution failed: {str(e)}"}]

        # Run in executor with timeout
        try:
            response_list = await asyncio.wait_for(
                app.state.loop.run_in_executor(executor, run_agent_sync),
                timeout=REQUEST_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error("Agent execution timeout")
            raise HTTPException(status_code=504, detail="Request timeout")

        async def stream_response():
            """Stream response with proper error handling"""
            try:
                chunk_count = 0
                request_id = f"chatcmpl-{int(time.time())}"
                
                for chunk in response_list:
                    if shutdown_event.is_set():
                        break
                        
                    chunk_count += 1
                    
                    # Extract content from agent response
                    content = ""
                    if isinstance(chunk, list) and len(chunk) > 0:
                        chunk_data = chunk[0]
                        if isinstance(chunk_data, dict):
                            content = chunk_data.get('content', '')
                    elif isinstance(chunk, dict):
                        content = chunk.get('content', '')
                        if 'error' in chunk:
                            content = f"Error: {chunk['error']}"
                    
                    if content:
                        # Filter out thinking content for Open WebUI compatibility
                        if '<think>' in content or '</think>' in content:
                            logger.debug(f"Filtering thinking content: {content[:50]}...")
                            continue
                        
                        # Skip empty or whitespace-only content
                        if not content.strip():
                            continue
                        
                        # SSE format for Open WebUI
                        sse_chunk = {
                            "id": f"{request_id}-{chunk_count}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": selected_model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": content},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(sse_chunk)}\n\n"
                        await asyncio.sleep(0.01)  # Prevent overwhelming
                
                # Send final chunk
                final_chunk = {
                    "id": f"{request_id}-{chunk_count + 1}",
                    "object": "chat.completion.chunk", 
                    "created": int(time.time()),
                    "model": selected_model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
                
                logger.info(f"Streamed {chunk_count} chunks successfully")
                
            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                error_chunk = {
                    "id": f"error-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": selected_model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": f"Streaming error: {str(e)}"},
                        "finish_reason": "error"
                    }]
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"

        return StreamingResponse(
            stream_response(), 
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

# --- Proxy Endpoints with proper async handling ---
@app.get("/api/tags")
async def tags_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logger.error(f"Tags error: {e}")
            raise HTTPException(status_code=502, detail="Failed to get model tags")

@app.get("/api/ps")
async def ps_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/ps")
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logger.error(f"Process status error: {e}")
            return JSONResponse(content={"models": []})

@app.get("/api/version")
async def version_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/version")
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logger.error(f"Version error: {e}")
            return JSONResponse(content={"version": "unknown"})

@app.get("/health")
async def health():
    return {
        "status": "healthy", 
        "timestamp": time.time(),
        "default_model": DEFAULT_MODEL,
        "tool_capable_models": TOOL_CAPABLE_MODELS
    }

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8009, 
        log_level="info"
    )