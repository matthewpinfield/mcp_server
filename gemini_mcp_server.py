#!/usr/bin/env python3
# MCP Server - LANGCHAIN Integration - Linter Fix for args_schema (v2) - Corrected Output

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx 
from httpx_sse import aconnect_sse 
import logging
import json
import asyncio
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub
from langchain_core.tools import BaseTool as LangchainBaseTool, ArgsSchema
from pydantic import BaseModel, Field 

from typing import List, Dict, Any, Union, Optional, AsyncGenerator, Type 
from contextlib import asynccontextmanager

# --- Configuration (Environment Variables) ---
RAG_SERVER_ENDPOINT = os.getenv("RAG_SERVER_ENDPOINT", "http://localhost:8008/custom_rag_stuff")
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434") 
OLLAMA_OPENAI_BASE = os.getenv("OLLAMA_OPENAI_BASE", "http://localhost:11434/v1") 
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen3:8b") 

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "3")) 
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60")) 
LANGCHAIN_AGENT_TIMEOUT = int(os.getenv("LANGCHAIN_AGENT_TIMEOUT", "180")) 
DIRECT_OLLAMA_TIMEOUT = int(os.getenv("DIRECT_OLLAMA_TIMEOUT", "90"))

DEFAULT_RAG_KEYWORDS = "flutter,dart,widget,state management,navigation,routing,buildrunner,firebase,api,documentation,code example,debug,error,fix,how to,what is,explain"
RAG_KEYWORDS_STR = os.getenv("MCP_RAG_KEYWORDS", DEFAULT_RAG_KEYWORDS)
RAG_KEYWORDS = [keyword.strip().lower() for keyword in RAG_KEYWORDS_STR.split(',') if keyword.strip()]

DEBUG_VERBOSE = os.getenv("DEBUG_VERBOSE", "False").lower() == "true"

LOG_LEVEL = logging.DEBUG if DEBUG_VERBOSE else logging.INFO
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if DEBUG_VERBOSE: logger.info("DEBUG_VERBOSE mode is ON.")
logger.info(f"Default Model: {DEFAULT_MODEL}")
logger.info(f"RAG Keywords for Langchain Agent: {RAG_KEYWORDS}")

executor: Optional[ThreadPoolExecutor] = None
shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global executor
    logger.info("MCP Server with Langchain starting up...")
    app.state.loop = asyncio.get_running_loop() 
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="LangchainTool")
    logger.info("MCP Server with Langchain started successfully.")
    yield
    logger.info("MCP Server with Langchain shutting down...")
    shutdown_event.set() 
    if executor:
        logger.info("Shutting down ThreadPoolExecutor for Langchain tools...")
        executor.shutdown(wait=False)
        start_time = time.time()
        active_threads_count = len(executor._threads) if hasattr(executor, '_threads') and executor._threads else 0
        grace_period = 15 
        while active_threads_count > 0 and (time.time() - start_time) < grace_period:
            await asyncio.sleep(0.5)
            if hasattr(executor, '_threads') and executor._threads:
                active_threads_count = sum(1 for t in executor._threads if t.is_alive())
            else: active_threads_count = 0
        if active_threads_count > 0: logger.warning(f"{active_threads_count} agent threads still active.")
        else: logger.info("All agent threads appear to have completed.")
    logger.info("MCP Server with Langchain shutdown process complete.")

app = FastAPI(title="MCP Server with Langchain", lifespan=lifespan)

def os_signal_handler(signum, frame):
    logger.info(f"Received OS signal {signum}, setting shutdown_event...")
    shutdown_event.set()

signal.signal(signal.SIGINT, os_signal_handler)
signal.signal(signal.SIGTERM, os_signal_handler)

class QueryFlutterDocsSchema(BaseModel): # This still inherits from pydantic_v1.BaseModel
    query: str = Field(description="The technical question about Flutter or Dart for documentation lookup.")

