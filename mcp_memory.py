#!/usr/bin/env python3
"""
MCP Memory System - Advanced 3-Tier Memory Architecture
=====================================================

A sophisticated memory system for LLMs using a 3-tier database approach:
- Tier 1 (Redis): Fast short-term conversation context
- Tier 2 (MongoDB): Permanent profile data and rules  
- Tier 3 (ChromaDB): Long-term semantic search on NAS

This module provides MCP tools for memory operations.
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import asyncio
import logging

# Database imports
import redis
import pymongo
import chromadb
from chromadb.utils import embedding_functions

# MCP imports (will be added when integrating with gemini_mcp_server)
# from mcp import types
# from mcp.server import Server

# Configuration
SSD_BASE_DATA_PATH = "/mnt/caseSSD/mcp_server_data/"
NAS_BASE_DATA_PATH = "/mnt/my_nas_mcp_share/archives/"

# Database paths
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

MONGODB_URI = "mongodb://localhost:27017/"
MONGODB_DATABASE = "mcp_memory"

CHROMA_PATH = os.path.join(NAS_BASE_DATA_PATH, "memory_vector_db")
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Memory settings
DEFAULT_USER = "default_user"
CONTEXT_WINDOW_HOURS = 24  # Hours of conversation context to retrieve
ARCHIVE_AFTER_DAYS = 30

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemorySystem:
    """
    Advanced 3-Tier Memory System for LLM
    
    Tier 1: Redis - Fast short-term conversation context
    Tier 2: MongoDB - Permanent profile data and rules
    Tier 3: ChromaDB - Long-term semantic search (on NAS)
    """
    
    def __init__(self):
        self.user = DEFAULT_USER
        self.redis_client = None
        self.mongo_client = None
        self.mongo_db = None
        self.chroma_client = None
        self.long_term_memory = None
        self.embedding_func = None
        self._initialize_databases()
    
    def _initialize_databases(self):
        """Initialize all three database connections"""
        try:
            self._setup_redis()
            self._setup_mongodb()
            self._setup_chromadb()
            logger.info("✅ All database connections initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize databases: {e}")
            raise
    
    def _setup_redis(self):
        """Initialize Redis connection for short-term memory"""
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e} (will use fallback)")
            self.redis_client = None
    
    def _setup_mongodb(self):
        """Initialize MongoDB connection for permanent memory"""
        try:
            self.mongo_client = pymongo.MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000
            )
            # Test connection
            self.mongo_client.admin.command('ping')
            self.mongo_db = self.mongo_client[MONGODB_DATABASE]
            
            # Ensure collections exist with proper indexes
            self._setup_mongodb_collections()
            logger.info("✅ MongoDB connection established")
        except Exception as e:
            logger.warning(f"⚠️ MongoDB connection failed: {e} (will use fallback)")
            self.mongo_client = None
            self.mongo_db = None
    
    def _setup_mongodb_collections(self):
        """Set up MongoDB collections and indexes"""
        # User profiles collection
        profiles = self.mongo_db.profiles
        profiles.create_index("user_id")
        
        # Raw logs collection for archival
        logs = self.mongo_db.raw_logs
        logs.create_index([("timestamp", 1), ("user_id", 1)])
        
        # Initialize default user profile if not exists
        if not profiles.find_one({"user_id": DEFAULT_USER}):
            default_profile = {
                "user_id": DEFAULT_USER,
                "created_at": datetime.now(),
                "rules": [],
                "preferences": {},
                "metadata": {}
            }
            profiles.insert_one(default_profile)
            logger.info("✅ Default user profile created")
    
    def _setup_chromadb(self):
        """Initialize ChromaDB connection for long-term semantic memory"""
        try:
            # Ensure NAS directory exists
            os.makedirs(CHROMA_PATH, exist_ok=True)
            
            # Initialize persistent client on NAS
            self.chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            
            # Set up embedding function (use default if sentence_transformers not available)
            try:
                self.embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=DEFAULT_EMBEDDING_MODEL
                )
            except Exception as e:
                logger.warning(f"⚠️ SentenceTransformer not available, using default embedding: {e}")
                self.embedding_func = embedding_functions.DefaultEmbeddingFunction()
            
            # Create/get long-term memory collection
            self.long_term_memory = self.chroma_client.get_or_create_collection(
                name="long_term_memory",
                embedding_function=self.embedding_func
            )
            
            logger.info(f"✅ ChromaDB initialized with {self.long_term_memory.count()} memories")
        except Exception as e:
            logger.error(f"❌ ChromaDB connection failed: {e}")
            raise
    
    def save_interaction(self, messages: List[Dict], tags: Optional[Dict] = None) -> Dict:
        """
        Core memory write operation - saves interaction to all 3 tiers
        
        Args:
            messages: List of chat messages [{"role": "user/assistant", "content": "..."}]
            tags: Optional manual tags {"domain": "programming", "language": "python", etc.}
        
        Returns:
            Dict with operation status and IDs
        """
        try:
            timestamp = datetime.now()
            interaction_id = f"interaction_{timestamp.timestamp()}"
            
            # Prepare interaction data
            interaction_data = {
                "id": interaction_id,
                "timestamp": timestamp,
                "messages": messages,
                "tags": tags or {},
                "user_id": DEFAULT_USER
            }
            
            results = {}
            
            # Tier 1: Save to Redis (short-term context)
            if self.redis_client:
                redis_key = f"context:{DEFAULT_USER}:{interaction_id}"
                self.redis_client.setex(
                    redis_key,
                    timedelta(hours=CONTEXT_WINDOW_HOURS),
                    json.dumps(interaction_data, default=str)
                )
                results["redis"] = redis_key
            else:
                results["redis"] = "unavailable"
            
            # Tier 2: Save to MongoDB (raw logs for archival)
            if self.mongo_db is not None:
                log_doc = {
                    **interaction_data,
                    "timestamp": timestamp,
                    "archived": False
                }
                mongo_result = self.mongo_db.raw_logs.insert_one(log_doc)
                results["mongodb"] = str(mongo_result.inserted_id)
            else:
                results["mongodb"] = "unavailable"
            
            # Tier 3: Save to ChromaDB (semantic search)
            conversation_text = self._format_messages_for_search(messages)
            
            # Prepare metadata for ChromaDB
            metadata = {
                "timestamp": timestamp.isoformat(),
                "user_id": DEFAULT_USER,
                "message_count": len(messages),
                "interaction_id": interaction_id,
            }
            # Add tags if provided
            if tags:
                metadata.update(tags)
            
            self.long_term_memory.add(
                documents=[conversation_text],
                metadatas=[metadata],
                ids=[interaction_id]
            )
            results["chromadb"] = interaction_id
            
            logger.info(f"✅ Interaction saved: {interaction_id}")
            return {"status": "success", "interaction_id": interaction_id, "results": results}
            
        except Exception as e:
            logger.error(f"❌ Failed to save interaction: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_key_value(self, key: str) -> Any:
        """
        Get a specific key-value pair from profile data (MongoDB)
        
        Args:
            key: The key to retrieve
            
        Returns:
            The value associated with the key, or None if not found
        """
        try:
            if self.mongo_db is None:
                return None
                
            profile = self.mongo_db.profiles.find_one({"user": self.user})
            if profile and key in profile:
                return profile[key]
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get key {key}: {e}")
            return None

    def set_key_value(self, key: str, value: Any) -> Dict:
        """
        Set a specific key-value pair in profile data (MongoDB)
        
        Args:
            key: The key to set
            value: The value to store
            
        Returns:
            Dict with operation status
        """
        try:
            if self.mongo_db is None:
                return {"status": "error", "error": "MongoDB unavailable"}
                
            result = self.mongo_db.profiles.update_one(
                {"user": self.user},
                {"$set": {key: value, "updated_at": datetime.now()}},
                upsert=True
            )
            return {"status": "success", "key": key, "modified": result.modified_count}
        except Exception as e:
            logger.error(f"❌ Failed to set key {key}: {e}")
            return {"status": "error", "error": str(e)}

    def get_context(self, query: Optional[str] = None, include_long_term: bool = True) -> Dict:
        """
        Core memory read operation - retrieves context from all 3 tiers
        
        Args:
            query: Optional semantic search query for long-term memory
            include_long_term: Whether to include semantic search results
        
        Returns:
            Dict with context from all memory tiers
        """
        try:
            context = {
                "short_term": [],
                "profile": {},
                "long_term": [],
                "timestamp": datetime.now().isoformat()
            }
            
            # Tier 1: Get recent context from Redis
            context["short_term"] = self._get_redis_context()
            
            # Tier 2: Get profile data from MongoDB
            context["profile"] = self._get_mongodb_profile()
            
            # Tier 3: Get semantic memories from ChromaDB
            if include_long_term and query:
                context["long_term"] = self._search_long_term_memory(query)
            
            logger.info(f"✅ Context retrieved: {len(context['short_term'])} recent, {len(context['long_term'])} semantic")
            return {"status": "success", "context": context}
            
        except Exception as e:
            logger.error(f"❌ Failed to get context: {e}")
            return {"status": "error", "error": str(e)}
    
    def add_permanent_rule(self, rule: str, category: str = "general") -> Dict:
        """
        Administrative operation - adds permanent rule to user profile
        
        Args:
            rule: The rule text to add
            category: Rule category for organization
        
        Returns:
            Dict with operation status
        """
        if self.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}
            
        try:
            rule_data = {
                "rule": rule,
                "category": category,
                "added_at": datetime.now(),
                "id": hashlib.md5(rule.encode()).hexdigest()[:8]
            }
            
            result = self.mongo_db.profiles.update_one(
                {"user_id": DEFAULT_USER},
                {"$push": {"rules": rule_data}}
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ Rule added: {rule}")
                return {"status": "success", "rule_id": rule_data["id"]}
            else:
                return {"status": "error", "error": "Failed to update profile"}
                
        except Exception as e:
            logger.error(f"❌ Failed to add rule: {e}")
            return {"status": "error", "error": str(e)}
    
    def add_correction(self, ai_response: str, user_correction: str, topic: str = None) -> Dict:
        """
        Store AI correction for learning from mistakes
        
        Args:
            ai_response: The incorrect AI response
            user_correction: The user's correction
            topic: Optional topic/category for the correction
            
        Returns:
            Dict with operation status
        """
        if self.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}
            
        try:
            correction_data = {
                "ai_response": ai_response,
                "user_correction": user_correction,
                "topic": topic or "general",
                "created_at": datetime.now(),
                "user_id": self.user,
                "id": hashlib.md5(f"{ai_response}{user_correction}".encode()).hexdigest()[:8]
            }
            
            # Store in correction_logs collection
            result = self.mongo_db.correction_logs.insert_one(correction_data)
            
            if result.inserted_id:
                logger.info(f"✅ Correction stored: {correction_data['id']}")
                return {"status": "success", "correction_id": correction_data["id"]}
            else:
                return {"status": "error", "error": "Failed to insert correction"}
                
        except Exception as e:
            logger.error(f"❌ Failed to add correction: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_corrections(self, topic: str = None, limit: int = 5) -> List[Dict]:
        """
        Retrieve relevant corrections for prompt injection
        
        Args:
            topic: Optional topic to filter corrections
            limit: Maximum number of corrections to return
            
        Returns:
            List of correction dictionaries
        """
        if self.mongo_db is None:
            return []
            
        try:
            query = {"user_id": self.user}
            if topic:
                query["topic"] = topic
                
            corrections = list(self.mongo_db.correction_logs.find(
                query,
                {"_id": 0, "ai_response": 1, "user_correction": 1, "topic": 1, "created_at": 1}
            ).sort("created_at", -1).limit(limit))
            
            return corrections
            
        except Exception as e:
            logger.error(f"❌ Failed to get corrections: {e}")
            return []
    
    def get_memory_stats(self) -> Dict:
        """
        Diagnostic operation - returns memory system statistics
        
        Returns:
            Dict with statistics from all memory tiers
        """
        try:
            stats = {
                "timestamp": datetime.now().isoformat(),
                "redis": {},
                "mongodb": {},
                "chromadb": {}
            }
            
            # Redis stats
            if self.redis_client:
                redis_info = self.redis_client.info()
                context_keys = len(self.redis_client.keys(f"context:{DEFAULT_USER}:*"))
                stats["redis"] = {
                    "status": "connected",
                    "memory_usage": redis_info.get("used_memory_human", "unknown"),
                    "active_contexts": context_keys
                }
            else:
                stats["redis"] = {"status": "unavailable"}
            
            # MongoDB stats
            if self.mongo_db is not None:
                db_stats = self.mongo_db.command("dbstats")
                stats["mongodb"] = {
                    "status": "connected",
                    "storage_size": db_stats.get("storageSize", 0),
                    "raw_logs_count": self.mongo_db.raw_logs.count_documents({}),
                    "profiles_count": self.mongo_db.profiles.count_documents({})
                }
            else:
                stats["mongodb"] = {"status": "unavailable"}
            
            # ChromaDB stats
            stats["chromadb"] = {
                "status": "connected",
                "memory_count": self.long_term_memory.count(),
                "storage_path": CHROMA_PATH
            }
            
            logger.info("✅ Memory stats retrieved")
            return {"status": "success", "stats": stats}
            
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {"status": "error", "error": str(e)}
    
    # Helper methods
    
    def _get_redis_context(self) -> List[Dict]:
        """Retrieve recent conversation context from Redis"""
        if not self.redis_client:
            return []
            
        try:
            keys = self.redis_client.keys(f"context:{DEFAULT_USER}:*")
            contexts = []
            
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    contexts.append(json.loads(data))
            
            # Sort by timestamp
            contexts.sort(key=lambda x: x["timestamp"])
            return contexts
            
        except Exception as e:
            logger.error(f"❌ Failed to get Redis context: {e}")
            return []
    
    def _get_mongodb_profile(self) -> Dict:
        """Retrieve user profile from MongoDB"""
        if self.mongo_db is None:
            return {}
            
        try:
            profile = self.mongo_db.profiles.find_one({"user_id": DEFAULT_USER})
            if profile:
                # Remove MongoDB ObjectId for JSON serialization
                profile.pop("_id", None)
                return profile
            return {}
            
        except Exception as e:
            logger.error(f"❌ Failed to get MongoDB profile: {e}")
            return {}
    
    def _search_long_term_memory(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search long-term semantic memory"""
        try:
            results = self.long_term_memory.query(
                query_texts=[query],
                n_results=n_results
            )
            
            formatted_results = []
            if results and results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = {}
                    distance = 0.0
                    
                    if (results.get("metadatas") and 
                        results["metadatas"] and 
                        len(results["metadatas"][0]) > i):
                        metadata = results["metadatas"][0][i] or {}
                    
                    if (results.get("distances") and 
                        results["distances"] and 
                        len(results["distances"][0]) > i):
                        distance = results["distances"][0][i]
                    
                    formatted_results.append({
                        "content": doc,
                        "metadata": metadata,
                        "relevance_score": 1.0 - distance  # Convert distance to relevance
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ Failed to search long-term memory: {e}")
            return []
    
    def _format_messages_for_search(self, messages: List[Dict]) -> str:
        """Convert messages to searchable text for ChromaDB"""
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])


