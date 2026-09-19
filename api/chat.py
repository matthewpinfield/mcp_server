#!/usr/bin/env python3
"""
Chat API endpoint for Advanced MCP Server - Version 2
Main chat_proxy endpoint with simplified Qwen3 integration
"""

import json
import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from config import DEFAULT_MODEL
from core.orchestrator import orchestrate_request

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
        requested_model_name = request_body.get("model", DEFAULT_MODEL)
        messages = request_body.get("messages", [])
        stream = request_body.get("stream", True)
       

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
            

        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        logger.info(
            f"Chat Request: Model='{requested_model_name}', Msgs={len(messages)}"
        )

        if user_message.strip().startswith("/"):
            # Route slash commands through orchestrator for proper routing
            response_text = ""
            async for chunk in orchestrate_request(messages, user_message, requested_model_name):
                response_text += chunk

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

        conversation_id = request.headers.get("X-Conversation-ID")

        if stream:
            async def agent_stream():
                async for chunk in orchestrate_request(
                    messages, user_message, requested_model_name, conversation_id
                ):
                    formatted_chunk = format_response_for_continue(chunk)
                    if not formatted_chunk:
                        continue
                        
                    stream_chunk = {
                        "id": "chatcmpl-agent",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": formatted_chunk},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(stream_chunk)}\n\n"

                final_chunk = {
                    "id": "chatcmpl-agent",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": requested_model_name,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                agent_stream(),
                media_type="text/event-stream",
                headers={"Content-Type": "text/event-stream"},
            )
        else:
            agent_response = ""
            async for chunk in orchestrate_request(
                messages, user_message, requested_model_name, conversation_id
            ):
                agent_response += chunk

            formatted_response = format_response_for_continue(agent_response)
            
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
                        "total_tokens": (len(user_message) + len(agent_response)) // 4,
                    },
                }
            )

       

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Chat endpoint error: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
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
