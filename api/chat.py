#!/usr/bin/env python3
"""
Chat API endpoint for Advanced MCP Server - Version 2
Main chat_proxy endpoint with simplified Qwen3 integration
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import (
    DEFAULT_MODEL,
    DEFAULT_SLASH_COMMANDS,
    LANGCHAIN_AGENT_TIMEOUT,
    OLLAMA_API_BASE,
)
from core.orchestrator import orchestrate_request

# Import all tools
from tools import (
    LangchainCodeSearchTool,
    LangchainFlutterDocTool,
    LangchainGitBranchTool,
    LangchainGitCommitTool,
    LangchainGitDiffTool,
    LangchainGitLogTool,
    LangchainGitStatusTool,
    LangchainMemorySearchTool,
    LangchainMemoryStatsTool,
    LangchainWebSearchTool,
    MultiLanguageSandboxTool,
    SandboxStatsTool,
)

logger = logging.getLogger(__name__)


def format_response_for_continue(response: str) -> str:
    """
    Format response for Continue IDE - return standard markdown unchanged
    """
    # Return the agent's standard markdown unchanged - Continue IDE handles it properly
    return response


router = APIRouter()


# ===== UNIFIED AGENT PATH WITH THINKING MODE =====

# ===== MAIN CHAT ENDPOINT =====


@router.post("/api/chat")
async def chat_proxy(request: Request):
    try:
        request_body = await request.json()
        logger.info(f"TWINNY DEBUG - Full request body: {json.dumps(request_body, indent=2)}")
        requested_model_name = request_body.get("model", DEFAULT_MODEL)
        messages = request_body.get("messages", [])
        stream = request_body.get("stream", True)
        logger.info(f"TWINNY DEBUG - Stream mode: {stream}, Model: {requested_model_name}")

        if not messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")

        user_message = ""
        if (
            messages
            and isinstance(messages[-1], dict)
            and messages[-1].get("role") == "user"
        ):
            content = messages[-1].get("content")
            if isinstance(content, str):
                user_message = content
            elif isinstance(content, list) and content:
                # Handle Twinny's array format: [{"type": "text", "text": "content"}]
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        user_message = item.get("text", "")
                        break

        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        logger.info(
            f"Chat Request: Model='{requested_model_name}', Msgs={len(messages)}"
        )

        if user_message.strip().startswith("/"):
            parts = user_message.strip().split(" ", 1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""

            try:
                memory_tool = LangchainMemorySearchTool()
                custom_commands_result = memory_tool._run("custom_slash_commands")
                custom_commands = (
                    json.loads(custom_commands_result) if custom_commands_result else {}
                )
            except:
                custom_commands = {}

            from tools.knowledge import process_slash_command

            response_text = process_slash_command(command, args, custom_commands)

            if stream:

                async def command_stream():
                    # Send the entire command response in a single chunk
                    stream_chunk = {
                        "id": "chatcmpl-command",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": response_text},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(stream_chunk)}\n\n"

                    final_chunk = {
                        "id": "chatcmpl-command",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"

                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    command_stream(),
                    media_type="text/event-stream",
                    headers={"Content-Type": "text/event-stream"},
                )
            else:
                return JSONResponse(
                    {"message": {"role": "assistant", "content": response_text}}
                )

        try:
            conversation_id = (
                request.headers.get("X-Conversation-ID") or f"chat_{int(time.time())}"
            )
            agent_response = await orchestrate_request(
                messages, user_message, requested_model_name, conversation_id
            )

            formatted_response = format_response_for_continue(agent_response)

            if stream:

                async def agent_stream():
                    # Send the entire formatted response in a single chunk
                    # This preserves all markdown formatting, including newlines and code blocks
                    stream_chunk = {
                        "id": "chatcmpl-agent",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": formatted_response},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(stream_chunk)}\n\n"

                    # Send the final chunk indicating the end of the stream
                    final_chunk = {
                        "id": "chatcmpl-agent",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"

                    # Standard OpenAI-compatible SSE termination
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    agent_stream(),
                    media_type="text/event-stream",
                    headers={"Content-Type": "text/event-stream"},
                )
            else:
                return JSONResponse(
                    {
                        "id": "chatcmpl-agent",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": formatted_response,
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": len(user_message) // 4,
                            "completion_tokens": len(agent_response) // 4,
                            "total_tokens": (len(user_message) + len(agent_response))
                            // 4,
                        },
                    }
                )

        except Exception as e:
            logger.error(f"TWINNY DEBUG - Agent execution error: {e}")
            logger.error(f"TWINNY DEBUG - Exception type: {type(e)}")
            logger.error(f"TWINNY DEBUG - Full traceback:", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Agent execution failed: {str(e)}"
            )

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
                "owned_by": "Advanced MCP Server",
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


@router.get("/api/tags")
async def get_tags():
    """Return available models for Twinny compatibility"""
    return {
        "models": [
            {
                "name": DEFAULT_MODEL,
                "modified_at": "2025-07-22T23:00:00Z",
                "size": 18000000000,
                "digest": "0b28110b7a33"
            }
        ]
    }

@router.get("/api/context-status")
async def context_status():
    """Get current context configuration and status"""
    # This would show context limits, usage, etc.
    # For now, return basic info
    return {
        "model": DEFAULT_MODEL,
        "context_limit": "Auto-detected from Ollama",
        "compaction_enabled": True,
        "status": "operational",
    }
