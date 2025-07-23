#!/usr/bin/env python3
"""
Knowledge System - RAG Tools + Slash Commands
==============================================
Contains RAG tools for Flutter docs and code search.
Memory functionality moved to memory.py for the new sliding window system.
"""

import json
import logging
from typing import Dict, Type
from pydantic import BaseModel, Field
from .base import AsyncTool

logger = logging.getLogger(__name__)

# ===== RAG TOOL SCHEMAS =====

class FlutterDocSchema(BaseModel):
    query: str = Field(description="Query to search Flutter/Dart documentation")
    max_results: int = Field(default=10, description="Maximum number of results to return")

class CodeSearchSchema(BaseModel):
    query: str = Field(description="Query to search code examples")
    max_results: int = Field(default=10, description="Maximum number of results to return")

# ===== RAG TOOLS =====

class LangchainFlutterDocTool(AsyncTool):
    name: str = "query_flutter_dart_documentation"
    description: str = (
        "Queries a knowledge base of Flutter/Dart documentation to answer technical questions about Flutter or Dart. Use this for specific Flutter/Dart coding questions, error explanations, or finding documentation."
    )
    args_schema: Type[BaseModel] = FlutterDocSchema

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
                        for i, result in enumerate(results[:3], 1):  # Show top 3 results
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

            logger.info(f"Docs Search: Successfully retrieved documentation (length: {len(result_text)}).")
            return f"Documentation found for query '{query}':\n{result_text}"

        except Exception as e:
            logger.error(f"Docs Search: Error: {e}")
            return f"Error during RAG tool execution: {str(e)}"

class LangchainCodeSearchTool(AsyncTool):
    name: str = "search_code_examples"
    description: str = (
        "Search Python and Flutter code examples from the code database using RAG system"
    )
    args_schema: Type[BaseModel] = CodeSearchSchema

    def _run(self, query: str, max_results: int = 10) -> str:
        logger.info(f"Code Search: Received query: '{query}', max_results={max_results}")
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

def process_slash_command(command: str, args: str, custom_commands: Dict) -> str:
    """
    Process slash commands - now delegated to appropriate systems
    
    Memory commands → tools/memory.py
    Rules commands → tools/rules.py  
    System commands → handled here
    """
    
    if command in ["/remember", "/recall", "/memory", "/memories"]:
        return "Memory commands have been moved to the new memory system. Use the memory tools instead."
    
    if command in ["/rule", "/list_rules", "/delete_rule", "/change_rule"]:
        return "Rules commands have been moved to the rules system. Use the rules tools instead."
    
    if command == "/commands":
        return """Available slash commands:
        
**Memory System:**
- Use memory_search tool for retrieving memories
- Use save_memory tool for saving memories  
- Use memory_stats tool for system statistics

**Rules System:**
- Use add_user_rule tool for adding rules
- Use list_user_rules tool for listing rules
- Use update_user_rule tool for updating rules  
- Use delete_user_rule tool for deleting rules

**System:**
- /commands - This help message
- /help - Get help for specific commands
"""
    
    if command == "/help":
        if args:
            return f"Help for {args}: Please use the corresponding tool instead of slash commands."
        else:
            return "Use /commands to see available commands, or specify a command for help."
    
    # Handle unknown commands
    return f"Unknown command '{command}'. Use /commands to see available commands."

# Legacy compatibility functions - minimal implementations
def mcp_save_interaction(conversation_id: str, messages: list) -> Dict:
    """Legacy compatibility - redirects to new memory system"""
    logger.warning("mcp_save_interaction is deprecated. Use tools.memory.get_memory_system().save_memory() instead.")
    return {"status": "deprecated", "message": "Use new memory system"}

def mcp_get_memory_stats() -> Dict:
    """Legacy compatibility - redirects to new memory system"""
    logger.warning("mcp_get_memory_stats is deprecated. Use tools.memory.get_memory_system() instead.")
    return {"status": "deprecated", "message": "Use new memory system"}

def get_memory_system():
    """Legacy compatibility - redirects to new memory system"""
    logger.warning("get_memory_system moved to tools.memory")
    from .memory import get_memory_system as new_get_memory_system
    return new_get_memory_system()