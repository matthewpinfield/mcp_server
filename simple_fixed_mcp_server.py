#!/usr/bin/env python3
# Simple Fixed MCP Server - Based on old working version with minimal changes

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
OLLAMA_OPENAI_BASE = "http://localhost:11434/v1"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- FastAPI App ---
app = FastAPI(title="Simple Fixed MCP Server")

# --- Thread Pool ---
executor = ThreadPoolExecutor(max_workers=3)

@app.on_event("startup")
async def startup_event():
    app.state.loop = asyncio.get_running_loop()
    logging.info("Simple MCP Server started")

@app.on_event("shutdown")
async def shutdown_event():
    executor.shutdown(wait=False)
    logging.info("Simple MCP Server shutdown")

# --- RAG Tool (Fixed for text responses) ---
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
                timeout=60  # Shorter timeout
            )
            response.raise_for_status()
            
            # Handle text response (your RAG server returns text/event-stream)
            content_type = response.headers.get('content-type', '').lower()
            
            if 'application/json' in content_type:
                rag_result = response.json()
                logging.info(f"RAG Tool: Got JSON response ({len(str(rag_result))} chars)")
            else:
                # Wrap text response in dict for agent
                rag_result = {"retrieved_documentation": response.text}
                logging.info(f"RAG Tool: Got text response ({len(response.text)} chars)")
            
            return rag_result

        except Exception as e:
            logging.error(f"RAG Tool Error: {e}")
            return {'error': f'Failed to retrieve documentation: {str(e)}'}

# --- Main Chat Endpoint ---
@app.post("/api/chat")
async def chat_proxy(request: Request):
    try:
        request_body = await request.json()
        model_name = request_body.get('model', 'qwen3:8b')
        messages = request_body.get('messages', [])
        
        if not messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
        logging.info(f"Processing chat request for model: {model_name}")

        # Smart model selection to avoid gemma
        tool_capable_models = ['qwen3:8b', 'qwen3:14b']
        if model_name in tool_capable_models:
            selected_model = model_name
            logging.info(f"Using requested model: {selected_model}")
        else:
            selected_model = 'qwen3:8b'
            logging.info(f"Redirecting {model_name} to {selected_model} for tool support")

        llm_config = {
            'model': selected_model,
            'model_server': OLLAMA_OPENAI_BASE,  # Use v1 endpoint
            'api_key': 'EMPTY',
            'generate_cfg': {
                'temperature': 0.7,
                'max_tokens': 2000  # Limit to prevent runaway
            }
        }

        # Use string-based tool registration (simpler)
        tools: List[Union[str, BaseTool]] = ['query_flutter_dart_docs']
        bot = Assistant(llm=llm_config, function_list=tools)

        def run_agent_sync():
            """Run agent synchronously"""
            try:
                logging.info("Agent: Starting execution")
                results = []
                for chunk in bot.run(messages=messages):
                    results.append(chunk)
                logging.info(f"Agent: Completed with {len(results)} chunks")
                return results
            except Exception as e:
                logging.error(f"Agent error: {e}", exc_info=True)
                return [{"error": f"Agent execution failed: {str(e)}"}]

        # Run in executor but get all results first
        response_list = await app.state.loop.run_in_executor(executor, run_agent_sync)

        async def stream_simple():
            """Simple streaming based on old version"""
            try:
                for chunk in response_list:
                    # Convert to simple JSON lines (like old version)
                    yield json.dumps(chunk) + '\n'
                    await asyncio.sleep(0.01)  # Small delay for smoother streaming
                logging.info(f"Streamed {len(response_list)} chunks")
            except Exception as e:
                logging.error(f"Streaming error: {e}")
                yield json.dumps({"error": f"Streaming failed: {str(e)}"}) + '\n'

        return StreamingResponse(
            stream_simple(), 
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache"}
        )

    except Exception as e:
        logging.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

# --- Proxy Endpoints ---
@app.get("/api/tags")
async def tags_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
            return JSONResponse(content=response.json())
        except Exception as e:
            logging.error(f"Tags error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ps")
async def ps_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/ps")
            return JSONResponse(content=response.json())
        except Exception as e:
            logging.error(f"PS error: {e}")
            return JSONResponse(content={"models": []})

@app.get("/api/version")
async def version_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/version")
            return JSONResponse(content=response.json())
        except Exception as e:
            logging.error(f"Version error: {e}")
            return JSONResponse(content={"version": "unknown"})

@app.get("/health")
async def health():
    return {"status": "ok", "time": time.time()}

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8009, 
        log_level="info"
    )