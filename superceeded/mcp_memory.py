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
import ollama

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

# Memory tier paths
CHROMA_TIER3_PATH = os.path.join(SSD_BASE_DATA_PATH, "tier3_memory_db")  # Tier 3 (SSD - fast)
CHROMA_NAS_PATH = os.path.join(NAS_BASE_DATA_PATH, "memory_vector_db")   # NAS archive (slow)
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text:latest"

# Memory settings
DEFAULT_USER = "default_user"
CONTEXT_WINDOW_HOURS = 24  # Hours of conversation context to retrieve
ARCHIVE_AFTER_DAYS = 14  # Days before Tier 1 → Tier 3a migration
NAS_ARCHIVE_AFTER_DAYS = 30  # Days before Tier 3a → Tier 3b migration
TIER_2_WARNING_THRESHOLD = 1000  # Number of rules before warning

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
        self.chroma_tier3_client = None
        self.chroma_nas_client = None
        self.tier3_memory = None  # Tier 3 (SSD - fast)
        self.nas_archive = None   # NAS archive (slow)
        self.embedding_func = None
        self._initialize_databases()
    
    def _initialize_databases(self):
        """Initialize all database connections with 4-tier architecture"""
        try:
            self._setup_redis()
            self._setup_mongodb()
            self._setup_chromadb_tier3()  # Tier 3
            self._setup_chromadb_nas()     # NAS archive
            logger.info("All 4-tier database connections initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize databases: {e}")
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
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e} (will use fallback)")
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
            logger.info("MongoDB connection established")
        except Exception as e:
            logger.warning(f"MongoDB connection failed: {e} (will use fallback)")
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
            logger.info("Default user profile created")
    
    def _check_and_mount_nas(self):
        """Check if NAS is online and accessible"""
        import subprocess
        import time
        
        nas_mount_point = "/mnt/my_nas_mcp_share"
        
        # Step 1: Check if mount point exists
        if not os.path.exists(nas_mount_point):
            logger.error(f"NAS mount point missing: {nas_mount_point}")
            return False
        
        # Step 2: Check if NAS is responding (test file access with timeout)
        try:
            # Test directory listing with timeout
            result = subprocess.run(['timeout', '5', 'ls', nas_mount_point], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.error("NAS directory listing failed (network timeout or NAS offline)")
                return False
        except subprocess.TimeoutExpired:
            logger.error("NAS access timeout - network may be down or NAS offline")
            return False
        except Exception as e:
            logger.error(f"NAS connectivity test failed: {e}")
            return False
        
        # Step 3: Test write access to verify NAS is fully operational
        try:
            test_file = os.path.join(nas_mount_point, ".nas_connectivity_test")
            with open(test_file, 'w') as f:
                f.write(f"connectivity_test_{time.time()}")
            os.remove(test_file)
            logger.info("NAS online and accessible")
            return True
            
        except OSError as e:
            if "Read-only file system" in str(e):
                logger.error("NAS is read-only - storage may be full or NAS in maintenance mode")
            elif "No space left" in str(e):
                logger.error("NAS storage full")
            elif "Permission denied" in str(e):
                logger.error("NAS permission denied - check credentials")
            else:
                logger.error(f"NAS write test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"NAS accessibility failed: {e}")
            logger.error("   NAS may be offline or network connection lost")
            return False

    def _setup_chromadb_tier3(self):
        """Initialize ChromaDB on SSD for Tier 3 (semantic search)"""
        try:
            # Ensure SSD directory exists
            os.makedirs(CHROMA_TIER3_PATH, exist_ok=True)
            
            # Initialize persistent client on SSD
            self.chroma_tier3_client = chromadb.PersistentClient(path=CHROMA_TIER3_PATH)
            
            # Set up Ollama embedding function
            if not self.embedding_func:
                class OllamaEmbeddingFunction(embedding_functions.EmbeddingFunction):
                    def __init__(self, model_name: str):
                        self.model_name = model_name
                    
                    def __call__(self, input: List[str]) -> List[List[float]]:
                        embeddings = []
                        for text in input:
                            try:
                                result = ollama.embeddings(model=self.model_name, prompt=text)
                                embeddings.append(result['embedding'])
                            except Exception as e:
                                logger.error(f"Ollama embedding error for text '{text[:50]}...': {e}")
                                # Return zero vector as fallback (768 dimensions for nomic-embed-text)
                                embeddings.append([0.0] * 768)
                        return embeddings
                
                self.embedding_func = OllamaEmbeddingFunction(DEFAULT_EMBEDDING_MODEL)
            
            # Create/get tier 3 memory collection
            self.tier3_memory = self.chroma_tier3_client.get_or_create_collection(
                name="tier3_memory",
                embedding_function=self.embedding_func
            )
            
            logger.info(f"ChromaDB Tier 3 initialized with {self.tier3_memory.count()} memories")
        except Exception as e:
            logger.error(f"ChromaDB SSD connection failed: {e}")
            raise

    def _setup_chromadb_nas(self):
        """Initialize ChromaDB on NAS for Tier 3b (long-term archive 30+ days)"""
        try:
            # Check NAS connectivity first
            if not self._check_and_mount_nas():
                logger.warning("NAS not available - Tier 3b (long-term archive) will be limited")
                self.chroma_nas_client = None
                self.archive_memory = None
                return
            
            # Ensure NAS directory exists
            os.makedirs(CHROMA_NAS_PATH, exist_ok=True)
            
            # Test write access to NAS
            test_file = os.path.join(CHROMA_NAS_PATH, ".write_test")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                logger.info("NAS write access confirmed")
            except Exception as e:
                logger.warning(f"NAS write access failed: {e} - Tier 3b will be read-only")
            
            # Initialize persistent client on NAS
            self.chroma_nas_client = chromadb.PersistentClient(path=CHROMA_NAS_PATH)
            
            # Create/get NAS archive collection
            self.nas_archive = self.chroma_nas_client.get_or_create_collection(
                name="nas_archive",
                embedding_function=self.embedding_func
            )
            
            logger.info(f"ChromaDB NAS archive initialized with {self.nas_archive.count()} archived memories")
        except Exception as e:
            logger.warning(f"ChromaDB NAS connection failed: {e} - long-term archive unavailable")
            self.chroma_nas_client = None
            self.nas_archive = None
    
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
                    timedelta(days=ARCHIVE_AFTER_DAYS),  # 14 days
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
            
            # Tier 3: Save to ChromaDB (semantic search) - NOW ON SSD
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
            
            self.tier3_memory.add(
                documents=[conversation_text],
                metadatas=[metadata],
                ids=[interaction_id]
            )
            results["chromadb"] = interaction_id
            
            logger.info(f"Interaction saved: {interaction_id}")
            return {"status": "success", "interaction_id": interaction_id, "results": results}
            
        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
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
            logger.error(f"Failed to get key {key}: {e}")
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
            logger.error(f"Failed to set key {key}: {e}")
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
            
            logger.info(f"Context retrieved: {len(context['short_term'])} recent, {len(context['long_term'])} semantic")
            return {"status": "success", "context": context}
            
        except Exception as e:
            logger.error(f"Failed to get context: {e}")
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
                logger.info(f"Rule added: {rule}")
                return {"status": "success", "rule_id": rule_data["id"]}
            else:
                return {"status": "error", "error": "Failed to update profile"}
                
        except Exception as e:
            logger.error(f"Failed to add rule: {e}")
            return {"status": "error", "error": str(e)}
    
    def delete_permanent_rule(self, rule_id: str) -> Dict:
        """
        Administrative operation - deletes permanent rule from user profile
        
        Args:
            rule_id: The rule ID to delete (8-character hash)
        
        Returns:
            Dict with operation status
        """
        if self.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}
            
        try:
            # First, get the rule to confirm it exists
            profile = self.mongo_db.profiles.find_one({"user_id": DEFAULT_USER})
            if not profile or "rules" not in profile:
                return {"status": "error", "error": "No rules found in profile"}
            
            # Find the rule by ID
            rule_to_delete = None
            for rule in profile["rules"]:
                if rule.get("id") == rule_id:
                    rule_to_delete = rule
                    break
            
            if not rule_to_delete:
                return {"status": "error", "error": f"Rule with ID '{rule_id}' not found"}
            
            # Delete the rule
            result = self.mongo_db.profiles.update_one(
                {"user_id": DEFAULT_USER},
                {"$pull": {"rules": {"id": rule_id}}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Rule deleted: {rule_to_delete.get('rule', rule_id)}")
                return {"status": "success", "deleted_rule": rule_to_delete}
            else:
                return {"status": "error", "error": "Failed to delete rule"}
                
        except Exception as e:
            logger.error(f"Failed to delete rule: {e}")
            return {"status": "error", "error": str(e)}
    
    def update_permanent_rule(self, rule_id: str, new_rule: str, new_category: str = None) -> Dict:
        """
        Administrative operation - updates permanent rule in user profile
        
        Args:
            rule_id: The rule ID to update (8-character hash)
            new_rule: The new rule text
            new_category: Optional new category (keeps existing if None)
        
        Returns:
            Dict with operation status
        """
        if self.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}
            
        try:
            # First, get the existing rule
            profile = self.mongo_db.profiles.find_one({"user_id": DEFAULT_USER})
            if not profile or "rules" not in profile:
                return {"status": "error", "error": "No rules found in profile"}
            
            # Find the rule by ID
            existing_rule = None
            for rule in profile["rules"]:
                if rule.get("id") == rule_id:
                    existing_rule = rule
                    break
            
            if not existing_rule:
                return {"status": "error", "error": f"Rule with ID '{rule_id}' not found"}
            
            # Prepare update data
            update_data = {
                "rule": new_rule,
                "category": new_category if new_category else existing_rule.get("category", "general"),
                "added_at": existing_rule.get("added_at"),  # Keep original timestamp
                "updated_at": datetime.now(),
                "id": rule_id  # Keep the same ID - don't regenerate
            }
            
            # Update the rule using array filters
            result = self.mongo_db.profiles.update_one(
                {"user_id": DEFAULT_USER, "rules.id": rule_id},
                {"$set": {"rules.$": update_data}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Rule updated: {existing_rule.get('rule')} -> {new_rule}")
                return {"status": "success", "old_rule": existing_rule, "new_rule": update_data}
            else:
                return {"status": "error", "error": "Failed to update rule"}
                
        except Exception as e:
            logger.error(f"Failed to update rule: {e}")
            return {"status": "error", "error": str(e)}
    
    def list_permanent_rules(self, search_query: str = None) -> Dict:
        """
        List permanent rules from user profile with optional search filtering
        
        Args:
            search_query: Optional search term to filter rules by content
        
        Returns:
            Dict with list of rules and their details
        """
        if self.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}
            
        try:
            profile = self.mongo_db.profiles.find_one({"user_id": DEFAULT_USER})
            if not profile or "rules" not in profile:
                return {"status": "success", "rules": [], "count": 0}
            
            rules = profile["rules"]
            
            # Filter by search query if provided
            if search_query:
                search_lower = search_query.lower()
                filtered_rules = []
                for rule in rules:
                    rule_text = rule.get("rule", "").lower()
                    rule_category = rule.get("category", "").lower()
                    if search_lower in rule_text or search_lower in rule_category:
                        filtered_rules.append(rule)
                rules = filtered_rules
            
            # Sort by creation date (newest first)
            rules.sort(key=lambda x: x.get("added_at", datetime.min), reverse=True)
            
            logger.info(f"Listed {len(rules)} rules" + (f" matching '{search_query}'" if search_query else ""))
            return {"status": "success", "rules": rules, "count": len(rules), "search_query": search_query}
            
        except Exception as e:
            logger.error(f"Failed to list rules: {e}")
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
                logger.info(f"Correction stored: {correction_data['id']}")
                return {"status": "success", "correction_id": correction_data["id"]}
            else:
                return {"status": "error", "error": "Failed to insert correction"}
                
        except Exception as e:
            logger.error(f"Failed to add correction: {e}")
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
            logger.error(f"Failed to get corrections: {e}")
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
            
            # ChromaDB stats (Tier 3 and NAS)
            stats["tier3_memory"] = {
                "status": "connected",
                "memory_count": self.tier3_memory.count(),
                "storage_path": CHROMA_TIER3_PATH
            }
            
            if self.nas_archive:
                stats["nas_archive"] = {
                    "status": "connected", 
                    "memory_count": self.nas_archive.count(),
                    "storage_path": CHROMA_NAS_PATH
                }
            else:
                stats["nas_archive"] = {"status": "unavailable"}
            
            logger.info("Memory stats retrieved")
            return {"status": "success", "stats": stats}
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
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
            logger.error(f"Failed to get Redis context: {e}")
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
            logger.error(f"Failed to get MongoDB profile: {e}")
            return {}
    
    def _search_long_term_memory(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search long-term semantic memory (SSD first, then NAS)"""
        try:
            # Search Tier 3 (SSD) first
            results = self.tier3_memory.query(
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
            logger.error(f"Failed to search long-term memory: {e}")
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

def mcp_delete_permanent_rule(rule_id: str) -> Dict:
    """MCP Tool: Delete permanent rule from user profile by ID"""
    return get_memory_system().delete_permanent_rule(rule_id)

def mcp_update_permanent_rule(rule_id: str, new_rule: str, new_category: str = None) -> Dict:
    """MCP Tool: Update permanent rule in user profile by ID"""
    return get_memory_system().update_permanent_rule(rule_id, new_rule, new_category)

def mcp_list_permanent_rules(search_query: str = None) -> Dict:
    """MCP Tool: List permanent rules with optional search filtering"""
    return get_memory_system().list_permanent_rules(search_query)

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

# ===== LANGCHAIN TOOL CLASSES =====

from langchain_core.tools import BaseTool as LangchainBaseTool
from pydantic import BaseModel, Field
from typing import Type
import asyncio

# Schema classes
class MemoryContextSchema(BaseModel):
    query: str = Field(description="Optional query to focus the memory search. Leave empty to get general context.")
    include_long_term: bool = Field(description="Whether to include semantic search of long-term memories", default=True)

class MemorySaveSchema(BaseModel):
    messages: List[Dict[str, str]] = Field(description="List of message objects like [{'role': 'user', 'content': 'text'}]")
    tags: Optional[Dict[str, str]] = Field(description="Optional tags for categorization like {'domain': 'programming', 'language': 'python'}", default=None)

class MemoryRuleSchema(BaseModel):
    rule: str = Field(description="The rule or preference text. Example: 'I prefer detailed explanations' or 'Always use TypeScript for web projects'")
    category: str = Field(description="Category like 'preference', 'coding_style', 'communication', etc.", default="preference")

# AsyncTool base class
class AsyncTool(LangchainBaseTool):
    """Base tool with standardized async implementation"""
    async def _arun(self, *args, **kwargs):
        # For tools in modular files, just call _run directly
        return self._run(*args, **kwargs)

class LangchainMemoryContextTool(AsyncTool):
    name: str = "get_memory_context"
    description: str = "Retrieves conversation context from the 3-tier memory system (Redis short-term, MongoDB profile, ChromaDB long-term). Use this to recall previous conversations, user preferences, and relevant semantic memories."
    args_schema: Type[BaseModel] = MemoryContextSchema

    def _run(self, query: str = "", include_long_term: bool = True) -> str:
        logger.info(f"Memory Context Tool: query='{query}', include_long_term={include_long_term}")
        try:
            result = mcp_get_context(query, include_long_term)
            if result["status"] == "success":
                context = result["context"]
                summary = f"Memory Context Retrieved:\n"
                summary += f"• Short-term: {len(context['short_term'])} recent interactions\n"
                summary += f"• Profile: {len(context['profile'].get('rules', []))} rules, {len(context['profile'].get('preferences', {}))} preferences\n"
                summary += f"• Long-term: {len(context['long_term'])} semantic matches\n\n"
                
                # Add recent context
                if context['short_term']:
                    summary += "Recent Conversations:\n"
                    for item in context['short_term'][-3:]:  # Last 3 interactions
                        summary += f"- {item.get('timestamp', '')}: {len(item.get('messages', []))} messages\n"
                
                # Add rules
                if context['profile'].get('rules'):
                    summary += f"\nActive Rules ({len(context['profile']['rules'])}):\n"
                    for rule in context['profile']['rules'][-5:]:  # Last 5 rules
                        summary += f"- [{rule.get('category', 'general')}] {rule.get('rule', '')}\n"
                
                # Add semantic results
                if context['long_term']:
                    summary += f"\nRelevant Past Context:\n"
                    for item in context['long_term'][:3]:  # Top 3 matches
                        summary += f"- (relevance: {item.get('relevance_score', 0):.2f}) {item.get('content', '')[:100]}...\n"
                
                return summary
            else:
                return f"Memory retrieval failed: {result.get('error', 'Unknown error')}"
        except Exception as e:
            logger.error(f"Memory Context Tool error: {e}")
            return f"Memory context error: {str(e)}"

class LangchainMemorySaveTool(LangchainBaseTool):
    name: str = "save_interaction_to_memory"
    description: str = "Saves conversation messages to memory. ONLY use this to store actual chat messages for recall. For user preferences or rules, use add_permanent_rule instead. Input requires 'messages' as a list of message objects like [{'role': 'user', 'content': 'text'}]."
    args_schema: Type[BaseModel] = MemorySaveSchema

    def _run(self, messages: List[Dict[str, str]], tags: Optional[Dict[str, str]] = None) -> str:
        logger.info(f"Memory Save Tool: {len(messages)} messages, tags={tags}")
        try:
            # Handle case where LangChain passes JSON string instead of parsed list
            if isinstance(messages, str):
                import json
                messages = json.loads(messages)
            
            result = mcp_save_interaction(messages, tags)
            if result["status"] == "success":
                return f"Interaction saved successfully: {result['interaction_id']}\nStored in: {', '.join([k for k, v in result['results'].items() if v != 'unavailable'])}"
            else:
                return f"Failed to save interaction: {result.get('error', 'Unknown error')}"
        except Exception as e:
            logger.error(f"Memory Save Tool error: {e}")
            return f"Memory save error: {str(e)}"

    async def _arun(self, messages: List[Dict[str, str]], tags: Optional[Dict[str, str]] = None) -> str:
        # Handle case where LangChain passes JSON string instead of parsed list
        if isinstance(messages, str):
            import json
            messages = json.loads(messages)
            
        return self._run(messages, tags)

class LangchainMemoryRuleTool(LangchainBaseTool):
    name: str = "add_permanent_rule"
    description: str = "Adds a permanent rule or preference to user profile. USE THIS for user preferences like 'I prefer detailed explanations' or behavior requests. Input: rule='text of the rule/preference', category='preference'."
    args_schema: Type[BaseModel] = MemoryRuleSchema

    def _run(self, rule: str, category: str = "general") -> str:
        logger.info(f"Memory Rule Tool: rule='{rule}', category='{category}'")
        try:
            result = mcp_add_permanent_rule(rule, category)
            if result["status"] == "success":
                return f"Rule added successfully: [{category}] {rule}\nRule ID: {result['rule_id']}"
            else:
                return f"Failed to add rule: {result.get('error', 'Unknown error')}"
        except Exception as e:
            logger.error(f"Memory Rule Tool error: {e}")
            return f"Memory rule error: {str(e)}"

    async def _arun(self, rule: str, category: str = "general") -> str:
        return self._run(rule, category)

class LangchainMemoryStatsTool(LangchainBaseTool):
    name: str = "get_memory_stats"
    description: str = "Gets diagnostic information about the memory system status and usage statistics."
    args_schema: Type[BaseModel] = BaseModel

    def _run(self) -> str:
        logger.info("Memory Stats Tool called")
        try:
            result = mcp_get_memory_stats()
            if result["status"] == "success":
                stats = result["stats"]
                summary = "Memory System Statistics:\n"
                summary += f"• Redis: {stats['redis'].get('status', 'unknown')} - {stats['redis'].get('active_contexts', 0)} contexts\n"
                summary += f"• MongoDB: {stats['mongodb'].get('status', 'unknown')} - {stats['mongodb'].get('raw_logs_count', 0)} logs, {stats['mongodb'].get('profiles_count', 0)} profiles\n"
                summary += f"• ChromaDB: {stats['chromadb'].get('status', 'unknown')} - {stats['chromadb'].get('memory_count', 0)} memories\n"
                summary += f"• Storage: {stats['chromadb'].get('storage_path', 'unknown')}"
                return summary
            else:
                return f"Memory stats failed: {result.get('error', 'Unknown error')}"
        except Exception as e:
            logger.error(f"Memory Stats Tool error: {e}")
            return f"Memory stats error: {str(e)}"

    async def _arun(self) -> str:
        return self._run()

def mcp_get_corrections(topic: str = None, limit: int = 5) -> List[Dict]:
    """MCP Tool: Retrieve relevant corrections for prompt injection"""
    return get_memory_system().get_corrections(topic, limit)


if __name__ == "__main__":
    # Test the memory system
    print(" MCP Memory System - Testing...")
    
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
        
        print("All tests completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {e}")