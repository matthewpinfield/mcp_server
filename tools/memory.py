#!/usr/bin/env python3
"""
Clean Memory System - Web-Style Pattern
=======================================
Redis (Day 1) -> LanceDB SSD (Day 2-30) -> LanceDB NAS (30+)
Agent searches summaries, then retrieves full conversations by ID.
"""

import asyncio
import json
import logging
import lancedb
import ollama
import redis
from datetime import datetime, timedelta
from typing import Dict, List, Type
from pydantic import BaseModel, Field

from config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_TIMEOUT,
    LANCEDB_TIER3_PATH, LANCEDB_NAS_PATH,
    DEFAULT_EMBEDDING_MODEL, DEFAULT_USER, DEFAULT_MODEL
)
from .base import AsyncTool

logger = logging.getLogger(__name__)

# Global connections (singleton pattern)
redis_client = None
lancedb_ssd_table = None
lancedb_nas_table = None


def get_redis_connection():
    """Get Redis connection (singleton)"""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                socket_timeout=REDIS_TIMEOUT, decode_responses=True
            )
            redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    return redis_client


def get_lancedb_connections():
    """Get LanceDB connections (singleton)"""
    global lancedb_ssd_table, lancedb_nas_table
    if lancedb_ssd_table is None:
        try:
            import pyarrow as pa
            schema = pa.schema([
                pa.field("conversation_id", pa.string()),
                pa.field("content", pa.string()),
                pa.field("messages", pa.string()),
                pa.field("summary", pa.string()),
                pa.field("timestamp", pa.timestamp('s')),
                pa.field("date", pa.string()),
                pa.field("user_id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 768))
            ])
            
            # SSD table (2-30 days)
            ssd_db = lancedb.connect(LANCEDB_TIER3_PATH)
            try:
                lancedb_ssd_table = ssd_db.open_table("memories")
            except:
                lancedb_ssd_table = ssd_db.create_table("memories", schema=schema)
            
            # NAS table (30+ days)
            nas_db = lancedb.connect(LANCEDB_NAS_PATH)
            try:
                lancedb_nas_table = nas_db.open_table("memories_archive")
            except:
                lancedb_nas_table = nas_db.create_table("memories_archive", schema=schema)
                
            logger.info("LanceDB connections established")
        except Exception as e:
            logger.error(f"LanceDB connection failed: {e}")
            raise
    return lancedb_ssd_table, lancedb_nas_table


class SimpleMemorySystem:
    """Clean memory system with Redis -> LanceDB sliding window"""
    
    def __init__(self):
        self.redis = get_redis_connection()
        self.ssd_table, self.nas_table = get_lancedb_connections()
    
    def save_memory(self, user_message: str, assistant_response: str) -> Dict:
        """Save conversation turn to Redis immediately, queue summary generation"""
        try:
            timestamp = datetime.now()
            conversation_id = f"chat_{int(timestamp.timestamp())}"
            
            messages = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_response}
            ]
            
            # Save immediately with placeholder summary
            memory = {
                "conversation_id": conversation_id,
                "messages": messages,
                "summary": "Summary pending...",
                "created_at": timestamp.isoformat(),
                "date": timestamp.strftime("%Y-%m-%d"),
                "user_id": DEFAULT_USER
            }
            
            # Save to Redis with 2-day TTL (FAST)
            redis_key = f"conversation:{conversation_id}"
            self.redis.setex(redis_key, timedelta(days=2), json.dumps(memory))
            
            # Queue background job for summary generation (FAST)
            job = {
                "conversation_id": conversation_id,
                "user_message": user_message[:500],  # Truncate for job queue
                "assistant_response": assistant_response[:1000]
            }
            self.redis.lpush("summary_jobs", json.dumps(job))
            
            logger.info(f"Memory saved: {conversation_id}")
            return {"status": "success", "conversation_id": conversation_id}
            
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_today_memories(self, query: str = None, limit: int = 5) -> List[Dict]:
        """Get today's memories from Redis"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            memories = []
            
            for key in self.redis.scan_iter(match="conversation:*"):
                try:
                    memory_data = json.loads(self.redis.get(key))
                    if memory_data.get("date") == today:
                        if query:
                            # Simple text search
                            search_text = " ".join([
                                msg.get("content", "") for msg in memory_data.get("messages", [])
                            ]).lower()
                            if query.lower() in search_text:
                                memories.append(memory_data)
                        else:
                            memories.append(memory_data)
                except:
                    continue
            
            # Sort by creation time (newest first)
            memories.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return memories[:limit]
            
        except Exception as e:
            logger.error(f"Error getting today's memories: {e}")
            return []
    
    async def search_historical_memories(self, query: str, limit: int = 5) -> List[Dict]:
        """Search historical memories in LanceDB with embeddings"""
        try:
            # Get query embeddings
            embed_response = await asyncio.wait_for(
                asyncio.to_thread(ollama.embeddings, model=DEFAULT_EMBEDDING_MODEL, prompt=query),
                timeout=30
            )
            query_embedding = embed_response["embedding"]
            
            all_results = []
            
            # Search SSD table (2-30 days)
            try:
                ssd_results = self.ssd_table.search(query_embedding).limit(limit * 2).to_list()
                for result in ssd_results:
                    all_results.append({
                        "conversation_id": result.get("conversation_id"),
                        "summary": result.get("summary", ""),
                        "date": result.get("date"),
                        "content": result.get("content", ""),
                        "messages": result.get("messages", ""),
                        "distance": result.get("_distance", 0.0),
                        "source": "ssd"
                    })
            except Exception as e:
                logger.debug(f"SSD search error: {e}")
            
            # Search NAS table (30+ days)
            try:
                nas_results = self.nas_table.search(query_embedding).limit(limit * 2).to_list()
                for result in nas_results:
                    all_results.append({
                        "conversation_id": result.get("conversation_id"),
                        "summary": result.get("summary", ""),
                        "date": result.get("date"),
                        "content": result.get("content", ""),
                        "messages": result.get("messages", ""),
                        "distance": result.get("_distance", 0.0),
                        "source": "nas"
                    })
            except Exception as e:
                logger.debug(f"NAS search error: {e}")
            
            # Sort by relevance and return top results
            all_results.sort(key=lambda x: x.get("distance", 1.0))
            return all_results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching historical memories: {e}")
            return []
    
    def get_full_memory(self, conversation_id: str) -> Dict:
        """Get complete conversation by ID"""
        try:
            # Try Redis first
            redis_key = f"conversation:{conversation_id}"
            memory_data = self.redis.get(redis_key)
            if memory_data:
                return json.loads(memory_data)
            
            # Try LanceDB SSD
            try:
                ssd_results = self.ssd_table.search().where(
                    f"conversation_id = '{conversation_id}'"
                ).limit(1).to_list()
                if ssd_results:
                    result = ssd_results[0]
                    return {
                        "conversation_id": result.get("conversation_id"),
                        "messages": json.loads(result.get("messages", "[]")),
                        "summary": result.get("summary", ""),
                        "date": result.get("date"),
                        "source": "ssd"
                    }
            except:
                pass
            
            # Try LanceDB NAS
            try:
                nas_results = self.nas_table.search().where(
                    f"conversation_id = '{conversation_id}'"
                ).limit(1).to_list()
                if nas_results:
                    result = nas_results[0]
                    return {
                        "conversation_id": result.get("conversation_id"),
                        "messages": json.loads(result.get("messages", "[]")),
                        "summary": result.get("summary", ""),
                        "date": result.get("date"),
                        "source": "nas"
                    }
            except:
                pass
            
            return {"error": "Memory not found"}
            
        except Exception as e:
            logger.error(f"Error getting full memory {conversation_id}: {e}")
            return {"error": str(e)}


# Global memory system instance
_memory_system = None

def get_memory_system() -> SimpleMemorySystem:
    """Get memory system singleton"""
    global _memory_system
    if _memory_system is None:
        _memory_system = SimpleMemorySystem()
    return _memory_system


# === AGENT TOOLS ===

class SearchMemorySchema(BaseModel):
    query: str = Field(description="Search query for memories")
    limit: int = Field(default=5, description="Maximum results to return")

class LangchainMemorySearchTool(AsyncTool):
    name: str = "search_memory"
    description: str = (
        "Search memories and return IDs with summaries. "
        "Use get_full_memory to retrieve complete conversations."
    )
    args_schema: Type[BaseModel] = SearchMemorySchema
    
    def _run(self, query: str, limit: int = 5) -> str:
        return asyncio.run(self._arun(query, limit))
    
    async def _arun(self, query: str, limit: int = 5) -> str:
        try:
            memory_system = get_memory_system()
            results = []
            
            # Search today's memories
            today_memories = memory_system.get_today_memories(query, limit)
            for memory in today_memories:
                memory_id = memory.get("conversation_id", "unknown")
                summary = memory.get("summary", "")
                date = memory.get("date", "unknown")
                results.append(f"**[{memory_id}]** TODAY ({date}): {summary}")
            
            # Search historical if needed
            if len(results) < limit:
                historical = await memory_system.search_historical_memories(
                    query, limit - len(results)
                )
                for memory in historical:
                    memory_id = memory.get("conversation_id", "unknown")
                    summary = memory.get("summary", "")
                    date = memory.get("date", "unknown")
                    source = memory.get("source", "unknown").upper()
                    results.append(f"**[{memory_id}]** {source} ({date}): {summary}")
            
            if not results:
                return f"No memories found for: {query}"
            
            return f"Found {len(results)} memories:\n\n" + "\n\n".join(results)
            
        except Exception as e:
            logger.error(f"Memory search error: {e}")
            return f"Search failed: {str(e)}"


class GetFullMemorySchema(BaseModel):
    memory_id: str = Field(description="Memory ID from search results")

class LangchainGetFullMemoryTool(AsyncTool):
    name: str = "get_full_memory"
    description: str = "Get complete conversation content by memory ID"
    args_schema: Type[BaseModel] = GetFullMemorySchema
    
    def _run(self, memory_id: str) -> str:
        try:
            memory_system = get_memory_system()
            memory = memory_system.get_full_memory(memory_id)
            
            if "error" in memory:
                return f"Error: {memory['error']}"
            
            messages = memory.get("messages", [])
            summary = memory.get("summary", "")
            date = memory.get("date", "unknown")
            source = memory.get("source", "redis")
            
            content = f"Memory: {memory_id}\n"
            content += f"Date: {date} | Source: {source.upper()}\n"
            content += f"Summary: {summary}\n\nFull Conversation:\n\n"
            
            for i, msg in enumerate(messages, 1):
                role = msg.get("role", "unknown").title()
                text = msg.get("content", "")
                content += f"{role} ({i}):\n{text}\n\n"
            
            return content
            
        except Exception as e:
            logger.error(f"Get full memory error: {e}")
            return f"Failed to retrieve memory: {str(e)}"


class LangchainMemoryStatsTool(AsyncTool):
    name: str = "memory_stats"
    description: str = "Get memory system statistics"
    args_schema: Type[BaseModel] = type('EmptySchema', (BaseModel,), {})
    
    def _run(self) -> str:
        try:
            memory_system = get_memory_system()
            
            # Count Redis memories (today)
            today = datetime.now().strftime("%Y-%m-%d")
            redis_count = 0
            for key in memory_system.redis.scan_iter(match="conversation:*"):
                try:
                    memory_data = json.loads(memory_system.redis.get(key))
                    if memory_data.get("date") == today:
                        redis_count += 1
                except:
                    continue
            
            # Count LanceDB memories
            ssd_count = len(memory_system.ssd_table) if memory_system.ssd_table else 0
            nas_count = len(memory_system.nas_table) if memory_system.nas_table else 0
            total = redis_count + ssd_count + nas_count
            
            return f"""Memory System Stats:

