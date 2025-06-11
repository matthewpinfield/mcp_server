#!/usr/bin/env python3
# /mnt/caseSSD/mcp_server_project/mcp_server.py

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import httpx
import logging
import json
import asyncio
import requests
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool
from typing import List, Dict, Any, Union 
from concurrent.futures import ThreadPoolExecutor

# --- Configuration ---
RAG_SERVER_ENDPOINT = "http://localhost:8008/custom_rag_stuff"
OLLAMA_API_BASE = "http://localhost:11434"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- FastAPI App ---
app = FastAPI(title="Unified MCP Orchestrator")

# --- Thread Pool for Synchronous Agent ---
executor = ThreadPoolExecutor(max_workers=10)

@app.on_event("startup")
async def startup_event():
    app.state.loop = asyncio.get_running_loop()

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

            logging.info(f"Making REAL HTTP POST request to RAG server at {RAG_SERVER_ENDPOINT} with query: {query}")
            
            response = requests.post(
                RAG_SERVER_ENDPOINT,
                json={"fullInput": query},
                timeout=120
            )
            response.raise_for_status()
            
            # Handle both JSON and text responses
            content_type = response.headers.get('content-type', '').lower()
            
            if 'application/json' in content_type:
                try:
                    rag_result = response.json()
                    logging.info(f"RAG server returned JSON: {rag_result}")
                    return rag_result
                except json.JSONDecodeError as e:
                    logging.warning(f"JSON parsing failed despite JSON content-type: {e}")
                    # Fallback to text
                    text_content = response.text.strip()
                    return {'retrieved_documentation': text_content}
            else:
                # Handle text/event-stream or other text responses
                text_content = response.text.strip()
                logging.info(f"RAG server returned text (length: {len(text_content)})")
                
                if not text_content:
                    return {'error': 'RAG server returned empty response'}
                
                # Try to parse as JSON first (in case content-type is wrong)
                if text_content.startswith(('{', '[')):
                    try:
                        rag_result = json.loads(text_content)
                        logging.info("Text response was actually valid JSON")
                        return rag_result
                    except json.JSONDecodeError:
                        pass  # Fall through to text handling
                
                # Return as text content in expected format
                return {'retrieved_documentation': text_content}

        except Exception as e:
            logging.error(f"Error calling RAG server in FlutterDocTool: {e}", exc_info=True)
            return {'error': f'Failed to call RAG server: {str(e)}'}

# --- Main Chat Endpoint ---
@app.post("/api/chat")
async def chat_proxy(request: Request):
    request_body = await request.json()
    model_name = request_body.get('model', 'qwen3:8b')
    messages = request_body.get('messages', [])
    
    logging.info(f"Processing request with Qwen-Agent for model: {model_name}")

    llm_config = {
        'model': model_name,
        'model_server': OLLAMA_API_BASE,
        'api_key': 'EMPTY',
        'generate_cfg': {
            'enable_thinking': False
        }
    }

    # --- THE FIX: Provide the most explicit type hint for Pylance ---
    # This tells Pylance that 'tools' is a list that can contain strings,
    # dictionaries, or instances of BaseTool, even if it only contains a string right now.
    tools: List[Union[str, Dict[Any, Any], BaseTool]] = ['query_flutter_dart_docs']

    bot = Assistant(llm=llm_config, function_list=tools)

    def run_agent_sync():
        try:
            yield from bot.run(messages=messages)
        except Exception as e:
            logging.error(f"FATAL ERROR in Qwen-Agent run: {e}", exc_info=True)
            error_response = {"error": "An error occurred during agent execution.", "details": str(e)}
            yield error_response

    response_iterator = await app.state.loop.run_in_executor(executor, run_agent_sync)

    async def stream_final_response():
        for chunk in response_iterator:
            yield json.dumps(chunk) + '\n'

    return StreamingResponse(stream_final_response(), media_type="application/x-ndjson")

# --- Other Endpoints (Restored) ---

@app.get("/api/tags")
async def tags_proxy():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logging.error("Error getting tags from Ollama in /api/tags:", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error getting tags from Ollama: {str(e)}")

@app.get("/api/ps")
async def ps_proxy():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/ps")
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logging.error("Error getting process status from Ollama in /api/ps:", exc_info=True)
            return JSONResponse(content={"models": []}, status_code=500)

@app.get("/api/version")
async def version_proxy():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/version")
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logging.error("Error getting version from Ollama in /api/version:", exc_info=True)
            return JSONResponse(content={"version": "unknown"}, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8009, log_level="info")