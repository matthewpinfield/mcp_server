#!/usr/bin/env python3
"""
Chat API endpoint for Advanced MCP Server - Version 2
Main chat_proxy endpoint with simplified Gemma4 integration
"""

import json
import logging
import asyncio
import time
from typing import List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, Request, HTTPException, Depends, Security
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import APIKeyHeader

from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub

from core.orchestrator import (
    get_tool_recommendations,
    get_workflow_recommendations,
    execute_agent_request
)

from config import (
    OLLAMA_API_BASE,
    DEFAULT_MODEL,
    LANGCHAIN_AGENT_TIMEOUT,
    DEFAULT_SLASH_COMMANDS,
    MCP_API_KEY
)

# Import all tools
from tools import (
    LangchainMemoryContextTool,
    LangchainMemorySaveTool,
    LangchainMemoryRuleTool,
    LangchainMemoryStatsTool,
    LangchainMemoryCorrectionTool,
    MultiLanguageSandboxTool,
    SandboxStatsTool,
    LangchainWebSearchTool,
    LangchainFlutterDocTool,
    LangchainCodeSearchTool
)


logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(_api_key_header)):
    """Require a matching X-API-Key header if MCP_API_KEY is configured.

    If MCP_API_KEY is unset, the API stays open (local-only default).
    """
    if MCP_API_KEY and api_key != MCP_API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return True

router = APIRouter(dependencies=[Depends(verify_api_key)])



# ===== UNIFIED AGENT PATH WITH THINKING MODE =====

# ===== MAIN CHAT ENDPOINT =====

@router.post("/api/chat")
async def chat_proxy(request: Request):
    """Main chat endpoint that routes requests to appropriate handlers"""
    try:
        request_body = await request.json()
        requested_model_name = request_body.get('model', DEFAULT_MODEL) 
        messages = request_body.get('messages', []) 
        stream = request_body.get("stream", True)
        
        if not messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
        # Get the latest user message (matching old format)
        user_message = ""
        if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
            content = messages[-1].get("content")
            if isinstance(content, str): 
                user_message = content
        
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")
        
        logger.info(f"Chat Request: Model='{requested_model_name}', Msgs={len(messages)}")
        
        # Check for slash commands
        if user_message.strip().startswith('/'):
            parts = user_message.strip().split(' ', 1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            
            # Get custom commands from memory
            try:
                memory_tool = LangchainMemoryContextTool()
                custom_commands_result = memory_tool._run("custom_slash_commands")
                custom_commands = json.loads(custom_commands_result) if custom_commands_result else {}
            except:
                custom_commands = {}
            
            # Process slash command
            from tools.knowledge import process_slash_command
            response_text = process_slash_command(command, args, custom_commands)
            
            if stream:
                async def command_stream():
                    # Send command response as streaming chunks
                    stream_chunk = {
                        "id": "chatcmpl-command",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": response_text},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(stream_chunk)}\n\n"
                    
                    # Send final chunk
                    final_chunk = {
                        "id": "chatcmpl-command",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }]
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                
                return StreamingResponse(
                    command_stream(), 
                    media_type="text/event-stream",
                    headers={"Content-Type": "text/event-stream"}
                )
            else:
                return JSONResponse({
                    "message": {"role": "assistant", "content": response_text}
                })
        
        # Get tool recommendations and determine thinking mode
        tool_recommendations = get_tool_recommendations(user_message)
        workflow_recommendations = get_workflow_recommendations(user_message)
        
        # Use simple pattern matching to determine thinking mode
        from core.orchestrator import is_title_generation_request, should_use_no_think
        
        # Skip thinking for title generation requests
        if is_title_generation_request(user_message):
            use_no_think = True
        else:
            # Use simple pattern matching
            use_no_think = should_use_no_think(user_message)
        
        # Add thinking mode prefix to user message
        if use_no_think:
            thinking_mode = "/no_think"
            modified_user_message = f"/no_think {user_message}"
        else:
            thinking_mode = "default thinking"
            modified_user_message = user_message  # Default thinking on
        
        # Update the last message with thinking mode directive
        modified_messages = messages.copy()
        if modified_messages and modified_messages[-1].get("role") == "user":
            modified_messages[-1] = {
                "role": "user", 
                "content": modified_user_message
            }
        
        logger.info(f"🧠 Using {thinking_mode} mode for: '{user_message}'")
        logger.info(f"💡 Tool recommendations: {tool_recommendations}")
        logger.info(f"🔄 Workflow recommendations: {workflow_recommendations}")
        
        # Execute agent request via orchestrator (unified path)
        try:
            agent_response = await execute_agent_request(modified_messages, modified_user_message, requested_model_name, tool_recommendations)
            
            if stream:
                async def agent_stream():
                    # Stream the final answer word-by-word
                    for word in agent_response.split():
                        stream_chunk = {
                            "id": "chatcmpl-agent",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": requested_model_name,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": word + " "},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(stream_chunk)}\n\n"
                        await asyncio.sleep(0.05)
                    
                    # Send final chunk
                    final_chunk = {
                        "id": "chatcmpl-agent",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }]
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                return StreamingResponse(
                    agent_stream(), 
                    media_type="text/event-stream",
                    headers={"Content-Type": "text/event-stream"}
                )
            else:
                return JSONResponse({
                    "id": "chatcmpl-agent",
                    "object": "chat.completion", 
                    "created": int(time.time()),
                    "model": requested_model_name,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": agent_response},
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": len(user_message) // 4,
                        "completion_tokens": len(agent_response) // 4,
                        "total_tokens": (len(user_message) + len(agent_response)) // 4
                    }
                })
                
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# ===== ADDITIONAL ENDPOINTS =====

@router.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint"""
    return {
        "data": [
            {
                "id": DEFAULT_MODEL,
                "object": "model",
                "created": 1677610602,
                "owned_by": "Advanced MCP Server"
            }
        ]
    }

@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint"""
    # Delegate to the main chat endpoint
    return await chat_proxy(request)

# --- START: Added Legacy Endpoint ---
@router.post("/v1/completions")
async def legacy_completions(request: Request):
    """
    OpenAI-compatible legacy completions endpoint.
    This acts as an alias for the chat completions endpoint.
    """
    # Delegate to the main chat endpoint
    return await chat_proxy(request)
# --- END: Added Legacy Endpoint ---

@router.get("/api/context-status") 
async def context_status():
    """Get current context configuration and status"""
    # This would show context limits, usage, etc.
    # For now, return basic info
    return {
        "model": DEFAULT_MODEL,
        "context_limit": "Auto-detected from Ollama",
        "compaction_enabled": True,
        "status": "operational"
    }