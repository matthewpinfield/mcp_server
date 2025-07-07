#!/usr/bin/env python3
"""
Knowledge Tools - RAG and Memory Management
==========================================

This module contains knowledge and memory tools as per mcp_engineering_plan.md:
- RAGQueryTool (FlutterDoc + CodeSearch from rag.py)
- MemoryManagementTool (all memory tools from memory.py)
"""

import logging
import json
import os
import requests
import threading
from datetime import datetime, timedelta
from typing import Type, List, Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator

from .base import AsyncTool
from config import DEFAULT_SLASH_COMMANDS

logger = logging.getLogger(__name__)

# ===== SLASH COMMAND PROCESSING =====

def process_slash_command(command: str, args: str, custom_commands: Dict[str, Any]) -> str:
    """Process slash commands and return appropriate response"""
    
    # Check custom commands first
    if command in custom_commands:
        custom_cmd = custom_commands[command]
        return f"Executing custom command: {custom_cmd['description']}"
    
    # Check built-in commands
    if command not in DEFAULT_SLASH_COMMANDS:
        available_commands = list(DEFAULT_SLASH_COMMANDS.keys()) + list(custom_commands.keys())
        return f"Unknown command '{command}'. Available commands: {', '.join(available_commands)}"
    
    cmd_config = DEFAULT_SLASH_COMMANDS[command]
    action = cmd_config["action"]
    
    # Route to appropriate tool based on action
    try:
        if action == "save_rule":
            result = mcp_add_permanent_rule(args, "preference")
            if result.get("status") == "success":
                rule_id = result.get('rule_id', 'unknown')
                return f"✅ Rule added: {args}\nRule ID: {rule_id}"
            else:
                return f"❌ Failed to add rule: {result.get('error', 'Unknown error')}"
                
        elif action == "save_memory":
            # Convert summary to message format
            messages = [{"role": "user", "content": f"Remember: {args}"}]
            result = mcp_save_interaction(messages, {"type": "user_memory"})
            if result.get("status") == "success":
                return f"✅ Information saved: {args}"
            else:
                return f"❌ Failed to save: {result.get('error', 'Unknown error')}"
                
        elif action == "get_memory":
            result = mcp_get_context(args, include_long_term=True)
            if result.get("status") == "success":
                context = result.get("context", {})
                response = f"📋 Memory search results for '{args}':\n"
                response += f"• {len(context.get('short_term', []))} recent interactions\n"
                response += f"• {len(context.get('profile', {}).get('rules', []))} rules\n"
                response += f"• {len(context.get('long_term', []))} semantic matches"
                return response
            else:
                return f"❌ Memory search failed: {result.get('error', 'Unknown error')}"
                
        elif action == "correct" or action == "fix":
            result = mcp_add_correction(args)
            if result.get("status") == "success":
                return f"✅ Correction saved: {args}"
            else:
                return f"❌ Failed to save correction: {result.get('error', 'Unknown error')}"
                
        elif action == "list_rules":
            result = mcp_list_rules(args if args.strip() else None)
            if result.get("status") == "success":
                rules = result.get("rules", [])
                if not rules:
                    return f"📋 No rules found{' matching \"' + args + '\"' if args.strip() else ''}"
                response = f"📋 Found {len(rules)} rule(s):\n"
                for rule in rules[:10]:  # Show max 10 rules
                    rule_id = rule.get("id", "unknown")
                    rule_text = rule.get("rule", "")
                    category = rule.get("category", "general")
                    response += f"• [{rule_id}] ({category}): {rule_text}\n"
                if len(rules) > 10:
                    response += f"... and {len(rules) - 10} more rules"
                return response
            else:
                return f"❌ Failed to list rules: {result.get('error', 'Unknown error')}"
                
        elif action == "delete_rule":
            if not args.strip():
                return "❌ Please provide a rule ID to delete. Usage: /delete_rule <rule_id>"
            result = mcp_delete_rule(args.strip())
            if result.get("status") == "success":
                return f"✅ Rule {args.strip()} deleted successfully"
            else:
                return f"❌ Failed to delete rule: {result.get('error', 'Unknown error')}"
                
        elif action == "change_rule":
            parts = args.split(' ', 1)
            if len(parts) < 2:
                return "❌ Please provide rule ID and new text. Usage: /change_rule <rule_id> <new_text>"
            rule_id, new_text = parts
            result = mcp_update_rule(rule_id.strip(), new_text.strip())
            if result.get("status") == "success":
                return f"✅ Rule {rule_id} updated successfully"
            else:
                return f"❌ Failed to update rule: {result.get('error', 'Unknown error')}"
                
        elif action == "list_commands":
            category = args.strip().lower() if args else None
            if category:
                commands = {k: v for k, v in DEFAULT_SLASH_COMMANDS.items() if v["category"] == category}
            else:
                commands = DEFAULT_SLASH_COMMANDS
            
            result = f"Available {category + ' ' if category else ''}commands:\n"
            for cmd, info in commands.items():
                result += f"{cmd}: {info['description']}\n"
            return result
            
        elif action == "command_help":
            if args in DEFAULT_SLASH_COMMANDS:
                cmd_info = DEFAULT_SLASH_COMMANDS[args]
                return f"{args}: {cmd_info['description']}\nUsage: {cmd_info['usage']}\nExample: {cmd_info['example']}"
            else:
                return f"No help available for '{args}'"
                
        else:
            return f"Command '{command}' recognized but not yet implemented (action: {action})"
            
    except Exception as e:
        logger.error(f"Error executing slash command {command}: {e}")
        return f"Error executing command '{command}': {str(e)}"

# ===== MEMORY SYSTEM IMPLEMENTATION =====

# Memory system imports
import redis
import pymongo
import chromadb
from chromadb.utils import embedding_functions
from chromadb.api.types import Documents, Embeddings
from typing import cast
import ollama
import hashlib
from datetime import datetime, timedelta

# Suppress ChromaDB telemetry logging
import logging
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.WARNING)

