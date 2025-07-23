#!/usr/bin/env python3
"""
Simplified Memory System - RAG Pattern Implementation
====================================================
Redis (Today) + LanceDB (Yesterday+) sliding window architecture
Modeled after dual_endpoint_server.py for simplicity and performance

Memory Flow:
- Redis: Today's memories only (sliding window)
- LanceDB SSD: Days 2-30 (batch transfer from Redis)
- LanceDB NAS: 30+ days (archival)

Agent Access:
- Today's context: Redis (~1ms)
- Historical search: LanceDB (~500ms)
"""

import asyncio
import json
import logging
import lancedb
import ollama
import redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Type
from pydantic import BaseModel, Field

from config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_TIMEOUT,
    LANCEDB_TIER3_PATH, LANCEDB_NAS_PATH,
    DEFAULT_EMBEDDING_MODEL, DEFAULT_USER
)
from .base import AsyncTool

logger = logging.getLogger(__name__)

# Global connections (singleton pattern like RAG)
redis_client = None
lancedb_ssd_table = None
lancedb_nas_table = None

def get_redis_connection():
    """Get or create Redis connection (singleton pattern)"""
    global redis_client
    
    if redis_client is None:
        try:
            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                socket_timeout=REDIS_TIMEOUT,
                socket_connect_timeout=REDIS_TIMEOUT,
                decode_responses=True,
            )
            redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    return redis_client

def get_lancedb_connections():
    """Get or create LanceDB connections (singleton pattern)"""
    global lancedb_ssd_table, lancedb_nas_table
    
    if lancedb_ssd_table is None:
        try:
            # SSD LanceDB (days 2-30)
            ssd_db = lancedb.connect(LANCEDB_TIER3_PATH)
            try:
                lancedb_ssd_table = ssd_db.open_table("memories")
            except:
                # Create table if it doesn't exist
                import pyarrow as pa
                schema = pa.schema([
                    pa.field("conversation_id", pa.string()),
                    pa.field("content", pa.string()),
                    pa.field("summary", pa.string()),
                    pa.field("timestamp", pa.timestamp('s')),
                    pa.field("date", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), 768))
                ])
                lancedb_ssd_table = ssd_db.create_table("memories", schema=schema)
            
            # NAS LanceDB (30+ days)
            nas_db = lancedb.connect(LANCEDB_NAS_PATH)
            try:
                lancedb_nas_table = nas_db.open_table("memories_archive")
            except:
                lancedb_nas_table = nas_db.create_table("memories_archive", schema=schema)
            
            logger.info(f"LanceDB connections established - SSD: {len(lancedb_ssd_table)} docs, NAS: {len(lancedb_nas_table)} docs")
            
        except Exception as e:
            logger.error(f"LanceDB connection failed: {e}")
            raise
    
    return lancedb_ssd_table, lancedb_nas_table

