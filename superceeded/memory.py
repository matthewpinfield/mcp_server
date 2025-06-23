#!/usr/bin/env python3
"""
Memory system tools for the Advanced MCP Server
"""

import logging
from typing import Type, List, Dict, Any
from pydantic import BaseModel, Field

from utils.base_tool import AsyncTool

# Memory system implementation - these functions should be implemented locally
def mcp_get_context(query: str, include_long_term: bool = True) -> dict:
    """Get memory context - placeholder implementation"""
    return {"status": "success", "context": {"short_term": [], "profile": {}, "long_term": []}}

def mcp_save_interaction(messages: list, tags: dict) -> dict:
    """Save interaction to memory - placeholder implementation"""
    return {"success": True}

def mcp_add_permanent_rule(rule_text: str) -> dict:
    """Add permanent rule - placeholder implementation"""
    return {"success": True}

def mcp_get_memory_stats() -> dict:
    """Get memory stats - placeholder implementation"""
    return {"success": True, "stats": {"redis_status": "OK", "mongodb_status": "OK", "chromadb_status": "OK", "redis_keys": 0, "mongodb_rules": 0, "chromadb_documents": 0, "overall_health": "OK"}}

def mcp_get_key_value(key: str) -> str:
    """Get key-value pair - placeholder implementation"""
    return f"No data for key: {key}"

def mcp_set_key_value(key: str, value: str) -> dict:
    """Set key-value pair - placeholder implementation"""
    return {"success": True}

def mcp_add_correction(correction_text: str) -> dict:
    """Add correction - placeholder implementation"""
    return {"success": True}

def mcp_get_corrections() -> dict:
    """Get corrections - placeholder implementation"""
    return {"success": True, "corrections": []}

logger = logging.getLogger(__name__)

# Memory wrapper function for backward compatibility
def mcp_get_memory_context(key_or_query: str):
    """Wrapper function to get memory context - handles both key lookups and queries"""
    try:
        # First try as a key lookup for custom commands, project info, etc.
        if key_or_query in ["custom_slash_commands", "current_project", "workspace_settings"]:
            return mcp_get_key_value(key_or_query)
        
        # Otherwise treat as a semantic query
        result = mcp_get_context(key_or_query, include_long_term=True)
        return result
    except Exception as e:
        return f"Memory error: {str(e)}"

# ===== MEMORY TOOL SCHEMAS =====

class MemoryContextSchema(BaseModel):
    query: str = Field(description="Query or key to retrieve from memory system")
    include_long_term: bool = Field(default=True, description="Include long-term memory in search")

class MemorySaveSchema(BaseModel):
    query: str = Field(description="Query or context for the interaction")
    response: str = Field(description="Response or information to save")
    tags: str = Field(default="", description="Comma-separated tags for categorization")

class MemoryRuleSchema(BaseModel):
    rule_text: str = Field(description="Rule or preference to permanently store")

class MemoryStatsSchema(BaseModel):
    pass  # No parameters needed

class MemoryCorrectionSchema(BaseModel):
    correction_text: str = Field(description="Correction to store for future learning")

# ===== MEMORY TOOLS =====

class LangchainMemoryContextTool(AsyncTool):
    name: str = "get_memory_context"
    description: str = (
        "Retrieves relevant context from the 3-tier memory system (Redis + MongoDB + ChromaDB). "
        "Searches conversation history, user preferences, and long-term archives. "
        "Use for: recalling previous discussions, user preferences, project context, or any stored information."
    )
    args_schema: Type[BaseModel] = MemoryContextSchema

    def _run(self, query: str = "", include_long_term: bool = True) -> str:
        logger.info(f"Memory Context Tool called with query: '{query}', include_long_term: {include_long_term}")
        try:
            result = mcp_get_memory_context(query)
            if result:
                logger.info(f"Memory Context Tool: Found context (length: {len(str(result))})")
                return f"Memory context for '{query}':\n{result}"
            else:
                logger.info("Memory Context Tool: No relevant context found")
                return f"No relevant memory context found for query: '{query}'"
        except Exception as e:
            logger.error(f"Memory Context Tool error: {e}")
            return f"Error retrieving memory context: {str(e)}"

class LangchainMemorySaveTool(AsyncTool):
    name: str = "save_interaction"
    description: str = (
        "Saves conversation context, user preferences, or important information to the memory system. "
        "Automatically tags and categorizes content for future retrieval. "
        "Use for: storing project decisions, user preferences, important findings, or context for future reference."
    )
    args_schema: Type[BaseModel] = MemorySaveSchema

    def _run(self, query: str, response: str, tags: str = "") -> str:
        logger.info(f"Memory Save Tool called for query: '{query[:50]}...'")
        try:
            # Convert tags string to list
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()] if tags else []
            
            # Convert to proper format expected by mcp_save_interaction
            messages = [{"role": "user", "content": query}, {"role": "assistant", "content": response}]
            tags_dict = {tag: True for tag in tag_list}
            result = mcp_save_interaction(messages, tags_dict)
            if result.get('success'):
                logger.info("Memory Save Tool: Successfully saved interaction")
                return f"Successfully saved interaction to memory with tags: {tag_list}"
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Memory Save Tool error: {error_msg}")
                return f"Failed to save interaction: {error_msg}"
        except Exception as e:
            logger.error(f"Memory Save Tool error: {e}")
            return f"Error saving to memory: {str(e)}"

class LangchainMemoryRuleTool(AsyncTool):
    name: str = "add_permanent_rule"
    description: str = (
        "Adds a permanent rule or preference to the user's profile in the memory system. "
        "These rules persist across all conversations and guide AI behavior. "
        "Use for: coding preferences, communication style, project standards, or any permanent user preferences."
    )
    args_schema: Type[BaseModel] = MemoryRuleSchema

    def _run(self, rule_text: str) -> str:
        logger.info(f"Memory Rule Tool called with rule: '{rule_text[:50]}...'")
        try:
            result = mcp_add_permanent_rule(rule_text)
            if result.get('success'):
                logger.info("Memory Rule Tool: Successfully added permanent rule")
                return f"Successfully added permanent rule to your profile: '{rule_text}'"
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
    args_schema: Type[BaseModel] = MemoryStatsSchema

    def _run(self) -> str:
        logger.info("Memory Stats Tool called")
        try:
            stats = mcp_get_memory_stats()
            if stats.get('success'):
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
    args_schema: Type[BaseModel] = MemoryCorrectionSchema

    def _run(self, correction_text: str) -> str:
        logger.info(f"Memory Correction Tool called with correction: '{correction_text[:50]}...'")
        try:
            result = mcp_add_correction(correction_text)
            if result.get('success'):
                logger.info("Memory Correction Tool: Successfully stored correction")
                return f"Thank you for the correction! I've stored this feedback: '{correction_text}'"
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Memory Correction Tool error: {error_msg}")
                return f"Failed to store correction: {error_msg}"
        except Exception as e:
            logger.error(f"Memory Correction Tool error: {e}")
            return f"Error storing correction: {str(e)}"