# Global memory system instance
memory_system = None

def get_memory_system() -> MemorySystem:
    """Get or create the global memory system instance"""
    global memory_system
    if memory_system is None:
        memory_system = MemorySystem()
    return memory_system


# MCP Tool Interface Functions
# These will be exposed as MCP tools to the LLM

def mcp_get_context(query: str = None, include_long_term: bool = True) -> Dict:
    """MCP Tool: Retrieve memory context for conversation"""
    return get_memory_system().get_context(query, include_long_term)

def mcp_save_interaction(messages: List[Dict], tags: Dict = None) -> Dict:
    """MCP Tool: Save conversation interaction to memory"""
    return get_memory_system().save_interaction(messages, tags)

def mcp_add_permanent_rule(rule: str, category: str = "general") -> Dict:
    """MCP Tool: Add permanent rule to user profile"""
    return get_memory_system().add_permanent_rule(rule, category)

def mcp_get_memory_stats() -> Dict:
    """MCP Tool: Get memory system diagnostics"""
    return get_memory_system().get_memory_stats()

def mcp_get_key_value(key: str) -> Any:
    """MCP Tool: Get a specific key from profile data"""
    return get_memory_system().get_key_value(key)

def mcp_set_key_value(key: str, value: Any) -> Dict:
    """MCP Tool: Set a specific key in profile data"""
    return get_memory_system().set_key_value(key, value)