Redis (Today): {redis_count} memories
LanceDB SSD (2-30 days): {ssd_count} memories  
LanceDB NAS (30+ days): {nas_count} memories
Total: {total} memories

Flow: Redis -> LanceDB SSD -> LanceDB NAS"""
            
        except Exception as e:
            logger.error(f"Memory stats error: {e}")
            return f"Stats failed: {str(e)}"


class SaveAgentNoteSchema(BaseModel):
    note: str = Field(description="Agent's note/analysis to save")

class LangchainSaveAgentNoteTool(AsyncTool):
    name: str = "save_agent_note"
    description: str = "Save your own notes, analysis, conclusions, and insights for future reference"
    args_schema: Type[BaseModel] = SaveAgentNoteSchema
    
    def _run(self, note: str) -> str:
        return asyncio.run(self._arun(note))
    
    async def _arun(self, note: str) -> str:
        try:
            memory_system = get_memory_system()
            timestamp = datetime.now()
            note_id = f"agent_note_{int(timestamp.timestamp())}"
            
            # Create embedding for note content
            embed_response = await asyncio.wait_for(
                asyncio.to_thread(ollama.embeddings, model=DEFAULT_EMBEDDING_MODEL, prompt=note),
                timeout=30
            )
            
            # Save directly to LanceDB SSD with agent tag
            note_record = {
                "conversation_id": note_id,
                "content": f"[AGENT] {note}",
                "messages": json.dumps([{"role": "agent", "content": note}]),
                "summary": f"Agent note: {note[:100]}{'...' if len(note) > 100 else ''}",
                "timestamp": timestamp.replace(microsecond=0),
                "date": timestamp.strftime("%Y-%m-%d"),
                "user_id": "agent",
                "vector": embed_response["embedding"]
            }
            
            memory_system.ssd_table.add([note_record])
            
            logger.info(f"Agent note saved: {note_id}")
            return f"Agent note saved as {note_id}"
            
        except Exception as e:
            logger.error(f"Save agent note error: {e}")
            return f"Failed to save note: {str(e)}"


class SearchAgentNotesSchema(BaseModel):
    query: str = Field(description="Search query for agent notes")
    limit: int = Field(default=5, description="Maximum results to return")

class LangchainSearchAgentNotesTool(AsyncTool):
    name: str = "search_agent_notes"
    description: str = "Search your previously saved notes, analysis, and insights"
    args_schema: Type[BaseModel] = SearchAgentNotesSchema
    
    def _run(self, query: str, limit: int = 5) -> str:
        return asyncio.run(self._arun(query, limit))
    
    async def _arun(self, query: str, limit: int = 5) -> str:
        try:
            memory_system = get_memory_system()
            
            # Get query embeddings
            embed_response = await asyncio.wait_for(
                asyncio.to_thread(ollama.embeddings, model=DEFAULT_EMBEDDING_MODEL, prompt=query),
                timeout=30
            )
            query_embedding = embed_response["embedding"]
            
            # Search LanceDB for agent notes only
            results = memory_system.ssd_table.search(query_embedding).where(
                "user_id = 'agent'"
            ).limit(limit).to_list()
            
            if not results:
                return f"No agent notes found for: {query}"
            
            response = f"Found {len(results)} agent notes:\n\n"
            for result in results:
                note_id = result.get("conversation_id", "unknown")
                content = result.get("content", "").replace("[AGENT] ", "")
                date = result.get("date", "unknown")
                
                response += f"**[{note_id}]** ({date})\n"
                response += f"{content}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Search agent notes error: {e}")
            return f"Search failed: {str(e)}"


# === MAINTENANCE FUNCTIONS ===

def run_daily_maintenance():
    """Transfer yesterday's Redis memories to LanceDB SSD"""
    try:
        memory_system = get_memory_system()
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        transferred = 0
        
        # Get all memories from yesterday
        for key in memory_system.redis.scan_iter(match="conversation:*"):
            try:
                memory_data = json.loads(memory_system.redis.get(key))
                if memory_data.get("date") == yesterday:
                    # Create embedding for content
                    messages = memory_data.get("messages", [])
                    content = " ".join([msg.get("content", "") for msg in messages])
                    
                    embed_response = ollama.embeddings(
                        model=DEFAULT_EMBEDDING_MODEL, 
                        prompt=content[:2000]
                    )
                    
                    # Prepare for LanceDB
                    lance_record = {
                        "conversation_id": memory_data.get("conversation_id"),
                        "content": content,
                        "messages": json.dumps(messages),
                        "summary": memory_data.get("summary", ""),
                        "timestamp": datetime.fromisoformat(memory_data.get("created_at")).replace(microsecond=0),
                        "date": memory_data.get("date"),
                        "user_id": memory_data.get("user_id", DEFAULT_USER),
                        "vector": embed_response["embedding"]
                    }
                    
                    # Insert to SSD table
                    memory_system.ssd_table.add([lance_record])
                    
                    # Delete from Redis after successful transfer
                    memory_system.redis.delete(key)
                    transferred += 1
                    
            except Exception as e:
                logger.error(f"Error transferring memory {key}: {e}")
                continue
        
        logger.info(f"Daily maintenance: transferred {transferred} memories to SSD")
        return {"status": "success", "transferred": transferred}
        
    except Exception as e:
        logger.error(f"Daily maintenance failed: {e}")
        return {"status": "error", "error": str(e)}


