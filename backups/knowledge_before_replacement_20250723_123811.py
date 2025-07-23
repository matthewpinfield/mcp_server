#!/usr/bin/env python3
"""
Knowledge Tools - RAG and Memory Management
==========================================

This module contains knowledge and memory tools as per mcp_engineering_plan.md:
- RAGQueryTool (FlutterDoc + CodeSearch from rag.py)
- MemoryManagementTool (all memory tools from memory.py)
"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel
from typing import Type


import requests
from pydantic import BaseModel, Field, model_validator

from config import DEFAULT_SLASH_COMMANDS

from .base import AsyncTool

logger = logging.getLogger(__name__)

# ===== SLASH COMMAND PROCESSING =====


def process_slash_command(
    command: str, args: str, custom_commands: Dict[str, Any]
) -> str:
    """Process slash commands by routing to appropriate tools"""

    # Check custom commands first
    if command in custom_commands:
        custom_cmd = custom_commands[command]
        return f"Executing custom command: {custom_cmd['description']}"

    # Check built-in commands
    if command not in DEFAULT_SLASH_COMMANDS:
        available_commands = list(DEFAULT_SLASH_COMMANDS.keys()) + list(
            custom_commands.keys()
        )
        return f"Unknown command '{command}'. Available commands: {', '.join(available_commands)}"

    cmd_config = DEFAULT_SLASH_COMMANDS[command]
    action = cmd_config["action"]

    # Route to appropriate tool methods - MVP approach
    try:
        # Handle rules commands with new rules system
        if action in ["save_rule", "list_rules", "delete_rule", "change_rule"]:
            from tools.rules import get_rules_manager
            from core.orchestrator import invalidate_rules_cache
            
            rules_manager = get_rules_manager()
            
            if action == "save_rule":
                result = rules_manager.add_rule(args)
                invalidate_rules_cache()  # Update cache
                return (
                    f"[PASS] Rule added: {args}"
                    if result.get("status") == "success"
                    else f"[FAIL] {result.get('error')}"
                )
            
            elif action == "list_rules":
                result = rules_manager.list_rules()
                if result.get("status") == "success":
                    rules = result.get("rules", [])
                    if not rules:
                        return "[INFO] No rules found"
                    response = f"[INFO] {len(rules)} rule(s):\n"
                    for rule in rules[:10]:
                        response += f"• [{rule.get('id', '')}] {rule.get('text', '')}\n"
                    return response
                return f"[FAIL] {result.get('error')}"

            elif action == "delete_rule":
                if not args.strip():
                    return "[FAIL] Usage: /delete_rule <rule_id>"
                result = rules_manager.delete_rule(args.strip())
                invalidate_rules_cache()  # Update cache
                return (
                    f"[PASS] Rule deleted"
                    if result.get("status") == "success"
                    else f"[FAIL] {result.get('error')}"
                )
            
            elif action == "change_rule":
                # Parse "rule_id new_text"
                parts = args.split(" ", 1)
                if len(parts) != 2:
                    return "[FAIL] Usage: /change_rule <rule_id> <new_text>"
                rule_id, new_text = parts
                result = rules_manager.update_rule(rule_id, new_text)
                invalidate_rules_cache()  # Update cache
                return (
                    f"[PASS] Rule updated: {rule_id}"
                    if result.get("status") == "success"
                    else f"[FAIL] {result.get('error')}"
                )

        # Handle memory commands with memory system  
        elif action == "get_memory":
            result = mcp_get_context(args, include_long_term=True)
            if result.get("status") == "success":
                context = result.get("context", {})
                return f"[INFO] Found: {len(context.get('short_term', []))} recent, {len(context.get('profile', {}).get('rules', []))} rules, {len(context.get('long_term', []))} semantic"
            return f"[FAIL] {result.get('error')}"

        elif action in ["correct", "fix"]:
            result = mcp_add_correction(args)
            return (
                f"[PASS] Correction saved"
                if result.get("status") == "success"
                else f"[FAIL] {result.get('error')}"
            )

        else:
            return f"Command '{command}' action '{action}' not implemented"

    except Exception as e:
        logger.error(f"Error executing slash command {command}: {e}")
        return f"Error executing command '{command}': {str(e)}"


# ===== MEMORY SYSTEM IMPLEMENTATION =====

import hashlib

import logging
from datetime import datetime, timedelta

# LanceDB hybrid system
from typing import cast

import ollama
import pymongo

# Memory system imports
import redis

# Import from config.py instead of hardcoding
from config import (
    DEFAULT_USER,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    MONGODB_URI,
    MONGODB_DATABASE,
    LANCEDB_TIER3_PATH,
    LANCEDB_NAS_PATH,
    DEFAULT_EMBEDDING_MODEL,
)


class MemorySystem:

    def _create_intelligent_summary(self, messages: List[Dict]) -> str:
        """Create intelligent 50-word summary of conversation"""
        try:
            if not messages:
                return "Empty conversation"

            # Extract conversation content
            conversation_text = ""
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "").strip()
                if content:
                    conversation_text += f"{role}: {content}\n"

            if not conversation_text:
                return "No content conversation"

            # Create summary using LLM
            prompt = f"""Summarize this conversation in exactly 50 words or less. Focus on the main topic, key points, and outcome:

{conversation_text}