class LangchainFlutterDocTool(LangchainBaseTool):
    name: str = "query_flutter_dart_documentation"
    description: str = "Queries a knowledge base of Flutter/Dart documentation to answer technical questions about Flutter or Dart. Use this for specific Flutter/Dart coding questions, error explanations, or finding documentation."
    # The type hint MUST be Type[BaseModel] to be compatible with the Pydantic class being assigned.
    args_schema: Type[BaseModel] = QueryFlutterDocsSchema # type: ignore

    def _run(self, query: str) -> str:
        logger.info(f"Langchain RAG Tool: Received query: '{query}'")
        try:
            import requests
            response = requests.post(RAG_SERVER_ENDPOINT, json={"fullInput": query}, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            try:
                rag_json = response.json()
                if isinstance(rag_json, dict):
                    if "answer" in rag_json: result_text = rag_json["answer"]
                    elif "text" in rag_json: result_text = rag_json["text"]
                    elif "content" in rag_json: result_text = rag_json["content"]
                    elif "retrieved_documentation_text" in rag_json: result_text = rag_json["retrieved_documentation_text"]
                    else: result_text = json.dumps(rag_json)
                else: result_text = json.dumps(rag_json)
            except ValueError: result_text = response.text
            logger.info(f"Langchain RAG Tool: Successfully retrieved documentation (length: {len(result_text)}).")
            return f"Documentation found for query '{query}':\n{result_text}"
        except Exception as e:
            logger.error(f"Langchain RAG Tool: Error: {e}", exc_info=DEBUG_VERBOSE)
            return f"Error during RAG tool execution: {str(e)}"

    async def _arun(self, query: str) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, query)

def strip_thoughts_from_content(content_to_process: str) -> str:
    final_speakable_content = ""
    while True:
        start_think_idx = content_to_process.find('<think>')
        end_think_idx = content_to_process.find('</think>')
        if start_think_idx != -1 and end_think_idx != -1 and start_think_idx < end_think_idx:
            final_speakable_content += content_to_process[:start_think_idx]
            if DEBUG_VERBOSE:
                thought = content_to_process[start_think_idx : end_think_idx + len('</think>')]
                logger.debug(f"Stripping thought: {thought[:100]}...")
            content_to_process = content_to_process[end_think_idx + len('</think>'):]
        elif start_think_idx != -1 and end_think_idx == -1 and len(content_to_process) > start_think_idx + 7: 
            final_speakable_content += content_to_process[:start_think_idx]
            if DEBUG_VERBOSE: logger.debug(f"Partial thought start detected, content before: '{final_speakable_content}', buffering rest: '{content_to_process[start_think_idx:100]}'")
            content_to_process = "" 
            break
        else: 
            final_speakable_content += content_to_process
            break
    return final_speakable_content.strip()


async def stream_langchain_agent_response(agent_executor_instance: AgentExecutor, input_messages: List[Dict[str, str]], model_name_used: str, request_id_prefix_str: str):
    """
    Invokes the ReAct agent, gets the complete final answer, and then streams
    it back to the client.
    """
    lc_messages_history = []
    user_input_for_agent = ""

    for msg in input_messages:
        if msg["role"] == "user":
            lc_messages_history.append(HumanMessage(content=msg["content"]))
            user_input_for_agent = msg["content"]
        elif msg["role"] == "assistant":
            lc_messages_history.append(AIMessage(content=msg["content"]))

    # For ReAct, it's more reliable to pass the full history.
    agent_input_data = {"input": user_input_for_agent, "chat_history": lc_messages_history}

    try:
        logger.info(f"Invoking ReAct agent for query: '{user_input_for_agent}'")
        # Use .ainvoke() to get the final result reliably.
        result = await agent_executor_instance.ainvoke(agent_input_data)
        final_answer = result.get("output", "[Agent did not return a final answer.]")
        logger.info(f"ReAct agent finished. Final Answer: {final_answer}")

        # Stream the final answer word-by-word for a good user experience.
        for word in final_answer.split():
            sse_chunk = {
                "id": f"{request_id_prefix_str}-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model_name_used,
                "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None }]
            }
            yield f"data: {json.dumps(sse_chunk)}\n\n"
            await asyncio.sleep(0.05)

        # Send the final DONE message.
        final_sse_chunk = {
            "id": f"{request_id_prefix_str}-final",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name_used,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
        }
        yield f"data: {json.dumps(final_sse_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Langchain Agent Path Streaming ({request_id_prefix_str}): Error during agent execution: {e}", exc_info=True)
        error_message = f"[Agent Error: {e}]"
        error_chunk = {"choices": [{"delta": {"content": error_message}, "finish_reason": "error"}]}
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"

