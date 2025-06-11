#!/usr/bin/env python3
# Fixed MCP Server - Let Ollama choose model, simple approach

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import logging
import json
import asyncio
import requests
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool
from typing import List, Dict, Any, Union 
from concurrent.futures import ThreadPoolExecutor
import time

# --- Configuration ---
RAG_SERVER_ENDPOINT = "http://localhost:8008/custom_rag_stuff"
OLLAMA_API_BASE = "http://localhost:11434"
OLLAMA_OPENAI_BASE = "http://localhost:11434/v1"  # OpenAI-compatible endpoint

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- FastAPI App ---
app = FastAPI(title="Fixed MCP Orchestrator")

# --- Thread Pool for Synchronous Agent (with proper cleanup) ---
executor = ThreadPoolExecutor(max_workers=5)

@app.on_event("startup")
async def startup_event():
    app.state.loop = asyncio.get_running_loop()
    logging.info("MCP Server started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    executor.shutdown(wait=True)
    logging.info("MCP Server shutdown complete")

# --- Define Your RAG Tool for Qwen-Agent ---
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
        try:
            if isinstance(params, str):
                params_dict = json.loads(params)
            else:
                params_dict = params
            
            query = params_dict.get('query')
            if not query:
                return {'error': 'The "query" parameter is missing.'}

            logging.info(f"RAG Tool: Querying for: {query}")
            
            response = requests.post(
                RAG_SERVER_ENDPOINT,
                json={"fullInput": query},
                timeout=120
            )
            response.raise_for_status()
            
            # Handle both JSON and text responses
            content_type = response.headers.get('content-type', '').lower()
            
            if 'application/json' in content_type:
                # JSON response
                rag_result = response.json()
                logging.info(f"RAG Tool: Retrieved JSON response with {len(str(rag_result))} chars")
            else:
                # Text response (including text/event-stream)
                rag_result = {"retrieved_documentation": response.text}
                logging.info(f"RAG Tool: Retrieved text response with {len(response.text)} chars")
            
            return rag_result

        except Exception as e:
            logging.error(f"RAG Tool Error: {e}")
            return {'error': f'Failed to retrieve documentation: {str(e)}'}

# --- Main Chat Endpoint ---
@app.post("/api/chat")
async def chat_proxy(request: Request):
    try:
        request_body = await request.json()
        model_name = request_body.get('model', 'qwen2.5:7b')  # Fallback only
        messages = request_body.get('messages', [])
        
        if not messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
        logging.info(f"Processing chat request for model: {model_name}")

        # Smart model selection: Allow choice between tool-capable models, prevent gemma
        tool_capable_models = ['qwen3:8b', 'qwen3:14b']
        default_model = 'qwen3:8b'
        
        # Use requested model if it supports tools, otherwise default to qwen3:8b
        if model_name in tool_capable_models:
            selected_model = model_name
            logging.info(f"Using requested tool-capable model: {selected_model}")
        else:
            selected_model = default_model
            logging.info(f"Requested model '{model_name}' doesn't support tools, using: {selected_model}")
        
        llm_config = {
            'model': selected_model,  # Ensure tool-capable model is used
            'model_server': OLLAMA_OPENAI_BASE,  # Use OpenAI-compatible endpoint
            'api_key': 'EMPTY',
            'generate_cfg': {
                # Standard OpenAI-compatible parameters only
                'temperature': 0.7,
                'max_tokens': 4000
            }
        }

        # Use string-based tool registration (works better)
        tools: List[Union[str, BaseTool]] = ['query_flutter_dart_docs']

        # Create fresh agent instance for each request (prevents state issues)
        bot = Assistant(llm=llm_config, function_list=tools)

        def run_agent_sync():
            """Run agent in thread pool to prevent blocking"""
            try:
                logging.info("Agent: Starting execution")
                response_count = 0
                for chunk in bot.run(messages=messages):
                    response_count += 1
                    logging.debug(f"Agent: Yielding chunk {response_count}")
                    yield chunk
                logging.info(f"Agent: Completed with {response_count} chunks")
            except Exception as e:
                logging.error(f"Agent execution error: {e}", exc_info=True)
                yield {"error": f"Agent execution failed: {str(e)}"}

        # Run in executor to prevent blocking
        response_iterator = await app.state.loop.run_in_executor(
            executor, 
            lambda: list(run_agent_sync())
        )

        async def stream_response():
            """SSE format for Open WebUI compatibility"""
            try:
                chunk_count = 0
                request_id = f"chatcmpl-{int(time.time())}"
                
                for chunk in response_iterator:
                    chunk_count += 1
                    
                    # Extract content from agent response
                    content = ""
                    if isinstance(chunk, list) and len(chunk) > 0:
                        chunk_data = chunk[0]
                        if isinstance(chunk_data, dict):
                            content = chunk_data.get('content', '')
                    elif isinstance(chunk, dict):
                        content = chunk.get('content', '')
                    
                    if content:
                        # SSE format for Open WebUI
                        sse_chunk = {
                            "id": f"{request_id}-{chunk_count}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model_name,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": content},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(sse_chunk)}\n\n"
                
                # Send final chunk
                final_chunk = {
                    "id": f"{request_id}-{chunk_count + 1}",
                    "object": "chat.completion.chunk", 
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
                
                logging.info(f"Streamed {chunk_count} chunks to client in SSE format")
            except Exception as e:
                logging.error(f"Streaming error: {e}")
                error_chunk = {
                    "id": f"error-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": f"Error: {str(e)}"},
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

    except Exception as e:
        logging.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

# --- Proxy Endpoints (Keep Ollama compatibility) ---
@app.get("/api/tags")
async def tags_proxy():
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logging.error(f"Tags proxy error: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get tags: {str(e)}")

@app.get("/api/ps")
async def ps_proxy():
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/ps")
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logging.error(f"Process status proxy error: {e}")
            return JSONResponse(content={"models": []})

@app.get("/api/version")
async def version_proxy():
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/version")
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logging.error(f"Version proxy error: {e}")
            return JSONResponse(content={"version": "unknown"})

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8009, 
        log_level="info",
        access_log=True
    )