#!/usr/bin/env python3
"""
High-Performance MCP Server - Optimized for <10 second responses
Bypasses Qwen-Agent overhead for simple queries, implements intelligent routing
"""

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import asyncio
import json
import time
import re
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import hashlib

# Configuration
RAG_SERVER_ENDPOINT = "http://localhost:8008/custom_rag_stuff"
OLLAMA_API_BASE = "http://localhost:11434"
OLLAMA_OPENAI_BASE = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen3:8b"

# Performance tuning
RAG_TIMEOUT = 30  # Reduced from 120
SIMPLE_QUERY_TIMEOUT = 15
CONNECTION_POOL_SIZE = 10

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Fast MCP Server")

class QueryType(Enum):
    SIMPLE_DIRECT = "simple_direct"  # Direct to Ollama (no RAG)
    RAG_REQUIRED = "rag_required"    # Needs Flutter/Dart docs
    COMPLEX_AGENT = "complex_agent"  # Needs full agent framework

@dataclass
class QueryAnalysis:
    query_type: QueryType
    confidence: float
    reason: str
    estimated_time: float

class IntelligentRouter:
    """Routes queries to the fastest appropriate handler"""
    
    # Keywords that indicate Flutter/Dart documentation is needed
    RAG_KEYWORDS = {
        'flutter', 'dart', 'widget', 'scaffold', 'material', 'cupertino',
        'stateful', 'stateless', 'build', 'context', 'pubspec', 'packages',
        'async', 'future', 'stream', 'provider', 'bloc', 'riverpod',
        'navigator', 'route', 'theme', 'animation', 'gesture'
    }
    
    # Keywords that indicate simple queries
    SIMPLE_KEYWORDS = {
        'hello', 'hi', 'help', 'what', 'how are you', 'explain', 'tell me',
        'define', 'meaning', 'example', 'simple', 'basic'
    }
    
    def analyze_query(self, messages: List[Dict]) -> QueryAnalysis:
        """Analyze query to determine optimal routing"""
        
        if not messages:
            return QueryAnalysis(QueryType.SIMPLE_DIRECT, 0.9, "Empty query", 2.0)
        
        # Get latest user message
        user_message = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_message = msg.get('content', '').lower()
                break
        
        if not user_message:
            return QueryAnalysis(QueryType.SIMPLE_DIRECT, 0.9, "No user content", 2.0)
        
        # Count relevant keywords
        rag_score = sum(1 for keyword in self.RAG_KEYWORDS if keyword in user_message)
        simple_score = sum(1 for keyword in self.SIMPLE_KEYWORDS if keyword in user_message)
        
        # Length-based heuristics
        word_count = len(user_message.split())
        
        # Decision logic
        if rag_score >= 2 or any(kw in user_message for kw in ['flutter api', 'dart documentation', 'widget example']):
            return QueryAnalysis(QueryType.RAG_REQUIRED, 0.8, f"Flutter/Dart keywords: {rag_score}", 25.0)
        
        elif rag_score == 1 and word_count > 5:
            return QueryAnalysis(QueryType.RAG_REQUIRED, 0.6, "Possible Flutter/Dart query", 25.0)
        
        elif simple_score > 0 or word_count < 10:
            return QueryAnalysis(QueryType.SIMPLE_DIRECT, 0.8, "Simple conversational query", 3.0)
        
        elif word_count > 20 or 'complex' in user_message:
            return QueryAnalysis(QueryType.COMPLEX_AGENT, 0.7, "Complex multi-step query", 45.0)
        
        else:
            return QueryAnalysis(QueryType.SIMPLE_DIRECT, 0.5, "Default to simple", 5.0)

# Global instances
router = IntelligentRouter()

# Connection pool for better performance
async_client_pool = None

@app.on_event("startup")
async def startup_event():
    global async_client_pool
    async_client_pool = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_connections=CONNECTION_POOL_SIZE, max_keepalive_connections=5)
    )
    logger.info("Fast MCP Server started with connection pooling")

@app.on_event("shutdown") 
async def shutdown_event():
    if async_client_pool:
        await async_client_pool.aclose()
    logger.info("Fast MCP Server shutdown")