async def stream_direct_from_ollama(messages: List[Dict[str, str]], model_name: str, request_id_prefix: str):
    api_url = f"{OLLAMA_OPENAI_BASE}/chat/completions"
    payload = { "model": model_name, "messages": messages, "stream": True, "temperature": float(os.getenv("LLM_TEMPERATURE_DIRECT", "0.7"))}
    logger.info(f"Direct Path ({request_id_prefix}): Streaming from Ollama model '{model_name}'. API: {api_url}")

    chunk_count = 0
    has_sent_content = False
    accumulated_content_for_current_thought_block = "" 
    try:
        async with aconnect_sse(httpx.AsyncClient(timeout=DIRECT_OLLAMA_TIMEOUT), "POST", api_url, json=payload) as event_source:
            async for sse_event in event_source.aiter_sse():
                if shutdown_event.is_set(): break
                if sse_event.event == "message":
                    if sse_event.data.strip() == "[DONE]": break
                    try:
                        chunk_data = json.loads(sse_event.data)
                        delta_content_raw = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content")
                        finish_reason_ollama = chunk_data.get("choices", [{}])[0].get("finish_reason")
                        if delta_content_raw is not None:
                            content_to_process = delta_content_raw
                            accumulated_content_for_current_thought_block += content_to_process
                            temp_speakable_buffer = ""
                            while True:
                                start_think_idx = accumulated_content_for_current_thought_block.find('<think>')
                                end_think_idx = accumulated_content_for_current_thought_block.find('</think>')
                                if start_think_idx != -1 and end_think_idx != -1 and start_think_idx < end_think_idx:
                                    temp_speakable_buffer += accumulated_content_for_current_thought_block[:start_think_idx] 
                                    if DEBUG_VERBOSE: logger.debug(f"Direct Path ({request_id_prefix}): Stripping thought: {accumulated_content_for_current_thought_block[start_think_idx : end_think_idx + len('</think>')][:100]}")
                                    accumulated_content_for_current_thought_block = accumulated_content_for_current_thought_block[end_think_idx + len('</think>'):]
                                elif start_think_idx != -1 and end_think_idx == -1 :
                                    temp_speakable_buffer += accumulated_content_for_current_thought_block[:start_think_idx]
                                    accumulated_content_for_current_thought_block = accumulated_content_for_current_thought_block[start_think_idx:]
                                    break 
                                else:
                                    temp_speakable_buffer += accumulated_content_for_current_thought_block
                                    accumulated_content_for_current_thought_block = ""
                                    break
                            final_speakable_content = temp_speakable_buffer 
                            if final_speakable_content:
                                chunk_count += 1
                                has_sent_content = True
                                sse_chunk = {"id": f"{request_id_prefix}-{chunk_count}", "object": "chat.completion.chunk", "created": int(time.time()), "model": model_name, "choices": [{"index": 0, "delta": {"content": final_speakable_content}, "finish_reason": None }]}
                                yield f"data: {json.dumps(sse_chunk)}\n\n"
                                await asyncio.sleep(0.01)
                        if finish_reason_ollama: 
                            if accumulated_content_for_current_thought_block.strip() and not accumulated_content_for_current_thought_block.strip().startswith("<think"):
                                yield f"data: {json.dumps({'id': f'{request_id_prefix}-{chunk_count+1}', 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model_name, 'choices': [{'index': 0, 'delta': {'content': accumulated_content_for_current_thought_block.strip()}, 'finish_reason': None }]})}\n\n"
                            break 
                    except Exception as e_parse: logger.error(f"Direct Path ({request_id_prefix}): Error parsing Ollama line: {e_parse} - Data: '{sse_event.data}'")
    except Exception as e_stream: logger.error(f"Direct Path ({request_id_prefix}): Unexpected error: {e_stream}", exc_info=DEBUG_VERBOSE)

    if not has_sent_content and chunk_count == 0: logger.warning(f"Direct Path ({request_id_prefix}): No content streamed.")
    final_sse_chunk = {"id": f"{request_id_prefix}-final", "object": "chat.completion.chunk", "created": int(time.time()), "model": model_name, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop" }]}
    yield f"data: {json.dumps(final_sse_chunk)}\n\n"
    yield "data: [DONE]\n\n"
    logger.info(f"Direct Path ({request_id_prefix}): Streamed {chunk_count} direct chunks. Sent DONE.")

@app.post("/api/chat")
async def chat_proxy(request: Request):
    try:
        request_body = await request.json()
        requested_model_name = request_body.get('model', DEFAULT_MODEL) 
        messages = request_body.get('messages', []) 
        if not messages: raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
        logger.info(f"Chat Request: Model='{requested_model_name}', Msgs={len(messages)}")
        last_user_message_content = ""
        if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
            content = messages[-1].get("content")
            if isinstance(content, str): last_user_message_content = content.lower()
        
        # Check for Flutter keywords but disable broken Langchain agent
        use_langchain_agent = False # Default to the direct path
        if RAG_KEYWORDS:
            for keyword in RAG_KEYWORDS:
                if keyword in last_user_message_content:
                    logger.info(f"Flutter keyword '{keyword}' found. Routing to Langchain RAG Agent.")
                    use_langchain_agent = True # ENABLE the agent path
                    break # Stop searching once a keyword is found
        
        request_id_base = int(time.time())

        if use_langchain_agent:
            logger.info("Chat Path: Using Langchain Agent.")
            agent_llm_model = requested_model_name 
            
            llm = ChatOllama(
                model=agent_llm_model, 
                base_url=OLLAMA_API_BASE, 
                temperature=float(os.getenv("LLM_TEMPERATURE_AGENT", "0.7"))
            )
            tools = [LangchainFlutterDocTool()]
                        # This is a standard, battle-tested prompt for ReAct agents.
            # It instructs the model to use the "Thought/Action/Action Input/Observation" format.
            prompt = hub.pull("hwchase17/react")
            
            # This creates an agent compatible with the ReAct prompt and base models.
            agent = create_react_agent(llm, tools, prompt)
            agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors="Check messages and try to recover, or output the parsing error directly to the user.")
            
            return StreamingResponse( 
                stream_langchain_agent_response(agent_executor, messages, agent_llm_model, f"chatcmpl-agent-{request_id_base}"), 
                media_type="text/event-stream", 
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*", "X-Accel-Buffering": "no"}
            )
        else:
            logger.info(f"Chat Path: No RAG keywords. Using Direct Ollama path with model '{requested_model_name}'.")
            return StreamingResponse( 
                stream_direct_from_ollama(messages, requested_model_name, f"chatcmpl-direct-{request_id_base}"), 
                media_type="text/event-stream", 
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*", "X-Accel-Buffering": "no"}
            )
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Outer chat endpoint error: {e}", exc_info=DEBUG_VERBOSE)
        return JSONResponse(status_code=500, content={"detail": f"Chat processing failed: {str(e)}"})