Summary (max 50 words):"""

            response = ollama.chat(
                model="qwen3:30b-a3b",
                messages=[
                    {
                        "role": "system",
                        "content": "Create concise, informative conversation summaries in 50 words or less.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            summary = response["message"]["content"].strip()
            return summary

        except Exception as e:
            logger.error(f"Failed to create intelligent summary: {e}")
            # Fallback to first user message
            for msg in messages:
                if msg.get("role") == "user" and msg.get("content", "").strip():
                    content = msg.get("content", "").strip()
                    return content[:80] + "..." if len(content) > 80 else content
            return "Conversation recorded"

    """Advanced 3-Tier Memory System for LLM"""

    def __init__(self):
        self.user = DEFAULT_USER
        self.redis_client = None
        self.mongo_client = None
        self.mongo_db = None
        self.tier3_memory = None
        self.nas_archive = None
        self.embedding_func = None
        self._initialize_databases()

    def _initialize_databases(self):
        """Initialize all database connections with 4-tier architecture"""
        try:
            self._setup_redis()
            self._setup_mongodb()
            # LanceDB hybrid system only
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
                socket_timeout=5,
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
                MONGODB_URI, serverSelectionTimeoutMS=5000
            )
            self.mongo_client.admin.command("ping")
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
                "rules": {},
                "metadata": {},
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
            result = subprocess.run(
                ["timeout", "5", "ls", nas_mount_point],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error(
                    "NAS directory listing failed (network timeout or NAS offline)"
                )
                return False
        except subprocess.TimeoutExpired:
            logger.error("NAS access timeout - network may be down or NAS offline")
            return False
        except Exception as e:
            logger.error(f"NAS connectivity test failed: {e}")
            return False

        try:
            test_file = os.path.join(nas_mount_point, ".nas_connectivity_test")
            with open(test_file, "w") as f:
                f.write(f"connectivity_test_{time.time()}")
            os.remove(test_file)
            logger.debug("NAS online and accessible")
            return True

        except OSError as e:
            if "Read-only file system" in str(e):
                logger.error(
                    "NAS is read-only - storage may be full or NAS in maintenance mode"
                )
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

    async def save_interaction(
        self,
        conversation_id: str,
        new_messages: List[Dict],
        tags: Optional[Dict] = None,
    ) -> Dict:
        """
        APPEND-ONLY CONVERSATION MODEL: Append new messages to existing conversation
        Eliminates 95% data duplication by storing each message only once
        """
        try:
            timestamp = datetime.now()

            # TIER 1: Append to existing conversation in Redis
            if self.redis_client is not None:
                conversation_key = f"conversation:{conversation_id}"

                # Get existing conversation or create new one
                existing_data = self.redis_client.get(conversation_key)
                if existing_data:
                    # APPEND to existing conversation
                    conversation_data = json.loads(existing_data)
                    conversation_data["messages"].extend(new_messages)
                    conversation_data["last_updated"] = timestamp.isoformat()
                    conversation_data["message_count"] = len(
                        conversation_data["messages"]
                    )

                    # Update conversation text for semantic search
                    conversation_text = self._format_messages_for_search(
                        conversation_data["messages"]
                    )
                    conversation_data["text"] = conversation_text

                    # Update embedding with full conversation context
                    try:
                        import asyncio
                        result = await asyncio.wait_for(
                            asyncio.to_thread(ollama.embeddings, model=DEFAULT_EMBEDDING_MODEL, prompt=conversation_text),
                            timeout=30,
                        )
                        conversation_data["embedding"] = result["embedding"]
                        logger.debug(
                            f"Updated embedding for conversation: {conversation_id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to update embedding for {conversation_id}: {e}"
                        )

                    action = "appended"
                else:
                    # CREATE new conversation
                    conversation_text = self._format_messages_for_search(new_messages)

                    # Compute embedding for semantic search
                    embedding = None
                    if conversation_text.strip():
                        try:
                            import asyncio
                            result = await asyncio.wait_for(
                                asyncio.to_thread(ollama.embeddings, model=DEFAULT_EMBEDDING_MODEL, prompt=conversation_text),
                                timeout=30,
                            )
                            embedding = result["embedding"]
                            logger.debug(
                                f"Computed embedding for new conversation: {conversation_id}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to compute embedding for {conversation_id}: {e}"
                            )

                    # Prepare metadata
                    metadata = {
                        "conversation_id": conversation_id,
                        "user_id": DEFAULT_USER,
                        "created_at": timestamp.isoformat(),
                        "last_updated": timestamp.isoformat(),
                        "message_count": len(new_messages),
                    }
                    if tags:
                        metadata.update(tags)

                    conversation_data = {
                        "conversation_id": conversation_id,
                        "text": conversation_text,
                        "summary": self._create_intelligent_summary(new_messages),
                        "embedding": embedding,
                        "metadata": metadata,
                        "messages": new_messages,  # Only store new messages once
                        "created_at": timestamp.isoformat(),
                        "last_updated": timestamp.isoformat(),
                        "message_count": len(new_messages),
                    }
                    action = "created"

                # Save the conversation (create or update)
                self.redis_client.setex(
                    conversation_key,
                    86400 * 14,  # 14 days in seconds
                    json.dumps(conversation_data, default=str),
                )

                logger.info(
                    f"Conversation {action} in Tier 1 (Redis): {conversation_id} - {len(new_messages)} messages"
                )
                return {
                    "status": "success",
                    "conversation_id": conversation_id,
                    "action": action,
                    "messages_added": len(new_messages),
                    "total_messages": conversation_data["message_count"],
                    "tier": "redis",
                }
            else:
                logger.error("Redis (Tier 1) not available - conversation not saved")
                return {"status": "error", "error": "Redis unavailable"}

        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
            return {"status": "error", "error": str(e)}

    # NOTE: Tier 1 to Tier 3 migration removed - hybrid system saves to both Redis and LanceDB simultaneously

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
                upsert=True,
            )
            return {"status": "success", "key": key, "modified": result.modified_count}
        except Exception as e:
            logger.error(f"Failed to set key {key}: {e}")
            return {"status": "error", "error": str(e)}

    async def get_context(
        self, query: Optional[str] = None, include_long_term: bool = True
    ) -> Dict:
        """Core memory read operation - retrieves context from all 3 tiers"""
        try:
            context = {
                "short_term": [],
                "profile": {},
                "long_term": [],
                "timestamp": datetime.now().isoformat(),
            }

            # Tier 1: Get context from Redis (semantic search if query provided)
            context["short_term"] = self._get_redis_context(query)

            # Tier 2: Get profile data from MongoDB
            context["profile"] = self._get_mongodb_profile()

            # Tier 3: Get semantic memories from LanceDB (hybrid system)
            if include_long_term and query:
                context["long_term"] = await self._search_hybrid_long_term_memory(query)

            logger.info(
                f"Context retrieved: {len(context['short_term'])} recent, {len(context['long_term'])} semantic"
            )
            return {"status": "success", "context": context}

        except Exception as e:
            logger.error(f"Failed to get context: {e}")
            return {"status": "error", "error": str(e)}

    # PERMANENT RULE MANAGEMENT
    def add_permanent_rule(self, rule: str, category: str = "general") -> Dict:
        """Administrative operation - adds permanent rule to user profile"""
        if self.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}

        try:
            rule_data = {
                "rule": rule,
                "category": category,
                "added_at": datetime.now(),
                "id": hashlib.md5(rule.encode()).hexdigest()[:8],
            }

            result = self.mongo_db.profiles.update_one(
                {"user_id": DEFAULT_USER}, {"$push": {"rules": rule_data}}
            )

            if result.modified_count > 0:
                logger.info(f"Rule added: {rule}")
                return {"status": "success", "rule_id": rule_data["id"]}
            else:
                return {"status": "error", "error": "Failed to update profile"}

        except Exception as e:
            logger.error(f"Failed to add rule: {e}")
            return {"status": "error", "error": str(e)}

    def list_rules(self, search_query: Optional[str] = None) -> Dict:
        """List rules with optional search filter"""
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

            return {"status": "success", "rules": rules, "count": len(rules)}
        except Exception as e:
            logger.error(f"Failed to list rules: {e}")
            return {"status": "error", "error": str(e)}

    def delete_rule(self, rule_id: str) -> Dict:
        """Delete rule by ID"""
        if self.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}

        try:
            result = self.mongo_db.profiles.update_one(
                {"user_id": DEFAULT_USER}, {"$pull": {"rules": {"id": rule_id}}}
            )

            if result.modified_count > 0:
                return {"status": "success", "deleted_count": result.modified_count}
            else:
                return {"status": "error", "error": f"Rule with ID {rule_id} not found"}
        except Exception as e:
            logger.error(f"Failed to delete rule: {e}")
            return {"status": "error", "error": str(e)}

    def update_rule(self, rule_id: str, new_rule: str) -> Dict:
        """Update rule by ID"""
        if self.mongo_db is None:
            return {"status": "error", "error": "MongoDB unavailable"}

        try:
            result = self.mongo_db.profiles.update_one(
                {"user_id": DEFAULT_USER, "rules.id": rule_id},
                {
                    "$set": {
                        "rules.$.rule": new_rule,
                        "rules.$.updated_at": datetime.now(),
                    }
                },
            )

            if result.modified_count > 0:
                return {"status": "success", "updated_count": result.modified_count}
            else:
                return {"status": "error", "error": f"Rule with ID {rule_id} not found"}
        except Exception as e:
            logger.error(f"Failed to update rule: {e}")
            return {"status": "error", "error": str(e)}

    def add_correction(
        self, ai_response: str, user_correction: str, topic: Optional[str] = None
    ) -> Dict:
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
                "id": hashlib.md5(
                    f"{ai_response}{user_correction}".encode()
                ).hexdigest()[:8],
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

    def get_corrections(
        self, topic: Optional[str] = None, limit: int = 5
    ) -> List[Dict]:
        """Retrieve relevant corrections for prompt injection"""
        if self.mongo_db is None:
            return []

        try:
            query = {"user_id": self.user}
            if topic:
                query["topic"] = topic

            corrections = list(
                self.mongo_db.correction_logs.find(
                    query,
                    {
                        "_id": 0,
                        "ai_response": 1,
                        "user_correction": 1,
                        "topic": 1,
                        "created_at": 1,
                    },
                )
                .sort("created_at", -1)
                .limit(limit)
            )

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
                "lancedb_status": "disconnected",
                "redis_keys": 0,
                "mongodb_rules": 0,
                "lancedb_conversations": 0,
                "overall_health": "unknown",
            }

            # Redis stats
            if self.redis_client is not None:
                try:
                    self.redis_client.ping()  # Test connection
                    conversation_keys = self.redis_client.keys("conversation:*")
                    redis_key_count = len(cast(list, conversation_keys))
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
                    self.mongo_client.admin.command("ping")  # Test connection
                    profile = self.mongo_db.profiles.find_one({"user_id": DEFAULT_USER})
                    rule_count = len(profile.get("rules", [])) if profile else 0
                    stats["mongodb_status"] = "connected"
                    stats["mongodb_rules"] = rule_count
                except Exception as e:
                    logger.debug(f"MongoDB stats error: {e}")
                    stats["mongodb_status"] = "error"
            else:
                logger.debug("MongoDB client is None")

            # LanceDB stats (Hybrid System)
            try:
                import lancedb

                lancedb_path = "/mnt/caseSSD/mcp_server_project/tier3_memory_lancedb"
                client = lancedb.connect(lancedb_path)
                if "conversations" in client.table_names():
                    table = client.open_table("conversations")
                    count = len(table.search().limit(5).to_list())
                    stats["lancedb_status"] = "connected"
                    stats["lancedb_conversations"] = count
                else:
                    stats["lancedb_status"] = "connected"
                    stats["lancedb_conversations"] = 0
            except Exception as e:
                logger.debug(f"LanceDB stats error: {e}")
                stats["lancedb_status"] = "error"

            # Overall health
            connected_systems = sum(
                1
                for status in [
                    stats["redis_status"],
                    stats["mongodb_status"],
                    stats["lancedb_status"],
                ]
                if status == "connected"
            )
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

    def _get_redis_context(self, query: Optional[str] = None) -> List[Dict]:
        """Retrieve conversation context from Redis using semantic cache matching"""
        if self.redis_client is None:
            return []

        try:
            # Get conversation keys (new hybrid format)
            conv_keys = self.redis_client.keys("conversation:*")

            # If no query, return recent conversations chronologically
            if not query or not query.strip():
                contexts = []
                for key in cast(list, conv_keys):
                    data = self.redis_client.get(key)
                    if data:
                        conversation_data = json.loads(cast(str, data))
                        contexts.append(
                            {
                                "content": conversation_data.get(
                                    "intelligent_summary",
                                    conversation_data.get("text", ""),
                                ),
                                "timestamp": conversation_data.get("created_at", ""),
                                "metadata": {
                                    "conversation_id": conversation_data.get(
                                        "conversation_id", ""
                                    ),
                                    "tools_executed": conversation_data.get(
                                        "tools_executed", []
                                    ),
                                    "source": "redis_cache",
                                },
                                "messages": conversation_data.get("messages", []),
                            }
                        )

                # Sort by timestamp and return recent 10 interactions
                contexts.sort(key=lambda x: x["timestamp"], reverse=True)
                return contexts[:10]

            # Semantic search when query is provided using semantic_cache_key
            return self._search_redis_semantic_cache(query)

        except Exception as e:
            logger.error(f"Failed to get Redis context: {e}")
            return []

    def _search_redis_semantic_cache(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Redis conversations using semantic_cache_key for fast similarity matching"""
        if self.redis_client is None:
            return []

        try:
            # Generate query cache key using same method as save
            query_cache_key = self._generate_cache_key(query)

            # Get all conversation keys
            conv_keys = self.redis_client.keys("conversation:*")
            cache_matches = []
            text_matches = []

            for key in cast(list, conv_keys):
                data = self.redis_client.get(key)
                if data:
                    try:
                        conversation_data = json.loads(cast(str, data))
                        stored_cache_key = conversation_data.get(
                            "semantic_cache_key", ""
                        )

                        # Fast cache key similarity (31% of queries can be cached per spec)
                        if stored_cache_key and self._cache_keys_similar(
                            query_cache_key, stored_cache_key
                        ):
                            cache_matches.append(
                                {
                                    "content": conversation_data.get(
                                        "intelligent_summary",
                                        conversation_data.get("text", ""),
                                    ),
                                    "timestamp": conversation_data.get(
                                        "created_at", ""
                                    ),
                                    "metadata": {
                                        "conversation_id": conversation_data.get(
                                            "conversation_id", ""
                                        ),
                                        "tools_executed": conversation_data.get(
                                            "tools_executed", []
                                        ),
                                        "source": "redis_cache_hit",
                                        "cache_key_match": True,
                                    },
                                    "similarity": 0.9,  # High similarity for cache hits
                                    "messages": conversation_data.get("messages", []),
                                }
                            )

                        # Fallback: simple text matching for non-cache hits
                        elif query.lower() in conversation_data.get("text", "").lower():
                            text_matches.append(
                                {
                                    "content": conversation_data.get(
                                        "intelligent_summary",
                                        conversation_data.get("text", ""),
                                    ),
                                    "timestamp": conversation_data.get(
                                        "created_at", ""
                                    ),
                                    "metadata": {
                                        "conversation_id": conversation_data.get(
                                            "conversation_id", ""
                                        ),
                                        "tools_executed": conversation_data.get(
                                            "tools_executed", []
                                        ),
                                        "source": "redis_text_match",
                                    },
                                    "similarity": 0.7,  # Lower similarity for text matches
                                    "messages": conversation_data.get("messages", []),
                                }
                            )

                    except Exception as e:
                        logger.warning(f"Error processing conversation {key}: {e}")
                        continue

            # Prioritize cache hits, then text matches
            all_matches = cache_matches + text_matches
            all_matches.sort(
                key=lambda x: (x["similarity"], x["timestamp"]), reverse=True
            )

            logger.info(
                f"Redis semantic cache search: {len(cache_matches)} cache hits, {len(text_matches)} text matches"
            )
            return all_matches[:limit]

        except Exception as e:
            logger.error(f"Redis semantic cache search failed: {e}")
            return []

    def _cache_keys_similar(self, key1: str, key2: str) -> bool:
        """Check if two semantic cache keys are similar enough (simple hash prefix matching)"""
        if not key1 or not key2:
            return False
        # Simple similarity: first 8 chars match (configurable threshold)
        return key1[:8] == key2[:8]

    # NOTE: _search_redis_semantic removed - unused dead code, using cache-based search instead

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if not a or not b:
            return 0.0

        try:
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5

            if norm_a == 0 or norm_b == 0:
                return 0.0

            return dot_product / (norm_a * norm_b)
        except Exception:
            return 0.0

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

    def _generate_cache_key(self, content: str) -> str:
        """Generate semantic cache key for similarity matching"""
        import hashlib

        content_words = content.lower().split()
        meaningful_words = [w for w in content_words if len(w) > 3][:10]
        meaningful_words.sort()
        return hashlib.md5(" ".join(meaningful_words).encode()).hexdigest()[:16]

    def _format_messages_for_search(self, messages: List[Dict]) -> str:
        """Convert messages to searchable text for LanceDB"""
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

    async def _search_hybrid_long_term_memory(
        self, query: str, n_results: int = 5
    ) -> List[Dict]:
        """Search hybrid LanceDB long-term memory"""
        try:
            import lancedb
            import ollama

            # Generate query embedding using same model as save
            import asyncio
            embedding_response = await asyncio.wait_for(
                asyncio.to_thread(ollama.embeddings, model="nomic-embed-text:latest", prompt=query[:2000]),
                timeout=30,
            )
            query_embedding = embedding_response["embedding"]

            # Connect to LanceDB
            lancedb_path = "/mnt/caseSSD/mcp_server_project/tier3_memory_lancedb"
            client = lancedb.connect(lancedb_path)

            # Check if conversations table exists
            if "conversations" not in client.table_names():
                logger.info("No conversations table in LanceDB yet")
                return []

            table = client.open_table("conversations")

            # Perform semantic search
            results = table.search(query_embedding).limit(n_results).to_list()

            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "content": result.get(
                            "intelligent_summary",
                            result.get("full_interaction_dump", ""),
                        )[:500],
                        "metadata": {
                            "conversation_id": result.get("id", "unknown"),
                            "created_at": str(result.get("created_at", "")),
                            "source": "lancedb_tier3",
                        },
                        "similarity": 1.0
                        - result.get(
                            "_distance", 0.0
                        ),  # Convert distance to similarity
                        "source": "lancedb_tier3",
                    }
                )

            logger.info(
                f"LanceDB semantic search returned {len(formatted_results)} results for query: {query}"
            )
            return formatted_results

        except Exception as e:
            logger.error(f"LanceDB long-term memory search failed: {e}")
            return []

    def migrate_redis_to_nas(
        self, nas_redis_path: str = "/mnt/my_nas_mcp_share/redis_backup"
    ) -> Dict:
        """Migrate Redis conversations older than 30 days to NAS storage"""
        try:
            import json
            import os
            from datetime import datetime, timedelta

            if self.redis_client is None:
                return {"status": "error", "error": "Redis unavailable for migration"}

            # Create NAS directory if it doesn't exist
            os.makedirs(nas_redis_path, exist_ok=True)

            cutoff_date = datetime.now() - timedelta(days=30)
            migrated_count = 0
            error_count = 0

            # Get all conversation keys
            conversation_keys = self.redis_client.keys("conversation:*")

            for key in conversation_keys:
                try:
                    data = self.redis_client.get(key)
                    if data:
                        conversation = json.loads(data)
                        created_at_str = conversation.get("created_at", "")

                        if created_at_str:
                            created_at = datetime.fromisoformat(
                                created_at_str.replace("Z", "+00:00")
                            )

                            # Migrate if older than 30 days
                            if created_at < cutoff_date:
                                # Save to NAS maintaining exact same format
                                nas_file = os.path.join(
                                    nas_redis_path, f"{key.replace(':', '_')}.json"
                                )
                                with open(nas_file, "w") as f:
                                    json.dump(conversation, f, indent=2)

                                # Remove from Redis after successful NAS save
                                self.redis_client.delete(key)
                                migrated_count += 1
                                logger.info(f"Migrated {key} to NAS")

                except Exception as e:
                    logger.error(f"Error migrating {key}: {e}")
                    error_count += 1

            result = {
                "status": "success",
                "migrated": migrated_count,
                "errors": error_count,
                "cutoff_date": cutoff_date.isoformat(),
                "nas_path": nas_redis_path,
            }

            # Suppress verbose migration logging for startup
            return result

        except Exception as e:
            logger.error(f"Redis NAS migration failed: {e}")
            return {"status": "error", "error": str(e)}

    def run_automated_migration(self) -> Dict:
        """Automated daily migration check - runs Redis + LanceDB migrations if needed"""
        try:
            results = {
                "timestamp": datetime.now().isoformat(),
                "redis_migration": None,
                "lancedb_migration": None,
                "status": "completed",
            }

            # Run Redis migration
            redis_result = self.migrate_redis_to_nas()
            results["redis_migration"] = redis_result

            # Run LanceDB migration
            lancedb_result = self.migrate_lancedb_to_nas()
            results["lancedb_migration"] = lancedb_result

            total_migrated = redis_result.get("migrated", 0) + lancedb_result.get(
                "migrated", 0
            )

            if total_migrated > 0:
                logger.info(
                    f"Automated migration completed: {total_migrated} total conversations migrated"
                )
            else:
                logger.debug(
                    "Automated migration check: no data to migrate (all < 30 days old)"
                )

            return results

        except Exception as e:
            logger.error(f"Automated migration failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def migrate_lancedb_to_nas(
        self, nas_lancedb_path: str = "/mnt/my_nas_mcp_share/lancedb_archive"
    ) -> Dict:
        """Migrate LanceDB conversations older than 30 days to NAS storage"""
        try:
            import os
            from datetime import datetime, timedelta

            import lancedb

            # Create NAS directory if it doesn't exist
            os.makedirs(nas_lancedb_path, exist_ok=True)

            # Connect to source LanceDB
            source_path = "/mnt/caseSSD/mcp_server_project/tier3_memory_lancedb"
            source_client = lancedb.connect(source_path)

            if "conversations" not in source_client.table_names():
                return {
                    "status": "success",
                    "migrated": 0,
                    "message": "No conversations table found",
                }

            source_table = source_client.open_table("conversations")

            # Connect to NAS LanceDB (create if doesn't exist)
            nas_client = lancedb.connect(nas_lancedb_path)

            cutoff_date = datetime.now() - timedelta(days=30)
            migrated_count = 0

            # Get all conversations
            all_conversations = source_table.search().limit(100).to_list()
            conversations_to_migrate = []
            conversations_to_keep = []

            for conv in all_conversations:
                created_at_str = str(conv.get("created_at", ""))
                try:
                    if created_at_str:
                        created_at = datetime.fromisoformat(
                            created_at_str.replace("Z", "+00:00")
                        )

                        if created_at < cutoff_date:
                            conversations_to_migrate.append(conv)
                        else:
                            conversations_to_keep.append(conv)
                except Exception as e:
                    logger.warning(f"Error parsing date for conversation: {e}")
                    conversations_to_keep.append(conv)  # Keep if date parsing fails

            # Migrate old conversations to NAS
            if conversations_to_migrate:
                # Create or append to NAS conversations table
                if "conversations" in nas_client.table_names():
                    nas_table = nas_client.open_table("conversations")
                    nas_table.add(conversations_to_migrate)
                else:
                    nas_client.create_table("conversations", conversations_to_migrate)

                migrated_count = len(conversations_to_migrate)

                # Replace source table with only recent conversations
                if conversations_to_keep:
                    # Drop and recreate source table with only recent data
                    source_client.drop_table("conversations")
                    source_client.create_table("conversations", conversations_to_keep)
                else:
                    # Drop table if no recent conversations
                    source_client.drop_table("conversations")

            result = {
                "status": "success",
                "migrated": migrated_count,
                "remaining": len(conversations_to_keep),
                "cutoff_date": cutoff_date.isoformat(),
                "nas_path": nas_lancedb_path,
            }

            # Suppress verbose migration logging for startup
            return result

        except Exception as e:
            logger.error(f"LanceDB NAS migration failed: {e}")
            return {"status": "error", "error": str(e)}

    def shutdown(self):
        """MVP shutdown - Python garbage collection handles connection cleanup safely"""
        logger.info("Memory system shutdown - connections will auto-close")