def mcp_add_correction(ai_response: str, user_correction: str, topic: str = None) -> Dict:
    """MCP Tool: Store AI correction for learning from mistakes"""
    return get_memory_system().add_correction(ai_response, user_correction, topic)

def mcp_get_corrections(topic: str = None, limit: int = 5) -> List[Dict]:
    """MCP Tool: Retrieve relevant corrections for prompt injection"""
    return get_memory_system().get_corrections(topic, limit)


if __name__ == "__main__":
    # Test the memory system
    print("🧠 MCP Memory System - Testing...")
    
    try:
        ms = MemorySystem()
        
        # Test save interaction
        test_messages = [
            {"role": "user", "content": "Hello, can you help me with Python?"},
            {"role": "assistant", "content": "Of course! I'd be happy to help with Python. What do you need?"}
        ]
        test_tags = {"domain": "programming", "language": "python"}
        
        save_result = ms.save_interaction(test_messages, test_tags)
        print(f"Save result: {save_result}")
        
        # Test get context
        context_result = ms.get_context("Python programming help")
        print(f"Context result: {context_result}")
        
        # Test add rule
        rule_result = ms.add_permanent_rule("Always explain Python concepts clearly", "programming")
        print(f"Rule result: {rule_result}")
        
        # Test stats
        stats_result = ms.get_memory_stats()
        print(f"Stats result: {stats_result}")
        
        print("✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")