class ResponseCache:
    """Simple in-memory cache for recent responses"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self.cache: Dict[str, Dict] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
    
    def _get_key(self, messages: List[Dict]) -> str:
        content = json.dumps(messages, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def get(self, messages: List[Dict]) -> Optional[str]:
        key = self._get_key(messages)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.ttl_seconds:
                logger.info(f"Cache hit for key: {key}")
                return entry['response']
            else:
                del self.cache[key]
        return None
    
    def set(self, messages: List[Dict], response: str):
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]
        
        key = self._get_key(messages)
        self.cache[key] = {
            'response': response,
            'timestamp': time.time()
        }
        logger.info(f"Cached response for key: {key}")

# Global cache
response_cache = ResponseCache()

async def handle_simple_direct(messages: List[Dict], model: str) -> AsyncGenerator[str, None]:
    """Handle simple queries directly with Ollama (no agent overhead)"""
    try:
        logger.info("Handler: Direct Ollama (bypassing agent)")
        
        # Check cache first
        cached_response = response_cache.get(messages)
        if cached_response:
            # Stream cached response word by word for natural feel
            words = cached_response.split()
            request_id = f"cached-{int(time.time())}"
            
            for i, word in enumerate(words):
                chunk = {
                    "id": f"{request_id}-{i}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": word + " " if i < len(words) - 1 else word},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.05)  # Natural typing speed
            
            # Final chunk
            final_chunk = {
                "id": f"{request_id}-final",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # Direct call to Ollama
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": 0.7,
                "num_predict": 800  # Limit for simple queries
            }
        }
        
        start_time = time.time()
        
        async with async_client_pool.stream(
            'POST', 
            f"{OLLAMA_OPENAI_BASE}/chat/completions",
            json=payload,
            timeout=SIMPLE_QUERY_TIMEOUT
        ) as response:
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Ollama error")
            
            full_response = ""
            chunk_count = 0
            
            async for chunk in response.aiter_lines():
                if chunk.startswith("data: "):
                    chunk_data = chunk[6:]  # Remove "data: " prefix
                    
                    if chunk_data == "[DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    
                    try:
                        parsed = json.loads(chunk_data)
                        if parsed.get("choices") and parsed["choices"][0].get("delta", {}).get("content"):
                            content = parsed["choices"][0]["delta"]["content"]
                            full_response += content
                        
                        yield f"data: {chunk_data}\n\n"
                        chunk_count += 1
                        
                    except json.JSONDecodeError:
                        continue
            
            # Cache the response
            if full_response:
                response_cache.set(messages, full_response)
            
            elapsed = time.time() - start_time
            logger.info(f"Direct handler completed in {elapsed:.2f}s with {chunk_count} chunks")
            
    except Exception as e:
        logger.error(f"Direct handler error: {e}")
        error_chunk = {
            "id": f"error-{int(time.time())}",
            "object": "chat.completion.chunk", 
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"Error: {str(e)}"},
                "finish_reason": "error"
            }]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

async def handle_rag_optimized(messages: List[Dict], model: str) -> AsyncGenerator[str, None]:
    """Handle RAG queries with optimized async calls"""
    try:
        logger.info("Handler: Optimized RAG (async)")
        
        # Extract query
        user_query = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_query = msg.get('content', '')
                break
        
        if not user_query:
            raise ValueError("No user query found")
        
        start_time = time.time()
        
        # Parallel RAG call - don't wait for full completion
        rag_task = asyncio.create_task(call_rag_server(user_query))
        
        # Send immediate acknowledgment
        request_id = f"rag-{int(time.time())}"
        
        ack_chunk = {
            "id": f"{request_id}-0",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": "Searching Flutter/Dart documentation..."},
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(ack_chunk)}\n\n"
        
        # Wait for RAG result with timeout
        try:
            rag_result = await asyncio.wait_for(rag_task, timeout=RAG_TIMEOUT)
            rag_time = time.time() - start_time
            logger.info(f"RAG completed in {rag_time:.2f}s")
            
        except asyncio.TimeoutError:
            logger.error("RAG timeout - falling back to direct mode")
            async for chunk in handle_simple_direct(messages, model):
                yield chunk
            return
        
        # Process RAG result and synthesize response
        if isinstance(rag_result, dict) and 'retrieved_documentation' in rag_result:
            docs = rag_result['retrieved_documentation']
        elif isinstance(rag_result, str):
            docs = rag_result
        else:
            docs = str(rag_result)
        
        # Stream the RAG response
        if docs:
            # Split into chunks for streaming
            content_chunks = split_content_for_streaming(docs)
            
            for i, chunk_content in enumerate(content_chunks):
                chunk = {
                    "id": f"{request_id}-{i+1}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk_content},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.02)  # Smooth streaming
        
        # Final chunk
        final_chunk = {
            "id": f"{request_id}-final", 
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"
        
        total_time = time.time() - start_time
        logger.info(f"Optimized RAG handler completed in {total_time:.2f}s")
        
    except Exception as e:
        logger.error(f"RAG handler error: {e}")
        error_chunk = {
            "id": f"error-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()), 
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"RAG Error: {str(e)}"},
                "finish_reason": "error"
            }]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

async def call_rag_server(query: str) -> Dict[str, Any]:
    """Optimized async call to RAG server"""
    try:
        payload = {"fullInput": query}
        
        response = await async_client_pool.post(
            RAG_SERVER_ENDPOINT,
            json=payload,
            timeout=RAG_TIMEOUT
        )
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '').lower()
        
        if 'application/json' in content_type:
            return response.json()
        else:
            return {"retrieved_documentation": response.text}
            
    except Exception as e:
        logger.error(f"RAG server error: {e}")
        raise

def split_content_for_streaming(content: str, chunk_size: int = 100) -> List[str]:
    """Split content into streamable chunks while preserving word boundaries"""
    words = content.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        current_chunk.append(word)
        current_length += len(word) + 1  # +1 for space
        
        if current_length >= chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_length = 0
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

async def handle_complex_agent(messages: List[Dict], model: str) -> AsyncGenerator[str, None]:
    """Fallback to full agent for complex queries"""
    try:
        logger.info("Handler: Full Agent (complex query)")
        
        # Import and use existing agent code
        from qwen_agent.agents import Assistant
        from qwen_agent.tools.base import BaseTool, register_tool
        
        @register_tool('query_flutter_dart_docs')
        class FastFlutterDocTool(BaseTool):
            description = 'Queries Flutter/Dart documentation quickly.'
            parameters = [{'name': 'query', 'type': 'string', 'description': 'Technical question', 'required': True}]
            
            def call(self, params, **kwargs):
                query = params.get('query') if isinstance(params, dict) else json.loads(params).get('query')
                
                import requests
                response = requests.post(RAG_SERVER_ENDPOINT, json={"fullInput": query}, timeout=RAG_TIMEOUT)
                response.raise_for_status()
                return {"retrieved_documentation": response.text}
        
        llm_config = {
            'model': model,
            'model_server': OLLAMA_OPENAI_BASE,
            'api_key': 'EMPTY',
            'generate_cfg': {'temperature': 0.7}
        }
        
        bot = Assistant(llm=llm_config, function_list=['query_flutter_dart_docs'])
        
        # Run agent in thread pool
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: list(bot.run(messages=messages)))
            
            try:
                results = await asyncio.get_event_loop().run_in_executor(None, future.result)
                
                request_id = f"agent-{int(time.time())}"
                chunk_count = 0
                
                for chunk in results:
                    if isinstance(chunk, list) and len(chunk) > 0:
                        chunk_data = chunk[0]
                        if isinstance(chunk_data, dict):
                            content = chunk_data.get('content', '')
                            if content:
                                sse_chunk = {
                                    "id": f"{request_id}-{chunk_count}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": content},
                                        "finish_reason": None
                                    }]
                                }
                                yield f"data: {json.dumps(sse_chunk)}\n\n"
                                chunk_count += 1
                                await asyncio.sleep(0.01)
                
                # Final chunk
                final_chunk = {
                    "id": f"{request_id}-final",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
                
                logger.info(f"Agent handler completed with {chunk_count} chunks")
                
            except Exception as e:
                logger.error(f"Agent execution error: {e}")
                raise
                
    except Exception as e:
        logger.error(f"Complex agent handler error: {e}")
        error_chunk = {
            "id": f"error-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"Agent Error: {str(e)}"},
                "finish_reason": "error"
            }]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

# Main endpoint with intelligent routing
@app.post("/api/chat")
async def optimized_chat(request: Request):
    try:
        request_body = await request.json()
        model = request_body.get('model', DEFAULT_MODEL)
        messages = request_body.get('messages', [])
        
        if not messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
        start_time = time.time()
        
        # Analyze query for optimal routing
        analysis = router.analyze_query(messages)
        
        logger.info(f"Query Analysis: {analysis.query_type.value} (confidence: {analysis.confidence:.2f}, estimated: {analysis.estimated_time}s) - {analysis.reason}")
        
        # Route to appropriate handler
        if analysis.query_type == QueryType.SIMPLE_DIRECT:
            response_generator = handle_simple_direct(messages, model)
        elif analysis.query_type == QueryType.RAG_REQUIRED:
            response_generator = handle_rag_optimized(messages, model)
        else:  # COMPLEX_AGENT
            response_generator = handle_complex_agent(messages, model)
        
        return StreamingResponse(
            response_generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Query-Type": analysis.query_type.value,
                "X-Estimated-Time": str(analysis.estimated_time)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

# Health and performance monitoring
@app.get("/api/performance-stats")
async def performance_stats():
    """Get performance metrics"""
    cache_stats = {
        "cache_size": len(response_cache.cache),
        "cache_hit_ratio": "N/A",  # Would need to track hits/misses
        "max_cache_size": response_cache.max_size
    }
    
    return {
        "server_type": "fast_optimized",
        "cache_stats": cache_stats,
        "connection_pool_size": CONNECTION_POOL_SIZE,
        "timeouts": {
            "rag_timeout": RAG_TIMEOUT,
            "simple_timeout": SIMPLE_QUERY_TIMEOUT
        }
    }

# Standard proxy endpoints
@app.get("/api/tags")
async def tags_proxy():
    async with async_client_pool as client:
        response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
        response.raise_for_status()
        return JSONResponse(content=response.json())

@app.get("/health")
async def health():
    return {"status": "healthy", "server": "fast_mcp", "timestamp": time.time()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8011, log_level="info")