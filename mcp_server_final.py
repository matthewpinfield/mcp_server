#!/usr/bin/env python3
# MCP Server - Single Unified Server for Open WebUI with Flutter Documentation

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import requests
import json
import logging
import time
import os
import asyncio
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MCP Server - Flutter Documentation",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Add CORS middleware for Open WebUI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OLLAMA_BASE = "http://localhost:11434"
RAG_SERVER_ENDPOINT = os.getenv("RAG_SERVER_ENDPOINT", "http://localhost:8008/custom_rag_stuff")
MCP_PORT = int(os.getenv("MCP_PORT", "8012"))
# No API key needed for local development

# Flutter function definition
FLUTTER_FUNCTION = {
    "type": "function",
    "function": {
        "name": "query_flutter_docs",
        "description": "Query Flutter/Dart documentation for technical questions about Flutter framework, Dart language, widgets, state management, navigation, APIs, debugging, or code examples. Use this when users ask specific Flutter/Dart questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The Flutter/Dart question to search documentation for"
                }
            },
            "required": ["query"]
        }
    }
}

class ChatMessage(BaseModel):
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None

class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    tools: Optional[List[Dict]] = None
    temperature: Optional[float] = 0.7

async def query_flutter_documentation(query: str) -> str:
    """Query Flutter documentation via integrated RAG"""
    try:
        logger.info(f"🔍 Starting Flutter docs query: {query}")
        logger.info(f"🌐 Calling RAG server at: {RAG_SERVER_ENDPOINT}")
        
        # Call RAG server directly (integrated)
        response = requests.post(
            RAG_SERVER_ENDPOINT,
            json={"fullInput": query},
            timeout=30
        )
        response.raise_for_status()
        
        # Handle both JSON and text responses
        try:
            rag_json = response.json()
            if isinstance(rag_json, dict):
                if "answer" in rag_json:
                    result = rag_json["answer"]
                elif "text" in rag_json:
                    result = rag_json["text"]
                elif "content" in rag_json:
                    result = rag_json["content"]
                else:
                    result = json.dumps(rag_json)
            else:
                result = json.dumps(rag_json)
        except ValueError:
            result = response.text
        
        logger.info(f"Documentation retrieved (length: {len(result)})")
        return result
        
    except Exception as e:
        logger.error(f"Flutter documentation query failed: {e}")
        return f"Error retrieving Flutter documentation: {str(e)}"

async def execute_function_call(function_name: str, arguments: dict) -> str:
    """Execute function calls"""
    if function_name == "query_flutter_docs":
        query = arguments.get("query")
        if not query:
            return "Error: Query parameter required"
        return await query_flutter_documentation(query)
    else:
        return f"Error: Unknown function: {function_name}"

