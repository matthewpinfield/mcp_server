#!/usr/bin/env python3
"""
Background Summary Worker
========================
Processes queued summary generation jobs without blocking main server.
"""

import json
import logging
import requests
import time
import re
from tools.memory import get_redis_connection
from config import DEFAULT_MODEL, NUM_CTX

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SummaryWorker:
    def __init__(self):
        self.redis = get_redis_connection()
        
    def generate_summary(self, user_message: str, assistant_response: str) -> str:
        """Generate summary using Gemma model"""
        try:
            # Strip thinking blocks
            clean_response = assistant_response
            if "<think>" in assistant_response and "</think>" in assistant_response:
                clean_response = re.sub(r'<think>.*?</think>', '', assistant_response, flags=re.DOTALL).strip()
            
            # Direct Ollama API call - same model AND same num_ctx as the main
            # chat agent (this is a background job; a mismatched num_ctx
            # forces Ollama to reload the model to reallocate its KV cache,
            # exactly like the model-swap VRAM thrashing this avoids elsewhere).
            payload = {
                "model": DEFAULT_MODEL,
                "prompt": f"Summarize in 50 words: User: {user_message[:200]} Assistant: {clean_response[:300]}",
                "stream": False,
                "think": False,
                "options": {"num_ctx": NUM_CTX},
            }
            
            response = requests.post("http://localhost:11434/api/generate", 
                                   json=payload, timeout=30)
            
            if response.status_code == 200:
                return response.json()["response"].strip()
            else:
                return f"User: {user_message[:50]}{'...' if len(user_message) > 50 else ''}"
                
        except Exception as e:
            logger.error(f"Gemma summary failed: {e}")
            return f"User: {user_message[:50]}{'...' if len(user_message) > 50 else ''}"
    
    def process_job(self, job_data: dict):
        """Process a single summary job"""
        try:
            conversation_id = job_data["conversation_id"]
            user_message = job_data["user_message"]
            assistant_response = job_data["assistant_response"]
            
            logger.info(f"Processing summary for: {conversation_id}")
            
            # Generate summary
            summary = self.generate_summary(user_message, assistant_response)
            
            # Update memory in Redis
            redis_key = f"conversation:{conversation_id}"
            memory_data = self.redis.get(redis_key)
            
            if memory_data:
                memory = json.loads(memory_data)
                memory["summary"] = summary
                
                # Update with same TTL
                ttl = self.redis.ttl(redis_key)
                if ttl > 0:
                    self.redis.setex(redis_key, ttl, json.dumps(memory))
                else:
                    self.redis.set(redis_key, json.dumps(memory))
                
                logger.info(f"Summary updated for: {conversation_id}")
            else:
                logger.warning(f"Memory not found for: {conversation_id}")
                
        except Exception as e:
            logger.error(f"Job processing failed: {e}")
    
    def run(self):
        """Main worker loop"""
        logger.info("Summary worker started. Waiting for jobs...")
        
        while True:
            try:
                # Block until job available (BRPOP with 30s timeout)
                result = self.redis.brpop("summary_jobs", timeout=30)
                
                if result:
                    queue_name, job_json = result
                    job_data = json.loads(job_json)
                    self.process_job(job_data)
                else:
                    # Timeout - just continue loop (normal behavior)
                    pass
                    
            except KeyboardInterrupt:
                logger.info("Worker stopped by user")
                break
            except Exception as e:
                # Only log non-timeout errors
                if "timeout" not in str(e).lower():
                    logger.error(f"Worker error: {e}")
                time.sleep(5)  # Brief pause before retrying

if __name__ == "__main__":
    worker = SummaryWorker()
    worker.run()