# Configuration from superceeded/mcp_memory.py
SSD_BASE_DATA_PATH = "/mnt/caseSSD/mcp_server_data/"
NAS_BASE_DATA_PATH = "/mnt/my_nas_mcp_share/archives/"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
MONGODB_URI = "mongodb://localhost:27017/"
MONGODB_DATABASE = "mcp_memory"
CHROMA_TIER3_PATH = os.path.join(SSD_BASE_DATA_PATH, "tier3_memory_db")
CHROMA_NAS_PATH = os.path.join(NAS_BASE_DATA_PATH, "memory_vector_db")
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text:latest"
DEFAULT_USER = "default_user"
CONTEXT_WINDOW_HOURS = 24
ARCHIVE_AFTER_DAYS = 14
NAS_ARCHIVE_AFTER_DAYS = 30
TIER_2_WARNING_THRESHOLD = 1000


class MemorySystem:
    """Advanced 3-Tier Memory System for LLM"""
    
    def __init__(self):
        self.user = DEFAULT_USER
        self.redis_client = None
        self.mongo_client = None
        self.mongo_db = None
        self.chroma_tier3_client = None
        self.chroma_nas_client = None
        self.tier3_memory = None
        self.nas_archive = None
        self.embedding_func = None
        self._initialize_databases()
    
    def _initialize_databases(self):
        """Initialize all database connections with 4-tier architecture"""
        try:
            self._setup_redis()
            self._setup_mongodb()
            self._setup_chromadb_tier3()
            self._setup_chromadb_nas()
            logger.debug("All 4-tier database connections initialized successfully")
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
            self.redis_client.ping()
            logger.debug("Redis connection established")
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
            self.mongo_client.admin.command('ping')
            self.mongo_db = self.mongo_client[MONGODB_DATABASE]
            self._setup_mongodb_collections()
            logger.debug("MongoDB connection established")
        except Exception as e:
            logger.warning(f"MongoDB connection failed: {e} (will use fallback)")
            self.mongo_client = None
            self.mongo_db = None
    
    def _setup_mongodb_collections(self):
        """Set up MongoDB collections and indexes"""
        if self.mongo_db is None:
            raise ConnectionError("MongoDB database not initialized")
        profiles = self.mongo_db.profiles
        profiles.create_index("user_id")
        logs = self.mongo_db.raw_logs
        logs.create_index([("timestamp", 1), ("user_id", 1)])
        
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
        
        if not os.path.exists(nas_mount_point):
            logger.error(f"NAS mount point missing: {nas_mount_point}")
            return False
        
        try:
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
        
        try:
            test_file = os.path.join(nas_mount_point, ".nas_connectivity_test")
            with open(test_file, 'w') as f:
                f.write(f"connectivity_test_{time.time()}")
            os.remove(test_file)
            logger.debug("NAS online and accessible")
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
            os.makedirs(CHROMA_TIER3_PATH, exist_ok=True)
            self.chroma_tier3_client = chromadb.PersistentClient(path=CHROMA_TIER3_PATH)
            
            if not self.embedding_func:
                class OllamaEmbeddingFunction(embedding_functions.EmbeddingFunction):
                    def __init__(self, model_name: str):
                        self.model_name = model_name
                    
                    def __call__(self, input: Documents) -> Embeddings:
                        embeddings = []
                        for text in input:
                            try:
                                result = ollama.embeddings(model=self.model_name, prompt=text)
                                embeddings.append(result['embedding'])
                            except Exception as e:
                                logger.error(f"Ollama embedding error for text '{text[:50]}...': {e}")
                                embeddings.append([0.0] * 768)
                        return cast(Embeddings, embeddings)
                
                self.embedding_func = OllamaEmbeddingFunction(DEFAULT_EMBEDDING_MODEL)
            
            self.tier3_memory = self.chroma_tier3_client.get_or_create_collection(
                name="tier3_memory",
                embedding_function=self.embedding_func
            )
            
            logger.debug(f"ChromaDB Tier 3 initialized with {self.tier3_memory.count()} memories")
        except Exception as e:
            logger.error(f"ChromaDB SSD connection failed: {e}")
            logger.warning("Falling back to in-memory storage for Tier 3")
            # Set up fallback in-memory storage
            self.chroma_tier3_client = None
            self.tier3_memory = None
            self.embedding_func = None

    def _setup_chromadb_nas(self):
        """Initialize ChromaDB on NAS for Tier 3b (long-term archive 30+ days)"""
        try:
            if not self._check_and_mount_nas():
                logger.warning("NAS not available - Tier 3b (long-term archive) will be limited")
                self.chroma_nas_client = None
                self.archive_memory = None
                return
            
            os.makedirs(CHROMA_NAS_PATH, exist_ok=True)
            
            test_file = os.path.join(CHROMA_NAS_PATH, ".write_test")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                logger.debug("NAS write access confirmed")
            except Exception as e:
                logger.warning(f"NAS write access failed: {e} - Tier 3b will be read-only")
            
            self.chroma_nas_client = chromadb.PersistentClient(path=CHROMA_NAS_PATH)
            
            self.nas_archive = self.chroma_nas_client.get_or_create_collection(
                name="nas_archive",
                embedding_function=self.embedding_func
            )
            
            logger.debug(f"ChromaDB NAS archive initialized with {self.nas_archive.count()} archived memories")
        except Exception as e:
            logger.warning(f"ChromaDB NAS connection failed: {e} - long-term archive unavailable")
            self.chroma_nas_client = None
            self.nas_archive = None
    
    def save_interaction(self, messages: List[Dict], tags: Optional[Dict] = None) -> Dict:
        """Core memory write operation - saves conversation to Tier 1 (Redis) only as per architecture"""
        try:
            timestamp = datetime.now()
            interaction_id = f"interaction_{timestamp.timestamp()}"
            
            # Prepare conversation text for semantic storage during migration
            conversation_text = self._format_messages_for_search(messages)
            
            # Prepare metadata for migration to Tier 3
            metadata = {
                "timestamp": timestamp.isoformat(),
                "user_id": DEFAULT_USER,
                "message_count": len(messages),
                "interaction_id": interaction_id,
            }
            if tags:
                metadata.update(tags)
            
            # TIER 1 ONLY: Save to Redis with 14-day TTL for migration
            if self.redis_client is not None:
                conversation_data = {
                    "text": conversation_text,
                    "metadata": metadata,
                    "messages": messages,  # Keep original messages for context retrieval
                    "timestamp": timestamp.isoformat()
                }
                self.redis_client.setex(
                    f"interaction:{interaction_id}",
                    86400 * 14,  # 14 days in seconds
                    json.dumps(conversation_data, default=str)
                )
                logger.info(f"Saved to Tier 1 (Redis) for 14-day migration: {interaction_id}")
                return {"status": "success", "interaction_id": interaction_id, "tier": "redis"}
            else:
                logger.error("Redis (Tier 1) not available - conversation not saved")
                return {"status": "error", "error": "Redis unavailable"}
                
        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
            return {"status": "error", "error": str(e)}
    
    def migrate_tier1_to_tier3(self) -> Dict:
        """Migrate conversations from Tier 1 (Redis) to Tier 3 (ChromaDB) after 14 days"""
        try:
            if self.redis_client is None or self.tier3_memory is None:
                return {"status": "error", "error": "Redis or ChromaDB unavailable for migration"}
            
            migrated_count = 0
            expired_keys = []
            
            # Get all interaction keys from Redis
            interaction_keys = self.redis_client.keys("interaction:*")
            
            for key in interaction_keys:
                try:
                    # Get TTL to check if it's near expiration (migrate when < 1 day left)
                    ttl = self.redis_client.ttl(key)
                    
                    if ttl <= 86400:  # Less than 1 day left, migrate to Tier 3
                        conversation_data_str = self.redis_client.get(key)
                        if conversation_data_str:
                            conversation_data = json.loads(conversation_data_str)
                            
                            # Migrate to ChromaDB
                            self.tier3_memory.add(
                                documents=[conversation_data["text"]],
                                metadatas=[conversation_data["metadata"]],
                                ids=[conversation_data["metadata"]["interaction_id"]]
                            )
                            
                            # Remove from Redis after successful migration
                            self.redis_client.delete(key)
                            migrated_count += 1
                            logger.info(f"Migrated {key} from Tier 1 to Tier 3")
                            
                    elif ttl == -1:  # Key has no expiration, shouldn't happen but clean up
                        expired_keys.append(key)
                        
                except Exception as e:
                    logger.error(f"Failed to migrate {key}: {e}")
                    continue
            
            # Clean up any keys without proper expiration
            for key in expired_keys:
                self.redis_client.delete(key)
                logger.warning(f"Cleaned up key without expiration: {key}")
            
            logger.info(f"Migration complete: {migrated_count} conversations moved to Tier 3")
            return {
                "status": "success", 
                "migrated_count": migrated_count,
                "cleaned_up": len(expired_keys)
            }
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def migrate_tier3_ssd_to_nas(self, nas_chromadb_path: str = "/mnt/my_nas_mcp_share/archives/memory_vector_db") -> Dict:
        """Migrate Tier 3 conversations from local SSD to NAS ChromaDB after 30 days"""
        try:
            if self.tier3_memory is None:
                return {"status": "error", "error": "ChromaDB Tier 3a (SSD) unavailable for NAS migration"}
            
            import chromadb
            from datetime import datetime, timedelta
            
            # Calculate 30-day cutoff date (as Unix timestamp for ChromaDB compatibility)
            cutoff_date = datetime.now() - timedelta(days=30)
            cutoff_timestamp = cutoff_date.timestamp()
            
            # Query conversations older than 30 days from Tier 3a (SSD)
            # Get all conversations (ChromaDB returns IDs automatically with get())
            all_results = self.tier3_memory.get(include=["documents", "metadatas"])
            
            # Filter results by timestamp in Python (more reliable than ChromaDB where clause)
            old_conversations = {"documents": [], "metadatas": [], "ids": []}
            
            # ChromaDB .get() returns ids in the result automatically
            ids = all_results.get("ids", [])
            if ids:
                for i, conversation_id in enumerate(ids):
                    metadata = all_results["metadatas"][i] if i < len(all_results["metadatas"]) else {}
                    
                    # Check timestamp in metadata
                    conversation_timestamp = metadata.get("timestamp")
                    if conversation_timestamp:
                        try:
                            # Handle both ISO string and Unix timestamp formats
                            if isinstance(conversation_timestamp, str):
                                conv_dt = datetime.fromisoformat(conversation_timestamp.replace('Z', '+00:00'))
                                conv_ts = conv_dt.timestamp()
                            else:
                                conv_ts = float(conversation_timestamp)
                                
                            # If older than 30 days, include in migration
                            if conv_ts < cutoff_timestamp:
                                old_conversations["documents"].append(all_results["documents"][i])
                                old_conversations["metadatas"].append(all_results["metadatas"][i])
                                old_conversations["ids"].append(conversation_id)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid timestamp format for {conversation_id}: {e}")
                            continue
            
            results = old_conversations
            
            if not results["ids"]:
                logger.info("No conversations older than 30 days found for NAS migration")
                return {"status": "success", "migrated_count": 0, "message": "No conversations to migrate"}
            
            # Initialize NAS ChromaDB (Tier 3b)
            nas_client = chromadb.PersistentClient(path=nas_chromadb_path)
            nas_archive = nas_client.get_or_create_collection(
                name="nas_archive",
                metadata={"description": "Long-term memory archive (30+ days)"}
            )
            
            # Migrate conversations to NAS ChromaDB
            nas_archive.add(
                documents=results["documents"],
                metadatas=results["metadatas"], 
                ids=results["ids"]
            )
            
            # Remove from local SSD ChromaDB after successful migration
            self.tier3_memory.delete(ids=results["ids"])
            
            migrated_count = len(results["ids"])
            logger.info(f"Migrated {migrated_count} conversations from Tier 3a (SSD) to Tier 3b (NAS): {nas_chromadb_path}")
            
            return {
                "status": "success",
                "migrated_count": migrated_count,
                "nas_path": nas_chromadb_path,
                "cutoff_date": cutoff_date.isoformat(),
                "collection": "nas_archive"
            }
            
        except Exception as e:
            logger.error(f"NAS migration failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_key_value(self, key: str) -> Any:
        """Get a specific key-value pair from profile data (MongoDB)"""
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
        """Set a specific key-value pair in profile data (MongoDB)"""
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
        """Core memory read operation - retrieves context from all 3 tiers"""
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
        """Administrative operation - adds permanent rule to user profile"""
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
    
    def add_correction(self, ai_response: str, user_correction: str, topic: Optional[str] = None) -> Dict:
        """Store AI correction for learning from mistakes"""
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
            
            result = self.mongo_db.correction_logs.insert_one(correction_data)
            
            if result.inserted_id:
                logger.info(f"Correction stored: {correction_data['id']}")
                return {"status": "success", "correction_id": correction_data["id"]}
            else:
                return {"status": "error", "error": "Failed to insert correction"}
                
        except Exception as e:
            logger.error(f"Failed to add correction: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_corrections(self, topic: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """Retrieve relevant corrections for prompt injection"""
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
        """Diagnostic operation - returns memory system statistics"""
        try:
            stats = {
                "timestamp": datetime.now().isoformat(),
                "redis_status": "disconnected",
                "mongodb_status": "disconnected",
                "chromadb_status": "disconnected",
                "redis_keys": 0,
                "mongodb_rules": 0,
                "chromadb_documents": 0,
                "overall_health": "unknown"
            }
            
            # Redis stats
            if self.redis_client is not None:
                try:
                    self.redis_client.ping()  # Test connection
                    interaction_keys = self.redis_client.keys("interaction:*")
                    redis_key_count = len(cast(list, interaction_keys))
                    stats["redis_status"] = "connected"
                    stats["redis_keys"] = redis_key_count
                except Exception as e:
                    logger.debug(f"Redis stats error: {e}")
                    stats["redis_status"] = "error"
            else:
                logger.debug("Redis client is None")
            
            # MongoDB stats
            if self.mongo_db is not None:
                try:
                    self.mongo_client.admin.command('ping')  # Test connection
                    profile = self.mongo_db.profiles.find_one({"user_id": DEFAULT_USER})
                    rule_count = len(profile.get("rules", [])) if profile else 0
                    stats["mongodb_status"] = "connected"
                    stats["mongodb_rules"] = rule_count
                except Exception as e:
                    logger.debug(f"MongoDB stats error: {e}")
                    stats["mongodb_status"] = "error"
            else:
                logger.debug("MongoDB client is None")
            
            # ChromaDB stats
            if self.tier3_memory is not None:
                try:
                    count = self.tier3_memory.count()
                    stats["chromadb_status"] = "connected"
                    stats["chromadb_documents"] = count
                except Exception as e:
                    logger.debug(f"ChromaDB stats error: {e}")
                    stats["chromadb_status"] = "error"
            else:
                logger.debug("ChromaDB tier3_memory is None")
            
            # Overall health
            connected_systems = sum(1 for status in [stats["redis_status"], stats["mongodb_status"], stats["chromadb_status"]] if status == "connected")
            if connected_systems == 3:
                stats["overall_health"] = "excellent"
            elif connected_systems == 2:
                stats["overall_health"] = "good"
            elif connected_systems == 1:
                stats["overall_health"] = "limited"
            else:
                stats["overall_health"] = "offline"
            
            logger.debug("Memory stats retrieved")
            return {"status": "success", "stats": stats}
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"status": "error", "error": str(e)}
    
    # Helper methods
    
    def _get_redis_context(self) -> List[Dict]:
        """Retrieve recent conversation context from Redis - LIMIT TO RECENT ONLY"""
        if self.redis_client is None:
            return []
            
        try:
            keys = self.redis_client.keys("interaction:*")
            contexts = []
            
            for key in cast(list, keys):
                data = self.redis_client.get(key)
                if data:
                    interaction_data = json.loads(cast(str, data))
                    # Extract the text content for context
                    contexts.append({
                        "content": interaction_data.get("text", ""),
                        "timestamp": interaction_data.get("timestamp", ""),
                        "metadata": interaction_data.get("metadata", {}),
                        "messages": interaction_data.get("messages", [])
                    })
            
            # Sort by timestamp and limit to recent 5 interactions only
            contexts.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # CRITICAL FIX: Only return last 5 interactions to prevent memory overflow
            return contexts[:5]
            
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
                profile.pop("_id", None)
                return profile
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get MongoDB profile: {e}")
            return {}
    
    def _search_long_term_memory(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search long-term semantic memory (Tier 3a SSD + Tier 3b NAS)"""
        try:
            all_results = []
            
            # Search Tier 3a (SSD ChromaDB) first
            if self.tier3_memory is not None:
                try:
                    ssd_results = self.tier3_memory.query(
                        query_texts=[query],
                        n_results=n_results
                    )
                    if ssd_results and ssd_results.get("documents"):
                        documents = ssd_results.get("documents", [[]])
                        metadatas = ssd_results.get("metadatas", [[]])
                        distances = ssd_results.get("distances", [[]])
                        
                        if documents and len(documents) > 0 and documents[0]:
                            for i, doc in enumerate(documents[0]):
                                metadata = metadatas[0][i] if metadatas and len(metadatas[0]) > i else {}
                                distance = distances[0][i] if distances and len(distances[0]) > i else 0.0
                                
                                all_results.append({
                                    "content": doc,
                                    "metadata": {**metadata, "source": "tier3a_ssd"},
                                    "similarity": 1.0 - distance,
                                    "source": "tier3a_ssd"
                                })
                except Exception as e:
                    logger.warning(f"Tier 3a SSD search failed: {e}")
            
            # Search Tier 3b (NAS ChromaDB) for archived conversations
            try:
                import chromadb
                nas_client = chromadb.PersistentClient(path="/mnt/my_nas_mcp_share/archives/memory_vector_db")
                nas_archive = nas_client.get_collection(name="nas_archive")
                
                nas_results = nas_archive.query(
                    query_texts=[query],
                    n_results=n_results
                )
                
                if nas_results and nas_results.get("documents"):
                    nas_documents = nas_results.get("documents", [[]])
                    nas_metadatas = nas_results.get("metadatas", [[]])
                    nas_distances = nas_results.get("distances", [[]])
                    
                    if nas_documents and len(nas_documents) > 0 and nas_documents[0]:
                        for i, doc in enumerate(nas_documents[0]):
                            metadata = nas_metadatas[0][i] if nas_metadatas and len(nas_metadatas[0]) > i else {}
                            distance = nas_distances[0][i] if nas_distances and len(nas_distances[0]) > i else 0.0
                            
                            all_results.append({
                                "content": doc,
                                "metadata": {**metadata, "source": "tier3b_nas"},
                                "similarity": 1.0 - distance,
                                "source": "tier3b_nas"
                            })
                            
            except Exception as e:
                logger.debug(f"Tier 3b NAS search failed (may not exist yet): {e}")
            
            # Sort by similarity and limit results
            all_results.sort(key=lambda x: x["similarity"], reverse=True)
            results = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
            
            # Convert back to expected format
            for result in all_results[:n_results]:
                results["documents"][0].append(result["content"])
                results["metadatas"][0].append(result["metadata"])
                results["distances"][0].append(1.0 - result["similarity"])
            
            formatted_results = []
            if results and results.get("documents"):
                documents = results.get("documents", [[]])
                metadatas = results.get("metadatas", [[]])
                distances = results.get("distances", [[]])
                
                if documents and len(documents) > 0 and documents[0]:
                    for i, doc in enumerate(documents[0]):
                        metadata = {}
                        distance = 0.0
                        
                        if (metadatas and len(metadatas) > 0 and metadatas[0] and 
                            len(metadatas[0]) > i):
                            metadata = metadatas[0][i] or {}
                        
                        if (distances and len(distances) > 0 and distances[0] and 
                            len(distances[0]) > i):
                            distance = distances[0][i]
                        
                        formatted_results.append({
                            "content": doc,
                            "metadata": metadata,
                            "relevance_score": 1.0 - distance
                        })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to search long-term memory: {e}")
            return []
    
    def _format_messages_for_search(self, messages: List[Dict]) -> str:
        """Convert messages to searchable text for ChromaDB"""
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
    
    def shutdown(self):
        """Properly close all database connections"""
        logger.info("Shutting down memory system...")
        
        try:
            # Close Redis connection
            if self.redis_client is not None:
                self.redis_client.close()
                logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
        
        try:
            # Close MongoDB connection
            if self.mongo_client is not None:
                self.mongo_client.close()
                logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")
        
        try:
            # ChromaDB clients don't need explicit closing, but reset references
            if self.chroma_tier3_client is not None:
                self.chroma_tier3_client = None
                self.tier3_memory = None
                logger.info("ChromaDB Tier 3 connection reset")
        except Exception as e:
            logger.error(f"Error resetting ChromaDB Tier 3: {e}")
            
        try:
            if self.chroma_nas_client is not None:
                self.chroma_nas_client = None
                self.nas_archive = None
                logger.info("ChromaDB NAS connection reset")
        except Exception as e:
            logger.error(f"Error resetting ChromaDB NAS: {e}")
        
        logger.info("Memory system shutdown complete")


# Global memory system instance with thread-safe initialization
memory_system = None
_memory_system_lock = threading.Lock()

def get_memory_system() -> MemorySystem:
    """Get or create the global memory system instance (thread-safe)"""
    global memory_system
    if memory_system is None:
        with _memory_system_lock:
            # Double-check locking pattern
            if memory_system is None:
                memory_system = MemorySystem()
    return memory_system


# MCP Tool Interface Functions
def mcp_get_context(query: Optional[str] = None, include_long_term: bool = True) -> Dict:
    """MCP Tool: Retrieve memory context for conversation"""
    try:
        # Input validation
        if query is not None:
            if not isinstance(query, str):
                return {"status": "error", "error": "Query must be a string or None", "context": {}}
            if len(query.strip()) > 1000:
                return {"status": "error", "error": "Query too long (max 1000 characters)", "context": {}}
            # Sanitize query - remove potentially dangerous characters
            query = query.strip()
            
        if not isinstance(include_long_term, bool):
            return {"status": "error", "error": "include_long_term must be a boolean", "context": {}}
            
        result = get_memory_system().get_context(query, include_long_term)
        if result.get("status") == "success" and "context" in result:
            # Convert any datetime objects to strings for JSON serialization
            context = result["context"]
            
            # Fix datetime serialization in short_term memories
            if "short_term" in context:
                for item in context["short_term"]:
                    if "timestamp" in item and hasattr(item["timestamp"], "isoformat"):
                        item["timestamp"] = item["timestamp"].isoformat()
            
            # Fix datetime serialization in profile data
            if "profile" in context and context["profile"]:
                profile = context["profile"]
                for field in ["created_at", "updated_at"]:
                    if field in profile and hasattr(profile[field], "isoformat"):
                        profile[field] = profile[field].isoformat()
                
                # Fix datetime in rules
                if "rules" in profile:
                    for rule in profile["rules"]:
                        for field in ["added_at", "updated_at"]:
                            if field in rule and hasattr(rule[field], "isoformat"):
                                rule[field] = rule[field].isoformat()
        
        return result
    except Exception as e:
        logger.error(f"mcp_get_context error: {e}")
        return {"status": "error", "error": str(e)}

def mcp_save_interaction(messages: List[Dict], tags: Optional[Dict] = None) -> Dict:
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

def mcp_add_correction(correction_text: str) -> Dict:
    """MCP Tool: Store AI correction for learning from mistakes"""
    return get_memory_system().add_correction("", correction_text)

def mcp_get_corrections(topic: Optional[str] = None, limit: int = 5) -> List[Dict]:
    """MCP Tool: Retrieve relevant corrections for prompt injection"""
    return get_memory_system().get_corrections(topic, limit)

# Memory wrapper function for backward compatibility
def mcp_list_rules(search_query: Optional[str] = None) -> Dict:
    """MCP Tool: List rules with optional search filter"""
    try:
        memory_system = get_memory_system()
        if memory_system.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}
            
        profile = memory_system.mongo_db.profiles.find_one({"user_id": DEFAULT_USER})
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
        
        return {"status": "success", "rules": rules, "count": len(rules)}
    except Exception as e:
        logger.error(f"mcp_list_rules error: {e}")
        return {"status": "error", "error": str(e)}

def mcp_delete_rule(rule_id: str) -> Dict:
    """MCP Tool: Delete rule by ID"""
    try:
        memory_system = get_memory_system()
        if memory_system.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}
            
        result = memory_system.mongo_db.profiles.update_one(
            {"user_id": DEFAULT_USER},
            {"$pull": {"rules": {"id": rule_id}}}
        )
        
        if result.modified_count > 0:
            return {"status": "success", "deleted_count": result.modified_count}
        else:
            return {"status": "error", "error": f"Rule with ID {rule_id} not found"}
    except Exception as e:
        logger.error(f"mcp_delete_rule error: {e}")
        return {"status": "error", "error": str(e)}