class SimpleMemorySystem:
    """Simplified memory system using Redis + LanceDB sliding window"""
    
    def __init__(self):
        self.redis = get_redis_connection()
        self.ssd_table, self.nas_table = get_lancedb_connections()
    
    def save_memory(self, conversation_id: str, messages: List[Dict], summary: str = None) -> Dict:
        """Save memory to Redis (today only) - APPEND to existing conversation"""
        try:
            timestamp = datetime.now()
            date_key = timestamp.strftime("%Y-%m-%d")
            redis_key = f"conversation:{conversation_id}"
            
            # Check if conversation already exists
            existing_data = self.redis.get(redis_key)
            
            if existing_data:
                # APPEND to existing conversation
                conversation = json.loads(existing_data)
                conversation["messages"].extend(messages)
                conversation["last_updated"] = timestamp.isoformat()
                conversation["summary"] = summary or conversation.get("summary", "")
            else:
                # CREATE new conversation
                conversation = {
                    "conversation_id": conversation_id,
                    "messages": messages,
                    "summary": summary or "",
                    "created_at": timestamp.isoformat(),
                    "last_updated": timestamp.isoformat(),
                    "date": date_key,
                    "user_id": DEFAULT_USER
                }
            
            # Store back to Redis (with TTL for sliding window)
            self.redis.setex(redis_key, timedelta(days=2), json.dumps(conversation))
            
            # Also add to daily list for batch processing
            daily_list_key = f"daily_memories:{date_key}"
            self.redis.lpush(daily_list_key, redis_key)
            self.redis.expire(daily_list_key, timedelta(days=2))
            
            logger.info(f"Memory saved to Redis: {conversation_id}")
            return {"status": "success", "location": "redis", "key": redis_key}
            
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_today_memories(self, query: str = None, limit: int = 5) -> List[Dict]:
        """Get today's memories from Redis - now works with existing conversation:* keys"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            pattern = f"conversation:*"
            
            memories = []
            for key in self.redis.scan_iter(match=pattern):
                try:
                    conversation = json.loads(self.redis.get(key))
                    
                    # Filter by today's date using the date field
                    if conversation.get("date") == today:
                        if query:
                            # Search in all messages content
                            found_match = False
                            for message in conversation.get("messages", []):
                                if query.lower() in message.get("content", "").lower():
                                    found_match = True
                                    break
                            if found_match:
                                memories.append(conversation)
                        else:
                            memories.append(conversation)
                except Exception as e:
                    logger.debug(f"Error loading memory {key}: {e}")
                    continue
            
            # Sort by last_updated (newest first)
            memories.sort(key=lambda x: x.get("last_updated", x.get("created_at", "")), reverse=True)
            return memories[:limit]
            
        except Exception as e:
            logger.error(f"Error retrieving today's memories: {e}")
            return []
    
    async def search_historical_memories(self, query: str, limit: int = 5, days_back: int = 30) -> List[Dict]:
        """Search historical memories in LanceDB (yesterday+)"""
        try:
            # Get query embeddings (like RAG)
            embed_response = await asyncio.wait_for(
                asyncio.to_thread(ollama.embeddings, model=DEFAULT_EMBEDDING_MODEL, prompt=query),
                timeout=30,
            )
            query_embedding = embed_response["embedding"]
            
            # Determine which table to search based on age
            cutoff_date = datetime.now() - timedelta(days=30)
            
            formatted_results = []
            
            # Search SSD table (2-30 days) - format like RAG
            try:
                ssd_results = self.ssd_table.search(query_embedding).limit(limit).to_list()
                for result in ssd_results:
                    formatted_result = {
                        "text": result.get("text", result.get("content", "")),  # Use existing field
                        "metadata": {
                            "conversation_id": result.get("conversation_id"),
                            "summary": result.get("summary", ""),
                            "date": result.get("date"),
                            "timestamp": result.get("timestamp")
                        },
                        "distance": result.get("_distance", 0.0),
                        "db_source": "memory_ssd",
                    }
                    formatted_results.append(formatted_result)
            except Exception as e:
                logger.debug(f"SSD search error: {e}")
            
            # If not enough results and looking far back, search NAS
            if len(formatted_results) < limit and days_back > 30:
                try:
                    nas_results = self.nas_table.search(query_embedding).limit(limit - len(formatted_results)).to_list()
                    for result in nas_results:
                        formatted_result = {
                            "text": result.get("text", result.get("content", "")),
                            "metadata": {
                                "conversation_id": result.get("conversation_id"),
                                "summary": result.get("summary", ""),
                                "date": result.get("date"),
                                "timestamp": result.get("timestamp")
                            },
                            "distance": result.get("_distance", 0.0),
                            "db_source": "memory_nas",
                        }
                        formatted_results.append(formatted_result)
                except Exception as e:
                    logger.debug(f"NAS search error: {e}")
            
            return formatted_results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching historical memories: {e}")
            return []
    
    def daily_batch_transfer(self) -> Dict:
        """Transfer yesterday's Redis memories to LanceDB (called daily)"""
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            daily_list_key = f"daily_memories:{yesterday}"
            
            # Get all memory keys from yesterday
            memory_keys = self.redis.lrange(daily_list_key, 0, -1)
            
            if not memory_keys:
                return {"status": "success", "transferred": 0, "message": "No memories to transfer"}
            
            transferred = 0
            batch_data = []
            
            for key in memory_keys:
                try:
                    memory_json = self.redis.get(key)
                    if memory_json:
                        memory_data = json.loads(memory_json)
                        
                        # Create embedding for LanceDB
                        content = memory_data.get("content", "")
                        embed_response = ollama.embeddings(model=DEFAULT_EMBEDDING_MODEL, prompt=content[:2000])
                        
                        # Prepare for LanceDB insert
                        lance_record = {
                            "conversation_id": memory_data.get("conversation_id"),
                            "content": content,
                            "summary": memory_data.get("summary", ""),
                            "timestamp": datetime.fromisoformat(memory_data.get("timestamp")),
                            "date": memory_data.get("date"),
                            "vector": embed_response["embedding"]
                        }
                        batch_data.append(lance_record)
                        transferred += 1
                        
                except Exception as e:
                    logger.error(f"Error processing memory {key}: {e}")
                    continue
            
            # Batch insert to LanceDB SSD
            if batch_data:
                self.ssd_table.add(batch_data)
                logger.info(f"Transferred {transferred} memories from Redis to LanceDB SSD")
            
            # Clean up Redis (memories naturally age out, but clean the daily list)
            self.redis.delete(daily_list_key)
            
            return {"status": "success", "transferred": transferred}
            
        except Exception as e:
            logger.error(f"Error in daily batch transfer: {e}")
            return {"status": "error", "error": str(e)}
    
    def archive_old_memories(self, days_threshold: int = 30) -> Dict:
        """Archive old memories from SSD to NAS (called periodically)"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_threshold)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")
            
            # Query old memories from SSD
            old_memories = self.ssd_table.search().where(f"date < '{cutoff_str}'").to_list()
            
            if not old_memories:
                return {"status": "success", "archived": 0, "message": "No old memories to archive"}
            
            # Move to NAS
            self.nas_table.add(old_memories)
            
            # Remove from SSD (recreate table without old records)
            recent_memories = self.ssd_table.search().where(f"date >= '{cutoff_str}'").to_list()
            
            # Recreate SSD table with only recent memories
            self.ssd_table.drop()
            import pyarrow as pa
            schema = pa.schema([
                pa.field("conversation_id", pa.string()),
                pa.field("content", pa.string()),
                pa.field("summary", pa.string()),
                pa.field("timestamp", pa.timestamp('s')),
                pa.field("date", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 768))
            ])
            ssd_db = lancedb.connect(LANCEDB_TIER3_PATH)
            self.ssd_table = ssd_db.create_table("memories", schema=schema)
            
            if recent_memories:
                self.ssd_table.add(recent_memories)
            
            logger.info(f"Archived {len(old_memories)} memories to NAS")
            return {"status": "success", "archived": len(old_memories)}
            
        except Exception as e:
            logger.error(f"Error archiving memories: {e}")
            return {"status": "error", "error": str(e)}

# Global memory system instance (singleton)
_memory_system = None

def get_memory_system() -> SimpleMemorySystem:
    """Get global memory system instance"""
    global _memory_system
    if _memory_system is None:
        _memory_system = SimpleMemorySystem()
    return _memory_system

# ===== LANGCHAIN TOOLS =====

class SaveMemorySchema(BaseModel):
    conversation_id: str = Field(description="Unique conversation identifier")
    messages: List[Dict] = Field(description="List of messages to save (role/content format)")
    summary: str = Field(default="", description="Optional summary of the conversation")

class LangchainMemorySaveTool(AsyncTool):
    name: str = "save_memory"
    description: str = (
        "Save a memory to the sliding window system. "
        "Memories are stored in Redis for today and automatically transferred to LanceDB for historical search."
    )
    args_schema: Type[BaseModel] = SaveMemorySchema

    def _run(self, conversation_id: str, messages: List[Dict], summary: str = "") -> str:
        try:
            result = get_memory_system().save_memory(conversation_id, messages, summary)
            if result["status"] == "success":
                return f"✅ Memory saved: {conversation_id} ({len(messages)} messages)"
            else:
                return f"❌ Failed to save memory: {result['error']}"
        except Exception as e:
            return f"❌ Error saving memory: {str(e)}"

class SearchMemorySchema(BaseModel):
    query: str = Field(description="Search query for memories")
    limit: int = Field(default=5, description="Maximum number of results")
    include_today: bool = Field(default=True, description="Include today's memories from Redis")
    days_back: int = Field(default=30, description="How many days back to search")

class LangchainMemorySearchTool(AsyncTool):
    name: str = "search_memory"
    description: str = (
        "Search memories across the sliding window system. "
        "Searches today's memories in Redis and historical memories in LanceDB."
    )
    args_schema: Type[BaseModel] = SearchMemorySchema

    def _run(self, query: str, limit: int = 5, include_today: bool = True, days_back: int = 30) -> str:
        import asyncio
        return asyncio.run(self._arun(query, limit, include_today, days_back))

    async def _arun(self, query: str, limit: int = 5, include_today: bool = True, days_back: int = 30) -> str:
        try:
            memory_system = get_memory_system()
            results = []
            
            # Search today's memories in Redis
            if include_today:
                today_results = memory_system.get_today_memories(query, limit // 2)
                for memory in today_results:
                    results.append(f"📅 TODAY: {memory.get('summary', memory.get('content', '')[:100])}")
            
            # Search historical memories in LanceDB
            historical_results = await memory_system.search_historical_memories(query, limit - len(results), days_back)
            for memory in historical_results:
                source = "SSD" if memory.get("source") == "ssd" else "NAS"
                date = memory.get("date", "unknown")
                content = memory.get("summary", memory.get("content", ""))[:100]
                results.append(f"📚 {source} ({date}): {content}")
            
            if not results:
                return f"🔍 No memories found for: {query}"
            
            return f"🧠 Found {len(results)} memories:\n\n" + "\n".join(results)
            
        except Exception as e:
            return f"❌ Error searching memories: {str(e)}"

class MemoryStatsSchema(BaseModel):
    pass

class LangchainMemoryStatsTool(AsyncTool):
    name: str = "memory_stats"
    description: str = "Get statistics about the memory system storage"
    args_schema: Type[BaseModel] = MemoryStatsSchema

    def _run(self) -> str:
        try:
            memory_system = get_memory_system()
            
            # Count Redis memories (today) - filter by date field
            today = datetime.now().strftime("%Y-%m-%d")
            redis_pattern = f"conversation:*"
            redis_count = 0
            
            for key in memory_system.redis.scan_iter(match=redis_pattern):
                try:
                    memory_data = json.loads(memory_system.redis.get(key))
                    if memory_data.get("date") == today:
                        redis_count += 1
                except:
                    continue
            
            # Count LanceDB memories
            ssd_count = len(memory_system.ssd_table) if memory_system.ssd_table else 0
            nas_count = len(memory_system.nas_table) if memory_system.nas_table else 0
            
            return f"""📊 Memory System Stats:
            
🔥 Redis (Today): {redis_count} memories
💿 LanceDB SSD (2-30 days): {ssd_count} memories  
🏛️ LanceDB NAS (30+ days): {nas_count} memories
📈 Total: {redis_count + ssd_count + nas_count} memories

System: Redis → LanceDB SSD → LanceDB NAS"""
            
        except Exception as e:
            return f"❌ Error getting memory stats: {str(e)}"

# ===== MAINTENANCE FUNCTIONS =====

def run_daily_maintenance():
    """Run daily maintenance tasks"""
    memory_system = get_memory_system()
    
    # Transfer yesterday's memories
    transfer_result = memory_system.daily_batch_transfer()
    logger.info(f"Daily transfer result: {transfer_result}")
    
    return transfer_result

def run_weekly_maintenance():
    """Run weekly maintenance tasks"""
    memory_system = get_memory_system()
    
    # Archive old memories
    archive_result = memory_system.archive_old_memories()
    logger.info(f"Weekly archive result: {archive_result}")
    
    return archive_result