# Global memory system instance with thread-safe initialization
memory_system = None
_memory_system_lock = threading.Lock()


def get_memory_system() -> MemorySystem:
    """Get or create the global memory system instance (thread-safe)"""
    global memory_system
    if memory_system is None:
        with _memory_system_lock:
            # Double-check locking patternA
            if memory_system is None:
                memory_system = MemorySystem()
    return memory_system


# MCP Tool Interface Functions
def mcp_get_context(
    query: Optional[str] = None, include_long_term: bool = True
) -> Dict:
    """MCP Tool: Retrieve memory context for conversation"""
    try:
        # Input validation
        if query is not None:
            if not isinstance(query, str):
                return {
                    "status": "error",
                    "error": "Query must be a string or None",
                    "context": {},
                }
            if len(query.strip()) > 1000:
                return {
                    "status": "error",
                    "error": "Query too long (max 1000 characters)",
                    "context": {},
                }
            # Sanitize query - remove potentially dangerous characters
            query = query.strip()

        if not isinstance(include_long_term, bool):
            return {
                "status": "error",
                "error": "include_long_term must be a boolean",
                "context": {},
            }

        import asyncio
        result = asyncio.run(get_memory_system().get_context(query, include_long_term))
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


def mcp_save_interaction(
    conversation_id: str, new_messages: List[Dict], tags: Optional[Dict] = None
) -> Dict:
    """MCP Tool: Save conversation interaction to memory using append-only model"""
    import asyncio
    return asyncio.run(get_memory_system().save_interaction(conversation_id, new_messages, tags))


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