def run_weekly_maintenance():
    """Archive old memories from SSD to NAS (30+ days)"""
    try:
        memory_system = get_memory_system()
        cutoff_date = datetime.now() - timedelta(days=30)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        # Get old memories from SSD
        old_memories = memory_system.ssd_table.search().where(f"date < '{cutoff_str}'").to_list()
        
        if not old_memories:
            logger.info("No old memories to archive")
            return {"status": "success", "archived": 0}
        
        # Move to NAS
        memory_system.nas_table.add(old_memories)
        
        # Remove from SSD by recreating with recent data only
        recent_memories = memory_system.ssd_table.search().where(f"date >= '{cutoff_str}'").to_list()
        memory_system.ssd_table.drop()
        
        import pyarrow as pa
        schema = pa.schema([
            pa.field("conversation_id", pa.string()),
            pa.field("content", pa.string()),
            pa.field("messages", pa.string()),
            pa.field("summary", pa.string()),
            pa.field("timestamp", pa.timestamp('s')),
            pa.field("date", pa.string()),
            pa.field("user_id", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), 768))
        ])
        
        ssd_db = lancedb.connect(LANCEDB_TIER3_PATH)
        memory_system.ssd_table = ssd_db.create_table("memories", schema=schema)
        
        if recent_memories:
            memory_system.ssd_table.add(recent_memories)
        
        logger.info(f"Weekly maintenance: archived {len(old_memories)} memories to NAS")
        return {"status": "success", "archived": len(old_memories)}
        
    except Exception as e:
        logger.error(f"Weekly maintenance failed: {e}")
        return {"status": "error", "error": str(e)}