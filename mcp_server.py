#!/usr/bin/env python3
# /mnt/caseSSD/mcp_server_project/mcp_server.py

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import logging
import json
import asyncio
import threading
import queue
import requests
import time
import re # For a more robust stripper if needed
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool
from typing import List, Dict, Any, Union

# --- Configuration ---
RAG_SERVER_ENDPOINT = "http://localhost:8008/custom_rag_stuff"
OLLAMA_API_BASE_FOR_PROXY = "http://localhost:11434"
OLLAMA_QWEN_BASE_FOR_AGENT = "http://localhost:11434/v1" # OpenAI-compatible endpoint

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s %(threadName)s - %(message)s')

app = FastAPI(title="Unified MCP Orchestrator")

# --- FlutterDocTool (remains the same as your last provided version) ---
@register_tool('query_flutter_dart_docs')
class FlutterDocTool(BaseTool):
    name = 'query_flutter_dart_docs'
    description = 'Queries a knowledge base of Flutter/Dart documentation for technical questions. Use this for specific Flutter/Dart coding, API, or framework questions.'
    parameters = [{'name': 'query', 'type': 'string', 'description': 'The technical question about Flutter or Dart. Be specific.', 'required': True}]
    def call(self, params: Union[str, Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        try:
            logging.info(f"TOOL_CALL: FlutterDocTool received params: {params}")
            if isinstance(params, str):
                try: params_dict = json.loads(params)
                except json.JSONDecodeError:
                    logging.error(f"TOOL_CALL_ERROR: Could not parse params string: {params}"); return {'error': 'Invalid JSON format for parameters.'}
            else: params_dict = params
            query = params_dict.get('query')
            if not query: logging.error("TOOL_CALL_ERROR: 'query' parameter is missing."); return {'error': 'The "query" parameter is missing.'}
            logging.info(f"TOOL_CALL: Making HTTP POST to RAG server {RAG_SERVER_ENDPOINT} with query: {query}")
            response = requests.post(RAG_SERVER_ENDPOINT, json={"fullInput": query}, timeout=120)
            response.raise_for_status()
            rag_content = response.text
            logging.debug(f"TOOL_CALL: RAG server response raw text: {rag_content[:200]}...")
            tool_result = {'retrieved_documentation': rag_content} # Agent expects a dict
            logging.info(f"TOOL_CALL: FlutterDocTool returning to agent: {str(tool_result)[:200]}...")
            return tool_result
        except requests.exceptions.HTTPError as http_err:
            err_resp_text = getattr(http_err.response, 'text', 'N/A')
            logging.error(f"TOOL_CALL_ERROR: HTTP error: {http_err} - Response: {err_resp_text}", exc_info=True)
            return {'error': f'HTTP error calling RAG server: {str(http_err)} - {err_resp_text}'}
        except Exception as e:
            logging.error(f"TOOL_CALL_ERROR: Unexpected error: {e}", exc_info=True)
            return {'error': f'Unexpected error in RAG tool: {str(e)}'}

# --- Main Chat Endpoint ---
@app.post("/api/chat")
async def chat_endpoint_with_search_findings(request: Request):
    try:
        request_body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")

    model_name = request_body.get('model', 'qwen3:8b') # Your target model in Ollama
    messages = request_body.get('messages', [])
    # stream_requested = request_body.get('stream', True) # Assuming streaming

    if not messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty.")

    response_queue = queue.Queue()
    request_id_base = f"chatcmpl-{int(time.time())}" 

    def run_agent_in_thread():
        try:
            # Based on search results (Qwen-Agent GitHub examples, Hugging Face Qwen3 docs)
            # for passing `enable_thinking` to an OpenAI-compatible endpoint via Qwen-Agent.
            llm_config = {
                'model': model_name,  # This should be the model name Ollama recognizes
                'model_server': OLLAMA_QWEN_BASE_FOR_AGENT, # e.g., http://localhost:11434/v1
                'api_key': 'EMPTY', # Standard for local Ollama
                'generate_cfg': {
                    'temperature': 0.7, # Example generation parameter
                    # For OpenAI-compatible endpoints, custom params often go in 'extra_body'.
                    # The Qwen-Agent examples suggest 'chat_template_kwargs' inside 'extra_body'
                    # might be how it passes 'enable_thinking' to the underlying template processor
                    # when the model is served via an OAI endpoint.
                    'extra_body': {
                        # This is the most promising structure found in Qwen-Agent examples for OAI endpoints
                        'chat_template_kwargs': {'enable_thinking': False},
                        # Some OAI servers might also pick up parameters directly in extra_body,
                        # or other specific keys. This might require experimentation if the above doesn't work.
                        # For example, directly:
                        # 'enable_thinking': False, # (Less likely to be picked up directly by Ollama this way via Qwen-Agent for the Qwen3 model's internal thinking)
                        # Or, the Ollama OpenAI endpoint might have its own way to specify this if it supports it for Qwen models.
                    }
                }
            }
            # As a simpler alternative if the above extra_body is too complex or not working:
            # If Ollama's /v1/chat/completions endpoint *directly* supports an 'enable_thinking' field
            # in its JSON payload for Qwen models, Qwen-Agent might pass it through if it's in 'generate_cfg'.
            # llm_config_alternative = {
            #     'model': model_name,
            #     'model_server': OLLAMA_QWEN_BASE_FOR_AGENT,
            #     'api_key': 'EMPTY',
            #     'generate_cfg': {
            #         'enable_thinking': False, # Try this if 'extra_body' doesn't seem to work
            #         'temperature': 0.7
            #     }
            # }
            # Use llm_config for now.

            tools_for_agent: List[Union[str, BaseTool]] = [FlutterDocTool()]
            bot = Assistant(llm=llm_config, function_list=tools_for_agent, name="ConfiguredAssistant")

            logging.info(f"AGENT_THREAD: Starting Qwen Agent. Attempting to set 'enable_thinking: False'. Config: {llm_config}")
            
            for agent_chunk in bot.run(messages=messages):
                logging.debug(f"AGENT_THREAD: Agent yielded: {agent_chunk}")
                response_queue.put(agent_chunk)
            
            response_queue.put(None) 
            logging.info("AGENT_THREAD: Agent finished.")

        except Exception as e:
            logging.error(f"AGENT_THREAD: Error: {e}", exc_info=True)
            response_queue.put({"error": str(e)})
            response_queue.put(None)

    thread = threading.Thread(target=run_agent_in_thread, name="QwenAgentThread")
    thread.start()

    async def sse_streamer_simplified():
        # Goal: Show "Thinking..." ONCE if initial response is delayed.
        # Then, stream content, stripping any residual <think> tags.
        initial_placeholder_sent = False
        request_chunk_counter = 0

        while True:
            try:
                agent_output_item = None
                try:
                    agent_output_item = response_queue.get_nowait()
                except queue.Empty:
                    if not initial_placeholder_sent:
                        # No chunk yet, and placeholder not sent. Check if it's been a moment.
                        # This is a brief pause to see if a chunk arrives immediately.
                        await asyncio.sleep(0.1) # Very short wait
                        if response_queue.empty() and not initial_placeholder_sent: # Check again
                            logging.info("STREAMER: Initial response not yet received, sending placeholder.")
                            placeholder_delta = {"content": "🤔 Processing..."}
                            placeholder_sse = {
                                "id": f"{request_id_base}-{request_chunk_counter}", "object": "chat.completion.chunk",
                                "created": int(time.time()), "model": model_name,
                                "choices": [{"index": 0, "delta": placeholder_delta, "finish_reason": None}]
                            }
                            yield f"data: {json.dumps(placeholder_sse)}\n\n"
                            initial_placeholder_sent = True
                            request_chunk_counter += 1
                    
                    await asyncio.sleep(0.05) # Standard wait if queue is empty
                    continue # Go back to try .get_nowait()

                # If we get here, a chunk was received (or placeholder was already sent)
                if not initial_placeholder_sent and not response_queue.empty(): # A chunk arrived before placeholder timeout
                    pass # We will process it below without sending the generic placeholder

                if agent_output_item is None: # End of stream
                    logging.info("STREAMER: Received None. Ending stream.")
                    break

                # Handle error dict from agent
                if isinstance(agent_output_item, dict) and "error" in agent_output_item:
                    logging.error(f"STREAMER: Error from agent: {agent_output_item['error']}")
                    error_delta = {"content": f"\n[Agent Error: {agent_output_item['error']}]"}
                    error_sse = {"id": f"{request_id_base}-{request_chunk_counter}", "object": "chat.completion.chunk",
                                 "created": int(time.time()), "model": model_name,
                                 "choices": [{"index": 0, "delta": error_delta, "finish_reason": "error"}]}
                    yield f"data: {json.dumps(error_sse)}\n\n"
                    request_chunk_counter +=1
                    continue

                # Process normal agent output (expecting list of dicts)
                if isinstance(agent_output_item, list) and len(agent_output_item) > 0:
                    chunk_data = agent_output_item[0]
                    if isinstance(chunk_data, dict):
                        content_to_send = chunk_data.get('content', '')
                        
                        if isinstance(content_to_send, str) and content_to_send:
                            # Fallback: Strip any <think> tags if 'enable_thinking:False' wasn't fully effective
                            # or if the agent framework itself adds them for tool use structure.
                            # A simple non-greedy regex for <think>...</think>
                            # This should handle simple, non-nested cases primarily.
                            cleaned_content = re.sub(r"<think>.*?</think>", "", content_to_send, flags=re.DOTALL)
                            # Remove any solitary <think> if </think> was missing or for other variants
                            cleaned_content = cleaned_content.replace("<think>", "").strip()

                            if cleaned_content:
                                delta = {"content": cleaned_content}
                                sse_chunk = {"id": f"{request_id_base}-{request_chunk_counter}", "object": "chat.completion.chunk",
                                             "created": int(time.time()), "model": model_name,
                                             "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
                                yield f"data: {json.dumps(sse_chunk)}\n\n"
                                request_chunk_counter += 1
                                initial_placeholder_sent = True # Mark that we've started sending real data

                        # Handle structured tool_calls if they are separate from 'content'
                        # (This part is simplified; OpenAI tool calls are a list of objects)
                        if chunk_data.get('tool_calls'):
                            logging.info(f"STREAMER: Agent provided tool_calls: {chunk_data['tool_calls']}")
                            tool_call_delta = {"tool_calls": chunk_data['tool_calls']} # OpenAI structure
                            sse_tool_chunk = {"id": f"{request_id_base}-{request_chunk_counter}", "object": "chat.completion.chunk",
                                               "created": int(time.time()), "model": model_name,
                                               "choices": [{"index": 0, "delta": tool_call_delta, "finish_reason": None}]} # Could be 'tool_calls'
                            yield f"data: {json.dumps(sse_tool_chunk)}\n\n"
                            request_chunk_counter += 1
                            initial_placeholder_sent = True
                else:
                    logging.warning(f"STREAMER: Unexpected agent output format: {agent_output_item}")
            
            except Exception as e: # Catch errors in the streamer loop itself
                logging.error(f"STREAMER: Loop Error: {e}", exc_info=True)
                try:
                    err_delta = {"content": f"\n[Streamer Loop Error: {str(e)}]"}
                    err_sse = {"id": f"{request_id_base}-{request_chunk_counter}", "object": "chat.completion.chunk",
                               "created": int(time.time()), "model": model_name,
                               "choices": [{"index": 0, "delta": err_delta, "finish_reason": "error"}]}
                    yield f"data: {json.dumps(err_sse)}\n\n"
                except: pass # Suppress errors during error reporting
                break # Exit loop on streamer error
        
        # Final "stop" chunk for SSE
        logging.info("STREAMER: Sending final [DONE] marker.")
        done_delta = {}
        done_sse = {"id": f"{request_id_base}-{request_chunk_counter}", "object": "chat.completion.chunk",
                    "created": int(time.time()), "model": model_name,
                    "choices": [{"index": 0, "delta": done_delta, "finish_reason": "stop"}]}
        yield f"data: {json.dumps(done_sse)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse_streamer_simplified(), media_type="text/event-stream")


# --- Other Endpoints (Unchanged, ensure OLLAMA_API_BASE_FOR_PROXY is used) ---
@app.get("/api/tags")
async def tags_proxy():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{OLLAMA_API_BASE_FOR_PROXY}/api/tags")
        response.raise_for_status(); return JSONResponse(content=response.json())
@app.get("/api/ps")
async def ps_proxy():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{OLLAMA_API_BASE_FOR_PROXY}/api/ps")
        response.raise_for_status(); return JSONResponse(content=response.json())
@app.get("/api/version")
async def version_proxy():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{OLLAMA_API_BASE_FOR_PROXY}/api/version")
        response.raise_for_status(); return JSONResponse(content=response.json())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8009, log_level="info")