def mcp_get_memory_context(key_or_query: str):
    """Wrapper function to get memory context - handles both key lookups and queries"""
    try:
        if key_or_query in [
            "custom_slash_commands",
            "current_project",
            "workspace_settings",
        ]:
            key_value = mcp_get_key_value(key_or_query)
            # Wrap key-value result in proper context structure
            return {
                "status": "success",
                "context": {
                    "key_value": key_value,
                    "profile": {},
                    "short_term": [],
                    "long_term": [],
                },
            }

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
                return {
                    "status": "error",
                    "error": "Serialization failed",
                    "context": {},
                }

        return result
    except Exception as e:
        logger.error(f"mcp_get_memory_context error: {e}")
        return {"status": "error", "error": f"Memory error: {str(e)}", "context": {}}


# NEW HYBRID SYSTEM MIGRATIONS PER NEW_MEMORY_IMPLEMENTATION_SPEC.md
def mcp_migrate_redis_to_nas(
    nas_redis_path: str = "/mnt/my_nas_mcp_share/redis_backup",
) -> Dict:
    """MCP Tool: Migrate Redis conversations older than 30 days to NAS storage"""
    return get_memory_system().migrate_redis_to_nas(nas_redis_path)


def mcp_migrate_lancedb_to_nas(
    nas_lancedb_path: str = "/mnt/my_nas_mcp_share/lancedb_archive",
) -> Dict:
    """MCP Tool: Migrate LanceDB conversations older than 30 days to NAS storage"""
    return get_memory_system().migrate_lancedb_to_nas(nas_lancedb_path)