def mcp_update_rule(rule_id: str, new_rule: str) -> Dict:
    """MCP Tool: Update rule by ID"""
    try:
        memory_system = get_memory_system()
        if memory_system.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}
            
        result = memory_system.mongo_db.profiles.update_one(
            {"user_id": DEFAULT_USER, "rules.id": rule_id},
            {"$set": {"rules.$.rule": new_rule, "rules.$.updated_at": datetime.now()}}
        )
        
        if result.modified_count > 0:
            return {"status": "success", "updated_count": result.modified_count}
        else:
            return {"status": "error", "error": f"Rule with ID {rule_id} not found"}
    except Exception as e:
        logger.error(f"mcp_update_rule error: {e}")
        return {"status": "error", "error": str(e)}

def mcp_get_memory_context(key_or_query: str):
    """Wrapper function to get memory context - handles both key lookups and queries"""
    try:
        if key_or_query in ["custom_slash_commands", "current_project", "workspace_settings"]:
            key_value = mcp_get_key_value(key_or_query)
            # Wrap key-value result in proper context structure
            return {"status": "success", "context": {"key_value": key_value, "profile": {}, "short_term": [], "long_term": []}}
        
        result = mcp_get_context(key_or_query, include_long_term=True)
        
        # Ensure JSON serialization works by converting any remaining datetime objects
        if isinstance(result, dict):
            import json
            try:
                # Test if it can be serialized
                json.dumps(result, default=str)
                return result
            except (TypeError, ValueError):
                # If serialization fails, return error dict instead of string
                return {"status": "error", "error": "Serialization failed", "context": {}}
        
        return result
    except Exception as e:
        logger.error(f"mcp_get_memory_context error: {e}")
        return {"status": "error", "error": f"Memory error: {str(e)}", "context": {}}

