#!/usr/bin/env python3
# OpenAI-Compatible API Server with Flutter Function Calling

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import requests
import json
import logging
import time
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenAI Compatible API with Flutter Functions")

# Configuration
OLLAMA_BASE = "http://localhost:11434"
FUNCTION_SERVER = "http://localhost:8010"

# Load Flutter function definition
with open('flutter_docs_function.json', 'r') as f:
    FLUTTER_FUNCTION = json.load(f)

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

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict]

async def execute_function_call(function_name: str, arguments: dict) -> str:
    """Execute function call via our function server"""
    try:
        response = requests.post(
            f"{FUNCTION_SERVER}/execute_function",
            json={"name": function_name, "arguments": arguments},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result.get('result', 'No result returned')
    except Exception as e:
        logger.error(f"Function execution error: {e}")
        return f"Function execution failed: {str(e)}"

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completions with function calling"""
    
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
    
    # Add Flutter function if tools are requested or if it's a Flutter-related query
    last_message = messages_dict[-1].get("content", "").lower() if messages_dict else ""
    flutter_keywords = ["flutter", "dart", "widget", "state", "build", "scaffold", "appbar"]
    
    if request.tools or any(keyword in last_message for keyword in flutter_keywords):
        ollama_payload["tools"] = [FLUTTER_FUNCTION]
    
    try:
        # Send to Ollama
        ollama_response = requests.post(
            f"{OLLAMA_BASE}/v1/chat/completions",
            json=ollama_payload,
            timeout=60
        )
        ollama_response.raise_for_status()
        
        if request.stream:
            # Handle streaming response
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
                    timeout=60
                )
                final_response.raise_for_status()
                return final_response.json()
            
            # No function call needed, return original response
            return result
            
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def stream_ollama_response(ollama_response):
    """Stream response from Ollama (simplified for now)"""
    for chunk in ollama_response.iter_content(chunk_size=1024):
        if chunk:
            yield chunk

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

@app.get("/")
async def root():
    return {"message": "OpenAI Compatible API with Flutter Functions", "version": "1.0.0"}

@app.get("/v1")
async def v1_root():
    return {"message": "OpenAI Compatible API v1", "available_endpoints": ["/v1/models", "/v1/chat/completions"]}

@app.get("/health")
async def health():
    return {"status": "healthy", "function_server": f"{FUNCTION_SERVER}"}

if __name__ == "__main__":
    logger.info("Starting OpenAI-compatible API server with Flutter functions...")
    logger.info("Configure Open WebUI to use: http://localhost:8011/v1")
    uvicorn.run(app, host="0.0.0.0", port=8011)