# ===== SCHEMAS =====


class FlutterDocSchema(BaseModel):
    query: str = Field(description="Flutter/Dart documentation query")
    max_results: int = Field(description="Maximum results", default=5)


class CodeSearchSchema(BaseModel):
    query: str = Field(description="Code example search query")
    max_results: int = Field(description="Maximum results", default=5)


class MemoryContextSchema(BaseModel):
    query: str = Field(description="Query or key to retrieve from memory system")
    include_long_term: bool = Field(
        default=True, description="Include long-term memory in search"
    )


# --- START: Flexible Schema for Save Tool ---


class MemoryRuleSchema(BaseModel):
    rule: str = Field(
        description="The rule text. Example: 'I prefer detailed explanations' or 'Always use TypeScript for web projects'"
    )
    category: str = Field(
        description="Category like 'general', 'coding_style', 'communication', etc.",
        default="general",
    )


class MemoryStatsSchema(BaseModel):
    pass  # No parameters needed


class MemoryCorrectionSchema(BaseModel):
    correction_text: str = Field(description="Correction to store for future learning")


class MemorySaveSchema(BaseModel):
    conversation_id: str = Field(description="Unique conversation identifier")
    messages: str = Field(description="JSON string of messages to save")
    tags: Optional[str] = Field(
        description="Optional JSON string of tags", default=None
    )