def mcp_migrate_tier1_to_tier3() -> Dict:
    """Public function to trigger Tier 1 to Tier 3 migration (14-day rule)"""
    memory_system = MemorySystem()
    return memory_system.migrate_tier1_to_tier3()

def mcp_migrate_tier3_to_nas(nas_chromadb_path: str = "/mnt/my_nas_mcp_share/archives/memory_vector_db") -> Dict:
    """Public function to trigger Tier 3 SSD to NAS migration (30-day rule)"""
    memory_system = MemorySystem()
    return memory_system.migrate_tier3_ssd_to_nas(nas_chromadb_path)

# ===== SCHEMAS =====

class FlutterDocSchema(BaseModel):
    query: str = Field(description="Flutter/Dart documentation query")
    max_results: int = Field(description="Maximum results", default=5)

class CodeSearchSchema(BaseModel):
    query: str = Field(description="Code example search query")
    max_results: int = Field(description="Maximum results", default=5)

class MemoryContextSchema(BaseModel):
    query: str = Field(description="Query or key to retrieve from memory system")
    include_long_term: bool = Field(default=True, description="Include long-term memory in search")

# --- START: Flexible Schema for Save Tool ---
class MemorySaveSchema(BaseModel):
    """A flexible schema that accepts either a simple summary or a full message list."""
    interaction_summary: Optional[str] = Field(None, description="A brief text summary of the interaction to be saved. Use this for simple notes.")
    messages: Optional[List[Dict[str, str]]] = Field(None, description="The full list of chat messages to save for complete context.")
    tags: Optional[Any] = Field(None, description="Tags for categorization. Can be a simple list of strings ['tag1', 'tag2'] or a dictionary {'key': 'value'}.")

    @model_validator(mode='after')
    def check_one_content_field(cls, self):
        if not self.interaction_summary and not self.messages:
            raise ValueError('Either "interaction_summary" or "messages" must be provided to save to memory.')
        return self