# --- OpenAI Compatible Endpoints ---
@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
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
            logger.error(f"Models endpoint error: {e}", exc_info=DEBUG_VERBOSE)
            raise HTTPException(status_code=502, detail="Failed to get models")

@app.post("/v1/chat/completions")
async def chat_completions_v1(request: Request):
    """OpenAI-compatible chat completions endpoint"""
    return await chat_proxy(request)

# --- Proxy Endpoints & Health ---
@app.get("/api/tags")
async def tags_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if DEBUG_VERBOSE: logger.debug(f"Proxying /api/tags to {OLLAMA_API_BASE}/api/tags")
            response = await client.get(f"{OLLAMA_API_BASE}/api/tags") 
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logger.error(f"Tags proxy error: {e}", exc_info=DEBUG_VERBOSE)
            raise HTTPException(status_code=502, detail="Failed to get model tags from Ollama")

@app.get("/api/ps")
async def ps_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if DEBUG_VERBOSE: logger.debug(f"Proxying /api/ps to {OLLAMA_API_BASE}/api/ps")
            response = await client.get(f"{OLLAMA_API_BASE}/api/ps") 
            response.raise_for_status()
            return JSONResponse(content=response.json() if response.content else {"models": []})
        except Exception as e:
            logger.error(f"Process status proxy error: {e}", exc_info=DEBUG_VERBOSE)
            return JSONResponse(content={"models": []}) 

@app.get("/api/version")
async def version_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if DEBUG_VERBOSE: logger.debug(f"Proxying /api/version to {OLLAMA_API_BASE}/api/version")
            response = await client.get(f"{OLLAMA_API_BASE}/api/version") 
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logger.error(f"Version proxy error: {e}", exc_info=DEBUG_VERBOSE)
            return JSONResponse(content={"version": "unknown"})

@app.get("/health")
async def health():
    ollama_healthy = False
    ollama_target_for_health = OLLAMA_API_BASE 
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(ollama_target_for_health) 
            ollama_healthy = response.status_code == 200
    except Exception: pass
    return {"status": "healthy" if ollama_healthy else "degraded", "timestamp": time.time(), 
            "default_model": DEFAULT_MODEL, 
            "ollama_status": "healthy" if ollama_healthy else "unreachable",
            "rag_keywords_count": len(RAG_KEYWORDS), 
            "debug_verbose": DEBUG_VERBOSE
           }

if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8012"))
    reload_enabled = os.getenv("MCP_RELOAD", "False").lower() == "true"
    uvicorn_log_level = logging.getLevelName(LOG_LEVEL).lower()
    logger.info(f"Starting Langchain MCP Server on http://0.0.0.0:{port}")
    uvicorn.run("__main__:app", host="0.0.0.0", port=port, log_level=uvicorn_log_level, reload=reload_enabled)