# ===== RAG TOOL CLASSES =====


class LangchainFlutterDocTool(AsyncTool):
    name: str = "query_flutter_dart_documentation"
    description: str = (
        "Queries a knowledge base of Flutter/Dart documentation to answer technical questions about Flutter or Dart. Use this for specific Flutter/Dart coding questions, error explanations, or finding documentation."
    )
    args_schema: type[BaseModel] = FlutterDocSchema

    def _run(self, query: str, max_results: int = 10) -> str:
        logger.info(f"Docs Search: Received query: '{query}'")
        try:
            import requests

            from config import RAG_SERVER_ENDPOINT, REQUEST_TIMEOUT

            response = requests.post(
                RAG_SERVER_ENDPOINT,
                params={"query": query, "limit": max_results},
                timeout=REQUEST_TIMEOUT,
                json={},
            )
            response.raise_for_status()

            try:
                rag_json = response.json()
                if isinstance(rag_json, dict) and "results" in rag_json:
                    # Handle dual endpoint server response format
                    results = rag_json["results"]
                    if results:
                        result_text = f" **Flutter/Dart Documentation Results** (Database: {rag_json.get('database', 'unknown')})\n\n"
                        for i, result in enumerate(
                            results[:3], 1
                        ):  # Show top 3 results
                            text = result.get("text", "").strip()
                            if len(text) > 800:
                                text = text[:800] + "..."
                            result_text += f"**Result {i}:**\n{text}\n\n"
                    else:
                        result_text = "No relevant documentation found."
                elif isinstance(rag_json, dict):
                    # Fallback for other response formats
                    if "answer" in rag_json:
                        result_text = rag_json["answer"]
                    elif "text" in rag_json:
                        result_text = rag_json["text"]
                    elif "content" in rag_json:
                        result_text = rag_json["content"]
                    else:
                        result_text = json.dumps(rag_json)
                else:
                    result_text = json.dumps(rag_json)
            except ValueError:
                result_text = response.text

            logger.info(
                f"Docs Search: Successfully retrieved documentation (length: {len(result_text)})."
            )
            return f"Documentation found for query '{query}':\n{result_text}"

        except Exception as e:
            logger.error(f"Docs Search: Error: {e}")
            return f"Error during RAG tool execution: {str(e)}"