# --- END: Flexible Schema for Save Tool ---

class MemoryRuleSchema(BaseModel):
    rule: str = Field(description="The rule or preference text. Example: 'I prefer detailed explanations' or 'Always use TypeScript for web projects'")
    category: str = Field(description="Category like 'preference', 'coding_style', 'communication', etc.", default="preference")

class MemoryStatsSchema(BaseModel):
    pass  # No parameters needed

class MemoryCorrectionSchema(BaseModel):
    correction_text: str = Field(description="Correction to store for future learning")

# ===== RAG TOOL CLASSES =====

class LangchainFlutterDocTool(AsyncTool):
    name: str = "query_flutter_dart_documentation"
    description: str = "Queries a knowledge base of Flutter/Dart documentation to answer technical questions about Flutter or Dart. Use this for specific Flutter/Dart coding questions, error explanations, or finding documentation."
    args_schema: type[BaseModel] = FlutterDocSchema

    def _run(self, query: str, max_results: int = 10) -> str:
        logger.info(f"Docs Search: Received query: '{query}'")
        try:
            import requests
            from config import RAG_SERVER_ENDPOINT, REQUEST_TIMEOUT
            
            response = requests.post(RAG_SERVER_ENDPOINT, params={"query": query, "limit": max_results}, timeout=REQUEST_TIMEOUT, json={})
            response.raise_for_status()
            
            try:
                rag_json = response.json()
                if isinstance(rag_json, dict) and "results" in rag_json:
                    # Handle dual endpoint server response format
                    results = rag_json["results"]
                    if results:
                        result_text = f" **Flutter/Dart Documentation Results** (Database: {rag_json.get('database', 'unknown')})\n\n"
                        for i, result in enumerate(results[:3], 1):  # Show top 3 results
                            text = result.get('text', '').strip()
                            if len(text) > 800:
                                text = text[:800] + "..."
                            result_text += f"**Result {i}:**\n{text}\n\n"
                    else:
                        result_text = "No relevant documentation found."
                elif isinstance(rag_json, dict):
                    # Fallback for other response formats
                    if "answer" in rag_json: result_text = rag_json["answer"]
                    elif "text" in rag_json: result_text = rag_json["text"]
                    elif "content" in rag_json: result_text = rag_json["content"]
                    else: result_text = json.dumps(rag_json)
                else: result_text = json.dumps(rag_json)
            except ValueError: result_text = response.text
            
            logger.info(f"Docs Search: Successfully retrieved documentation (length: {len(result_text)}).")
            return f"Documentation found for query '{query}':\n{result_text}"
            
        except Exception as e:
            logger.error(f"Docs Search: Error: {e}")
            return f"Error during RAG tool execution: {str(e)}"