@app.post("/api/chat/completions")
async def chat_external(request: ChatRequest):
    """Chat endpoint for Open WebUI External API"""
    return await chat_completions(request)

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completions with Flutter function calling"""
    
    # Convert Pydantic models to dicts for Ollama
    messages_dict = []
    for msg in request.messages:
        msg_dict = {"role": msg.role, "content": msg.content}
        if msg.tool_calls:
            msg_dict["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            msg_dict["tool_call_id"] = msg.tool_call_id
        messages_dict.append(msg_dict)
    
    # Prepare payload for Ollama
    ollama_payload = {
        "model": request.model,
        "messages": messages_dict,
        "stream": request.stream,
        "temperature": request.temperature
    }
    
    # Add Flutter function for Flutter-related queries
    last_message = messages_dict[-1].get("content", "").lower() if messages_dict else ""
    flutter_keywords = ["flutter", "dart", "widget", "state", "build", "scaffold", "appbar", "stateful", "stateless"]
    
    # Always enable Flutter function for testing
    ollama_payload["tools"] = [FLUTTER_FUNCTION]
    logger.info(f"Flutter function enabled for this query. Stream={request.stream}")
    
    try:
        # Send to Ollama
        ollama_response = requests.post(
            f"{OLLAMA_BASE}/v1/chat/completions",
            json=ollama_payload,
            timeout=90
        )
        ollama_response.raise_for_status()
        
        if request.stream:
            # Handle streaming response (simplified for now)
            return StreamingResponse(
                stream_ollama_response(ollama_response),
                media_type="text/event-stream"
            )
        else:
            # Handle non-streaming response
            result = ollama_response.json()
            
            # Check if function was called
            choice = result.get('choices', [{}])[0]
            message = choice.get('message', {})
            logger.info(f"🤖 Ollama response message keys: {list(message.keys())}")
            
            if 'tool_calls' in message:
                logger.info("Function called - executing and getting final response")
                
                # Execute function call
                tool_call = message['tool_calls'][0]
                function_name = tool_call['function']['name']
                function_args = json.loads(tool_call['function']['arguments'])
                
                function_result = await execute_function_call(function_name, function_args)
                
                # Send function result back to Ollama for final response
                follow_up_messages = messages_dict + [
                    message,  # Assistant's function call
                    {
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": function_result
                    }
                ]
                
                final_payload = {
                    "model": request.model,
                    "messages": follow_up_messages,
                    "stream": False,
                    "temperature": request.temperature
                }
                
                final_response = requests.post(
                    f"{OLLAMA_BASE}/v1/chat/completions",
                    json=final_payload,
                    timeout=90
                )
                final_response.raise_for_status()
                return final_response.json()
            
            # No function call needed, return original response
            return result
            
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def stream_ollama_response(ollama_response):
    """Stream response from Ollama"""
    for chunk in ollama_response.iter_content(chunk_size=1024):
        if chunk:
            yield chunk

@app.get("/api/models")
async def list_models_external():
    """List models for Open WebUI External API"""
    try:
        response = requests.get(f"{OLLAMA_BASE}/api/tags")
        response.raise_for_status()
        ollama_models = response.json()
        
        # Open WebUI expects this exact format
        models = []
        for model in ollama_models.get('models', []):
            models.append({
                "id": model['name'],
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ollama"
            })
        
        return {"object": "list", "data": models}
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch models")

@app.get("/v1/models")
async def list_models():
    """List available models from Ollama"""
    try:
        response = requests.get(f"{OLLAMA_BASE}/api/tags")
        response.raise_for_status()
        ollama_models = response.json()
        
        # Convert to OpenAI format
        models = []
        for model in ollama_models.get('models', []):
            models.append({
                "id": model['name'],
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ollama"
            })
        
        return {"object": "list", "data": models}
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch models")

# Proxy endpoints for Open WebUI compatibility
@app.get("/api/tags")
async def tags_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_BASE}/api/tags")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Tags proxy error: {e}")
            raise HTTPException(status_code=502, detail="Failed to get model tags")

@app.get("/api/ps")
async def ps_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_BASE}/api/ps")
            response.raise_for_status()
            return response.json() if response.content else {"models": []}
        except Exception as e:
            logger.error(f"Process status proxy error: {e}")
            return {"models": []}

@app.get("/api/version")
async def version_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_BASE}/api/version")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Version proxy error: {e}")
            return {"version": "unknown"}

@app.get("/")
async def root():
    return {
        "message": "MCP Server - Flutter Documentation", 
        "version": "1.0.0",
        "flutter_docs": "Integrated",
        "models_endpoint": "/v1/models",
        "chat_endpoint": "/v1/chat/completions"
    }

@app.get("/v1")
async def v1_root():
    return {
        "message": "MCP Server OpenAI API v1", 
        "available_endpoints": ["/v1/models", "/v1/chat/completions"],
        "flutter_function": "Enabled"
    }

@app.get("/health")
async def health():
    # Test RAG server connectivity
    rag_healthy = False
    try:
        test_response = requests.get(RAG_SERVER_ENDPOINT.replace('/custom_rag_stuff', '/health'), timeout=5)
        rag_healthy = test_response.status_code == 200
    except:
        pass
    
    # Test Ollama connectivity
    ollama_healthy = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE}/api/version")
            ollama_healthy = response.status_code == 200
    except:
        pass
    
    return {
        "status": "healthy" if (rag_healthy and ollama_healthy) else "degraded",
        "ollama": "healthy" if ollama_healthy else "unreachable",
        "flutter_docs": "healthy" if rag_healthy else "unreachable",
        "port": MCP_PORT,
        "timestamp": time.time()
    }

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 MCP Server - Flutter Documentation")
    logger.info("=" * 50)
    logger.info(f"📡 OpenAI API: http://localhost:{MCP_PORT}/v1")
    logger.info(f"🔧 Configure Open WebUI with: http://localhost:{MCP_PORT}/v1")
    logger.info(f"📚 Flutter Documentation: Integrated")
    logger.info(f"🤖 Recommended Model: qwen3:8b")
    logger.info("=" * 50)
    
    # Allow Docker access while restricting to local network
    uvicorn.run(app, host="0.0.0.0", port=MCP_PORT)