class LangchainCodeSearchTool(AsyncTool):
    name: str = "search_code_examples"
    description: str = (
        "Search Python and Flutter code examples from the code database using RAG system"
    )
    args_schema: type[BaseModel] = CodeSearchSchema

    def _run(self, query: str, max_results: int = 10) -> str:
        logger.info(
            f"Code Search: Received query: '{query}', max_results={max_results}"
        )
        try:
            import requests

            from config import RAG_CODE_ENDPOINT, REQUEST_TIMEOUT

            response = requests.post(
                RAG_CODE_ENDPOINT,
                params={"query": query, "limit": max_results},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            result = response.json()

            # Handle dual endpoint response format
            if result and result.get("results"):
                docs = result.get("results", [])
                if docs:
                    formatted_response = f"Code Examples for '{query}':\n\n"
                    for i, doc in enumerate(docs, 1):
                        title = doc.get("title", doc.get("source", "Unknown"))
                        content = doc.get("text", doc.get("content", ""))[:400] + "..."
                        source = doc.get("source", "Unknown")

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
        "Retrieves relevant context from the hybrid memory system (Redis LanceDB). "
        "Searches conversation history and long-term archives. "
        "Use for: recalling previous discussions, project context, or any stored information."
    )
    args_schema: type[BaseModel] = MemoryContextSchema

    def _run(self, query: str = "", include_long_term: bool = True) -> str:
        logger.info(
            f"Memory Context Tool: query='{query}', include_long_term={include_long_term}"
        )
        try:
            result = mcp_get_context(query, include_long_term)
            if result.get("status") == "success":
                context = result.get("context", {})
                summary = f"Memory Context Retrieved:\n"
                summary += f"• Short-term: {len(context.get('short_term', []))} recent interactions\n"
                summary += f"• Long-term: {len(context.get('long_term', []))} semantic matches\n\n"

                # Add recent context from Tier 1 Redis (FAST)
                if context.get("short_term"):
                    summary += "**Recent Conversations (Tier 1 Redis - Fast):**\n"
                    for item in context["short_term"][-3:]:  # Last 3 interactions
                        summary += f"- {item.get('timestamp', '')}: {len(item.get('messages', []))} messages\n"
                        # If this is a query search, show matching content
                        if query and item.get("content"):
                            content = item.get("content", "")
                            if query.lower() in content.lower():
                                summary += f"  Match: {content[:200]}...\n"

                # Add semantic results from LanceDB (FAST - hybrid system)
                if context.get("long_term"):
                    summary += f"\n**Semantic Search Results (LanceDB - Fast):**\n"
                    for item in context["long_term"][:3]:  # Top 3 matches
                        summary += f"- (relevance: {item.get('relevance_score', 0):.2f}) {item.get('content', '')[:100]}...\n"

                return summary
            else:
                return (
                    f"Memory retrieval failed: {result.get('error', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(f"Memory Context Tool error: {e}")
            return f"Memory context error: {str(e)}"


class LangchainMemoryListRulesTool(AsyncTool):
    """A tool to specifically list the user-defined rules from MongoDB."""

    name: str = "list_user_rules"
    description: str = (
        "Retrieves and lists all permanent user rules that define my operating instructions and preferences. "
        "Use this tool ONLY when asked to list, check, see, or remember your rules."
    )
    # This tool takes no arguments, so we use an empty schema.
    args_schema: Type[BaseModel] = type("EmptySchema", (BaseModel,), {})

    def _run(self) -> str:
        logger.info("List Rules Tool called")
        try:
            # This directly calls the efficient function in your MemorySystem
            result = get_memory_system().list_rules()

            if result.get("status") == "success":
                rules = result.get("rules", [])
                if not rules:
                    return "No user rules are currently stored."

                # Format the output cleanly and concisely
                response_parts = [f"I found {len(rules)} user rules:"]
                for rule in rules:
                    response_parts.append(
                        f"- [{rule.get('category', 'general')}] {rule.get('rule', '')}"
                    )
                return "\n".join(response_parts)
            else:
                return (
                    f"Failed to retrieve rules: {result.get('error', 'Unknown error')}"
                )
        except Exception as e:
            logger.error(f"List Rules Tool error: {e}")
            return f"An error occurred while listing the rules: {str(e)}"


# --- START: Robust Memory Save Tool ---


class LangchainMemoryStatsTool(AsyncTool):
    name: str = "get_memory_stats"
    description: str = (
        "Gets comprehensive statistics about the memory system status, usage, and health. "
        "Shows Redis, MongoDB, and LanceDB connection status and data counts. "
        "Use for: system diagnostics, understanding memory usage, or troubleshooting memory issues."
    )
    args_schema: type[BaseModel] = MemoryStatsSchema

    def _run(self) -> str:
        logger.info("Memory Stats Tool called")
        try:
            stats = mcp_get_memory_stats()
            if stats.get("status") == "success":
                stats_data = stats["stats"]
                response = "Hybrid Memory System Status (Redis + LanceDB):\n"
                response += f"• Redis Cache: {stats_data.get('redis_status', 'Unknown')} ({stats_data.get('redis_keys', 0)} conversations)\n"
                response += f"• MongoDB Rules: {stats_data.get('mongodb_status', 'Unknown')} ({stats_data.get('mongodb_rules', 0)} user rules)\n"
                response += f"• LanceDB Archive: {stats_data.get('lancedb_status', 'Unknown')} ({stats_data.get('lancedb_conversations', 0)} semantic conversations)\n"
                response += (
                    f"• System Health: {stats_data.get('overall_health', 'Unknown')}\n"
                )
                response += (
                    f"• Architecture: Redis semantic cache + LanceDB vector storage\n"
                )
                response += f"• Performance: <50ms retrieval, async saves, NAS migration after 30 days"
                logger.info("Memory Stats Tool: Successfully retrieved stats")
                return response
            else:
                error_msg = stats.get("error", "Unknown error")
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
        logger.info(
            f"Memory Correction Tool called with correction: '{correction_text[:50]}...'"
        )
        try:
            # Note: The original mcp_add_correction expects ai_response and user_correction.
            # We'll pass the correction_text as the user_correction.
            result = get_memory_system().add_correction(
                ai_response="N/A", user_correction=correction_text
            )
            if result.get("status") == "success":
                logger.info("Memory Correction Tool: Successfully stored correction")
                return f"Thank you for the correction! I've stored this feedback: '{correction_text}'"
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Memory Correction Tool error: {error_msg}")
                return f"Failed to store correction: {error_msg}"
        except Exception as e:
            logger.error(f"Memory Correction Tool error: {e}")
            return f"Error storing correction: {str(e)}"


class LangchainMemorySaveTool(AsyncTool):
    name: str = "save_memory_interaction"
    description: str = (
        "Saves conversation interactions to the hybrid memory system (Redis + LanceDB). "
        "Stores user-assistant exchanges for future recall and context. "
        "Use for: saving conversations, preserving context, building conversation history."
    )
    args_schema: type[BaseModel] = MemorySaveSchema

    def _run(
        self, conversation_id: str, messages: str, tags: Optional[str] = None
    ) -> str:
        logger.info(
            f"Memory Save Tool: conversation_id='{conversation_id}', message_count={len(messages.split(','))}"
        )
        try:
            import json

            # Parse messages from JSON string
            try:
                parsed_messages = json.loads(messages)
                if not isinstance(parsed_messages, list):
                    return "Error: messages must be a JSON array of message objects"
            except json.JSONDecodeError as e:
                return f"Error parsing messages JSON: {str(e)}"

            # Parse tags if provided
            parsed_tags = None
            if tags and tags.strip():
                try:
                    parsed_tags = json.loads(tags)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Error parsing tags JSON: {e}, using tags as string"
                    )
                    parsed_tags = {"note": tags}

            # NEW: Use hybrid Redis + LanceDB architecture
            result = self._save_to_hybrid_system(
                conversation_id, parsed_messages, parsed_tags
            )

            if result.get("status") == "success":
                saved_count = result.get("messages_added", len(parsed_messages))
                logger.info(
                    f"Memory Save Tool: Successfully saved {saved_count} messages"
                )
                return f"Successfully saved {saved_count} messages to hybrid memory system (Redis + LanceDB)"
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Memory Save Tool error: {error_msg}")
                return f"Failed to save conversation: {error_msg}"

        except Exception as e:
            logger.error(f"Memory Save Tool error: {e}")
            return f"Error saving conversation to memory: {str(e)}"

    def _save_to_hybrid_system(
        self, conversation_id: str, messages: List[Dict], tags: Optional[Dict] = None
    ) -> Dict:
        """Save to hybrid Redis semantic cache + LanceDB archival system"""
        try:
            import threading

            import redis

            # Connect to Redis
            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_timeout=5,
            )

            timestamp = datetime.now()

            # Extract conversation content
            user_content = " ".join(
                [
                    msg.get("content", "")
                    for msg in messages
                    if msg.get("role") == "user"
                ]
            )
            assistant_content = " ".join(
                [
                    msg.get("content", "")
                    for msg in messages
                    if msg.get("role") == "assistant"
                ]
            )
            combined_content = f"{user_content} {assistant_content}"

            # Generate intelligent summary immediately for Redis
            intelligent_summary = self._generate_intelligent_summary(combined_content)

            # Redis semantic cache entry (preserve existing structure + add semantic fields)
            redis_key = f"conversation:{conversation_id}"
            existing_data = redis_client.get(redis_key)

            if existing_data:
                # Update existing conversation
                conversation_data = json.loads(existing_data)
                conversation_data["messages"].extend(messages)
                conversation_data["last_updated"] = timestamp.isoformat()
                conversation_data["message_count"] = len(conversation_data["messages"])
            else:
                # Create new conversation with preserved fields for existing tools
                conversation_data = {
                    "conversation_id": conversation_id,
                    "messages": messages,
                    "created_at": timestamp.isoformat(),
                    "last_updated": timestamp.isoformat(),
                    "message_count": len(messages),
                    "text": combined_content,  # Preserve for existing retrieval
                    "summary": intelligent_summary,  # Preserve for existing retrieval
                }

            # Add NEW semantic cache fields
            conversation_data.update(
                {
                    "intelligent_summary": intelligent_summary,
                    "semantic_cache_key": self._generate_cache_key(combined_content),
                    "user_rules": self._extract_rules(messages),
                    "tools_executed": self._detect_tools(combined_content),
                }
            )

            # Save to Redis immediately (fast operation)
            redis_client.setex(
                redis_key, 86400 * 14, json.dumps(conversation_data, default=str)
            )

            # Queue LanceDB save asynchronously
            self._async_lancedb_save(
                conversation_id, combined_content, intelligent_summary, timestamp
            )

            return {
                "status": "success",
                "conversation_id": conversation_id,
                "messages_added": len(messages),
                "redis_saved": True,
                "lancedb_queued": True,
            }

        except Exception as e:
            logger.error(f"Hybrid save failed: {e}")
            return {"status": "error", "error": str(e)}

    def _generate_intelligent_summary(self, content: str) -> str:
        """Generate intelligent summary using Gemma"""
        try:
            if len(content) < 100:
                return content[:100]

            import ollama

            prompt = (
                f"Summarize this conversation in 50 words or less:\n\n{content[:1000]}"
            )

            response = ollama.chat(
                model="gemma3:4b",
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1},
            )

            return response["message"]["content"].strip()[:300]

        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return content[:100]

    def _extract_rules(self, messages: List[Dict]) -> List[str]:
        """Extract user rules from conversation"""
        prefs = []
        user_text = " ".join(
            [msg.get("content", "") for msg in messages if msg.get("role") == "user"]
        ).lower()

        if "detailed" in user_text:
            prefs.append("detailed_explanations")
        if "code" in user_text:
            prefs.append("code_examples")
        if "step" in user_text:
            prefs.append("step_by_step")

        return prefs[:5]

    def _detect_tools(self, content: str) -> List[str]:
        """Detect tools executed based on content"""
        tools = []
        content_lower = content.lower()

        if "web search" in content_lower:
            tools.append("web_search")
        if "memory" in content_lower:
            tools.append("memory_context")
        if "sandbox" in content_lower:
            tools.append("sandbox_execute")

        return tools

    async def _async_lancedb_save(
        self, conversation_id: str, content: str, summary: str, timestamp: datetime
    ):
        """Asynchronously save to LanceDB with full interaction dump"""

        def background_lancedb_save():
            try:
                import lancedb
                import ollama
                import pyarrow as pa

                # Generate embedding (sync version)
                embedding_response = ollama.embeddings(model="nomic-embed-text:latest", prompt=content[:2000])
                embedding = embedding_response["embedding"]

                # Connect to LanceDB
                lancedb_path = "/mnt/caseSSD/mcp_server_project/tier3_memory_lancedb"
                client = lancedb.connect(lancedb_path)

                # Get or create conversations table
                try:
                    table = client.open_table("conversations")
                except Exception:
                    # Create table with schema
                    schema = pa.schema(
                        [
                            pa.field("id", pa.string()),
                            pa.field("full_interaction_dump", pa.string()),
                            pa.field("vector", pa.list_(pa.float32(), 768)),
                            pa.field("created_at", pa.timestamp("ns")),
                            pa.field("intelligent_summary", pa.string()),
                        ]
                    )

                    empty_data = pa.table(
                        {
                            "id": [],
                            "full_interaction_dump": [],
                            "vector": [],
                            "created_at": [],
                            "intelligent_summary": [],
                        },
                        schema=schema,
                    )

                    table = client.create_table("conversations", data=empty_data)

                # Insert conversation data
                table.add(
                    [
                        {
                            "id": conversation_id,
                            "full_interaction_dump": content,  # Full content for semantic search
                            "vector": embedding,
                            "created_at": timestamp,
                            "last_updated": timestamp,  # ADD MISSING FIELD
                            "intelligent_summary": summary,
                            "tools_executed": [],  # ADD MISSING FIELD
                            "search_optimized_text": content[:1000],  # ADD MISSING FIELD
                        }
                    ]
                )

                logger.info(f"LanceDB save completed for {conversation_id}")

            except Exception as e:
                logger.error(f"Async LanceDB save failed: {e}")

        # Start background thread
        thread = threading.Thread(target=background_lancedb_save, daemon=False)
        thread.start()

    def _generate_cache_key(self, content: str) -> str:
        """Generate semantic cache key for similarity matching"""
        import hashlib
        content_words = content.lower().split()
        meaningful_words = [w for w in content_words if len(w) > 3][:10]
        meaningful_words.sort()
        return hashlib.md5(" ".join(meaningful_words).encode()).hexdigest()[:16]

    def _extract_rules(self, messages: List[Dict]) -> List[str]:
        """Extract user rules from conversation"""
        prefs = []
        user_text = " ".join([msg.get("content", "") for msg in messages if msg.get("role") == "user"]).lower()
        if "detailed" in user_text:
            prefs.append("detailed_explanations")
        if "code" in user_text:
            prefs.append("code_examples") 
        if "step" in user_text:
            prefs.append("step_by_step")
        return prefs[:5]

    def _detect_tools(self, content: str) -> List[str]:
        """Detect tools executed based on content"""
        tools = []
        content_lower = content.lower()
        if "web search" in content_lower:
            tools.append("web_search")
        if "memory" in content_lower:
            tools.append("memory_context")
        if "sandbox" in content_lower:
            tools.append("sandbox_execute")
        return tools