class LangchainCodeSearchTool(AsyncTool):
    name: str = "search_code_examples"
    description: str = "Search Python and Flutter code examples from the code database using RAG system"
    args_schema: type[BaseModel] = CodeSearchSchema

    def _run(self, query: str, max_results: int = 10) -> str:
        logger.info(f"Code Search: Received query: '{query}', max_results={max_results}")
        try:
            import requests
            from config import RAG_CODE_ENDPOINT, REQUEST_TIMEOUT
            
            response = requests.post(RAG_CODE_ENDPOINT, params={"query": query, "limit": max_results}, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            result = response.json()
            
            # Handle dual endpoint response format
            if result and result.get('results'):
                docs = result.get('results', [])
                if docs:
                    formatted_response = f"Code Examples for '{query}':\n\n"
                    for i, doc in enumerate(docs, 1):
                        title = doc.get('title', doc.get('source', 'Unknown'))
                        content = doc.get('text', doc.get('content', ''))[:400] + "..."
                        source = doc.get('source', 'Unknown')
                        
                        formatted_response += f"{i}. **{title}**\n"
                        formatted_response += f"   Source: {source}\n"
                        formatted_response += f"   {content}\n\n"
                    
                    logger.info(f"Code Search: Found {len(docs)} results")
                    return formatted_response
                else:
                    return f"No code examples found for '{query}'"
            else:
                return f"Code search failed: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            logger.error(f"Code Search Tool error: {e}")
            return f"Code search error: {str(e)}"

# ===== MEMORY TOOL CLASSES =====

class LangchainMemoryContextTool(AsyncTool):
    name: str = "get_memory_context"
    description: str = (
        "Retrieves relevant context from the 3-tier memory system (Redis + MongoDB + ChromaDB). "
        "Searches conversation history, user preferences, and long-term archives. "
        "Use for: recalling previous discussions, user preferences, project context, or any stored information."
    )
    args_schema: type[BaseModel] = MemoryContextSchema

    def _run(self, query: str = "", include_long_term: bool = True) -> str:
        logger.info(f"Memory Context Tool: query='{query}', include_long_term={include_long_term}")
        try:
            result = mcp_get_context(query, include_long_term)
            if result.get("status") == "success":
                context = result.get("context", {})
                summary = f"Memory Context Retrieved:\n"
                summary += f"• Short-term: {len(context.get('short_term', []))} recent interactions\n"
                summary += f"• Profile: {len(context.get('profile', {}).get('rules', []))} rules, {len(context.get('profile', {}).get('preferences', {}))} preferences\n"
                summary += f"• Long-term: {len(context.get('long_term', []))} semantic matches\n\n"
                
                # Add recent context from Tier 1 Redis (FAST)
                if context.get('short_term'):
                    summary += "**Recent Conversations (Tier 1 Redis - Fast):**\n"
                    for item in context['short_term'][-3:]:  # Last 3 interactions
                        summary += f"- {item.get('timestamp', '')}: {len(item.get('messages', []))} messages\n"
                        # If this is a query search, show matching content
                        if query and item.get('content'):
                            content = item.get('content', '')
                            if query.lower() in content.lower():
                                summary += f"  Match: {content[:200]}...\n"
                
                # Add rules from Tier 2 MongoDB (PERSISTENT)
                if context.get('profile', {}).get('rules'):
                    summary += f"\n**Active Rules (Tier 2 MongoDB - Persistent):** ({len(context['profile']['rules'])})\n"
                    for rule in context['profile']['rules'][-5:]:  # Last 5 rules
                        summary += f"- [{rule.get('category', 'general')}] {rule.get('rule', '')}\n"
                
                # Add semantic results from Tier 3 ChromaDB (SLOW - only when needed)
                if context.get('long_term'):
                    summary += f"\n**Semantic Search Results (Tier 3 ChromaDB - Slow):**\n"
                    for item in context['long_term'][:3]:  # Top 3 matches
                        summary += f"- (relevance: {item.get('relevance_score', 0):.2f}) {item.get('content', '')[:100]}...\n"
                
                return summary
            else:
                return f"Memory retrieval failed: {result.get('error', 'Unknown error')}"
        except Exception as e:
            logger.error(f"Memory Context Tool error: {e}")
            return f"Memory context error: {str(e)}"

# --- START: Robust Memory Save Tool ---
class LangchainMemorySaveTool(AsyncTool):
    name: str = "save_interaction"
    description: str = (
        "Saves conversation context, user preferences, or important information to the memory system. "
        "Accepts either a simple 'interaction_summary' string or a full 'messages' list. "
        "Use this for: storing project decisions, user preferences, important findings, or context for future reference."
    )
    args_schema: type[BaseModel] = MemorySaveSchema

    def _run(self, interaction_summary: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None, tags: Optional[Any] = None) -> str:
        
        reformatted_messages = []
        if messages:
            logger.info(f"Memory Save Tool called with {len(messages)} messages.")
            reformatted_messages = messages
        elif interaction_summary:
            logger.info(f"Memory Save Tool called with summary: '{interaction_summary}'")
            # Adapt the simple summary from the agent into the structured 'messages' format
            reformatted_messages = [
                {"role": "user", "content": "Summary of preceding interaction."},
                {"role": "assistant", "content": interaction_summary}
            ]
        else:
            # This case is handled by the Pydantic validator, but it's good practice
            # to have an explicit error here.
            return "Error: Tool 'save_interaction' was called without 'interaction_summary' or 'messages'."

        # Normalize the tags input
        tag_dict = {}
        if isinstance(tags, list):
            tag_dict = {f"tag_{i+1}": tag for i, tag in enumerate(tags)}
        elif isinstance(tags, dict):
            tag_dict = tags

        try:
            result = mcp_save_interaction(reformatted_messages, tag_dict)
            
            if result.get('status') == 'success':
                logger.info("Memory Save Tool: Successfully saved interaction")
                return f"Successfully saved interaction to memory. Tags: {json.dumps(tag_dict)}"
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Memory Save Tool error: {error_msg}")
                return f"Failed to save interaction: {error_msg}"
        except Exception as e:
            logger.error(f"Memory Save Tool error: {e}")
            return f"Error saving to memory: {str(e)}"
# --- END: Robust Memory Save Tool ---


class LangchainMemoryRuleTool(AsyncTool):
    name: str = "add_permanent_rule"
    description: str = (
        "Adds a permanent rule or preference to the user's profile in the memory system. "
        "These rules persist across all conversations and guide AI behavior. "
        "Use for: coding preferences, communication style, project standards, or any permanent user preferences."
    )
    args_schema: type[BaseModel] = MemoryRuleSchema

    def _run(self, rule: str, category: str = "preference") -> str:
        logger.info(f"Memory Rule Tool called with rule: '{rule[:50]}...'")
        try:
            result = mcp_add_permanent_rule(rule, category)
            if result.get('status') == 'success':
                logger.info("Memory Rule Tool: Successfully added permanent rule")
                return f"Successfully added permanent rule to your profile: '{rule}'"
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Memory Rule Tool error: {error_msg}")
                return f"Failed to add rule: {error_msg}"
        except Exception as e:
            logger.error(f"Memory Rule Tool error: {e}")
            return f"Error adding rule to memory: {str(e)}"

class LangchainMemoryStatsTool(AsyncTool):
    name: str = "get_memory_stats"
    description: str = (
        "Gets comprehensive statistics about the memory system status, usage, and health. "
        "Shows Redis, MongoDB, and ChromaDB connection status and data counts. "
        "Use for: system diagnostics, understanding memory usage, or troubleshooting memory issues."
    )
    args_schema: type[BaseModel] = MemoryStatsSchema

    def _run(self) -> str:
        logger.info("Memory Stats Tool called")
        try:
            stats = mcp_get_memory_stats()
            if stats.get('status') == 'success':
                stats_data = stats['stats']
                response = "Memory System Statistics:\n"
                response += f"• Redis Status: {stats_data.get('redis_status', 'Unknown')}\n"
                response += f"• MongoDB Status: {stats_data.get('mongodb_status', 'Unknown')}\n"
                response += f"• ChromaDB Status: {stats_data.get('chromadb_status', 'Unknown')}\n"
                response += f"• Working Memory Items: {stats_data.get('redis_keys', 0)}\n"
                response += f"• User Profile Rules: {stats_data.get('mongodb_rules', 0)}\n"
                response += f"• Long-term Archives: {stats_data.get('chromadb_documents', 0)}\n"
                response += f"• Memory Health: {stats_data.get('overall_health', 'Unknown')}"
                logger.info("Memory Stats Tool: Successfully retrieved stats")
                return response
            else:
                error_msg = stats.get('error', 'Unknown error')
                logger.error(f"Memory Stats Tool error: {error_msg}")
                return f"Failed to get memory stats: {error_msg}"
        except Exception as e:
            logger.error(f"Memory Stats Tool error: {e}")
            return f"Error getting memory stats: {str(e)}"

class LangchainMemoryCorrectionTool(AsyncTool):
    name: str = "add_correction"
    description: str = (
        "Stores a correction for the AI's previous response to improve future performance. "
        "Helps the AI learn from mistakes and provide better responses over time. "
        "Use for: correcting AI errors, providing better examples, or teaching preferred approaches."
    )
    args_schema: type[BaseModel] = MemoryCorrectionSchema

    def _run(self, correction_text: str) -> str:
        logger.info(f"Memory Correction Tool called with correction: '{correction_text[:50]}...'")
        try:
            # Note: The original mcp_add_correction expects ai_response and user_correction.
            # We'll pass the correction_text as the user_correction.
            result = get_memory_system().add_correction(ai_response="N/A", user_correction=correction_text)
            if result.get('status') == 'success':
                logger.info("Memory Correction Tool: Successfully stored correction")
                return f"Thank you for the correction! I've stored this feedback: '{correction_text}'"
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Memory Correction Tool error: {error_msg}")
                return f"Failed to store correction: {error_msg}"
        except Exception as e:
            logger.error(f"Memory Correction Tool error: {e}")
            return f"Error storing correction: {str(e)}"
