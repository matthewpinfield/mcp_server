#!/usr/bin/env python3
"""
Advanced MCP Server - Orchestrated Toolkit with Memory Integration
================================================================

This is the advanced MCP server that implements the "Orchestrated Toolkit" model
with the 3-tier memory system integration. It includes:

- Memory System: 4 MCP tools for memory operations
- RAG System: Existing Flutter/Dart documentation tool  
- Layer 1 Manual Tagging: Real-time context-aware tagging
- Orchestrator Logic: Intelligent routing and memory management

Based on gemini_mcp_server.py but enhanced with memory capabilities.
"""

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx 
from httpx_sse import aconnect_sse 
import logging
import json
import asyncio
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub
from langchain_core.tools import BaseTool as LangchainBaseTool, ArgsSchema
from pydantic import BaseModel, Field 

from typing import List, Dict, Any, Union, Optional, AsyncGenerator, Type 
from contextlib import asynccontextmanager

# Import our memory system
from mcp_memory import (
    get_memory_system, 
    mcp_get_context, 
    mcp_save_interaction, 
    mcp_add_permanent_rule, 
    mcp_get_memory_stats,
    mcp_get_key_value,
    mcp_set_key_value,
    mcp_add_correction,
    mcp_get_corrections
)

# Import our sandbox system
from mcp_sandbox import execute_code, get_sandbox_stats, debug_code, test_code

# Memory wrapper function for backward compatibility
def mcp_get_memory_context(key_or_query: str) -> Any:
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

# Import for web search and content scraping
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

# Import for Git operations
import subprocess
import os
from pathlib import Path

# Import for GitHub API integration
import requests
from urllib.parse import quote

# --- Configuration (Environment Variables) ---
RAG_SERVER_ENDPOINT = os.getenv("RAG_SERVER_ENDPOINT", "http://localhost:8008/search/docs")
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434") 
OLLAMA_OPENAI_BASE = os.getenv("OLLAMA_OPENAI_BASE", "http://localhost:11434/v1") 
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen3:8b") 

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "3")) 
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60")) 
LANGCHAIN_AGENT_TIMEOUT = int(os.getenv("LANGCHAIN_AGENT_TIMEOUT", "180")) 
DIRECT_OLLAMA_TIMEOUT = int(os.getenv("DIRECT_OLLAMA_TIMEOUT", "90"))

DEFAULT_RAG_KEYWORDS = "flutter,dart,widget,state management,navigation,routing,buildrunner,firebase,api,documentation,code example,debug,error,fix,how to,what is,explain"
RAG_KEYWORDS_STR = os.getenv("MCP_RAG_KEYWORDS", DEFAULT_RAG_KEYWORDS)
RAG_KEYWORDS = [keyword.strip().lower() for keyword in RAG_KEYWORDS_STR.split(',') if keyword.strip()]

# Memory-specific configuration
MEMORY_KEYWORDS = ["remember", "recall", "forget", "save this", "memory", "context", "history", "previous", "earlier", "before"]
PROGRAMMING_LANGUAGES = ["python", "dart", "flutter", "javascript", "typescript", "java", "c++", "c#", "rust", "go", "php", "ruby"]
PROGRAMMING_DOMAINS = ["api", "backend", "frontend", "mobile", "web", "database", "devops", "machine learning", "ai"]

# Web search configuration
WEB_SEARCH_KEYWORDS = ["search", "look up", "find information", "what's new", "latest", "recent", "news", "current", "today", "2024", "2025", "google", "web search", "online"]
WEB_SEARCH_MAX_RESULTS = 5

# Git/GitHub configuration
GIT_KEYWORDS = ["git", "commit", "push", "pull", "branch", "merge", "checkout", "status", "diff", "log", "clone", "repository", "repo"]
GITHUB_KEYWORDS = ["github", "issue", "pull request", "pr", "release", "repository search", "repo search"]
DEV_WORKFLOW_KEYWORDS = ["build", "test", "lint", "format", "deploy", "ci", "cd", "pipeline", "package", "dependency"]

# Repository analysis configuration
REPO_ANALYSIS_KEYWORDS = ["explore", "analyze", "structure", "dependencies", "metrics", "code analysis", "project analysis", "file tree", "repository structure"]

# Development helpers configuration  
PACKAGE_SEARCH_KEYWORDS = ["package", "library", "npm", "pip", "pub", "cargo", "maven", "search packages", "find library"]
BUILD_COMMAND_KEYWORDS = ["build", "test", "lint", "format", "deploy", "ci", "cd", "pipeline", "run command", "execute"]

# Auto-linter configuration
AUTO_LINTER_KEYWORDS = ["lint", "analyze code", "flutter analyze", "dart fix", "eslint", "prettier", "auto fix", "format code", "code quality", "style check"]

# Sandbox configuration
SANDBOX_KEYWORDS = ["run code", "execute", "test code", "debug", "verify", "check output", "sandbox", "python", "calculate", "what does this code do", "run this", "execute this"]
CALCULATION_KEYWORDS = ["calculate", "compute", "math", "mathematics", "solve", "equation", "formula", "sum", "average", "statistics"]

# Slash commands configuration
DEFAULT_SLASH_COMMANDS = {
    # Memory Management
    "/rule": {
        "description": "Add a new rule or preference to memory",
        "usage": "/rule <rule_text>",
        "example": "/rule I prefer detailed code explanations",
        "category": "memory",
        "action": "save_rule"
    },
    "/remember": {
        "description": "Save specific information to memory",
        "usage": "/remember <information>",
        "example": "/remember This project uses Redux for state management",
        "category": "memory", 
        "action": "save_memory"
    },
    "/recall": {
        "description": "Retrieve information from memory",
        "usage": "/recall <query>",
        "example": "/recall state management preferences",
        "category": "memory",
        "action": "get_memory"
    },
    "/forget": {
        "description": "Remove information from memory",
        "usage": "/forget <query>",
        "example": "/forget old project preferences",
        "category": "memory",
        "action": "delete_memory"
    },
    "/stats": {
        "description": "Show memory and system statistics",
        "usage": "/stats",
        "example": "/stats",
        "category": "memory",
        "action": "get_stats"
    },
    "/correct": {
        "description": "Correct the AI's last response for future learning",
        "usage": "/correct <correction_text>",
        "example": "/correct Actually, use async/await instead of .then()",
        "category": "memory",
        "action": "correct"
    },
    "/fix": {
        "description": "Fix the AI's last response (alias for /correct)",
        "usage": "/fix <correction_text>", 
        "example": "/fix The correct syntax is setState(() => ...)",
        "category": "memory",
        "action": "fix"
    },
    
    # Development Workflow
    "/build": {
        "description": "Quick build command detection and execution",
        "usage": "/build [command]",
        "example": "/build test",
        "category": "development",
        "action": "build_command"
    },
    "/package": {
        "description": "Quick package search",
        "usage": "/package <ecosystem> <query>",
        "example": "/package npm react-router",
        "category": "development", 
        "action": "package_search"
    },
    "/analyze": {
        "description": "Quick repository analysis",
        "usage": "/analyze [type]",
        "example": "/analyze structure",
        "category": "development",
        "action": "repo_analysis"
    },
    
    # Git Operations
    "/status": {
        "description": "Quick git status check",
        "usage": "/status",
        "example": "/status",
        "category": "git",
        "action": "git_status"
    },
    "/commit": {
        "description": "Quick git commit",
        "usage": "/commit <message>",
        "example": "/commit Add new feature",
        "category": "git",
        "action": "git_commit"
    },
    "/branch": {
        "description": "Git branch operations",
        "usage": "/branch [action] [name]",
        "example": "/branch create feature-auth",
        "category": "git", 
        "action": "git_branch"
    },
    
    # System & Help
    "/commands": {
        "description": "List all available slash commands",
        "usage": "/commands [category]",
        "example": "/commands memory",
        "category": "system",
        "action": "list_commands"
    },
    "/help": {
        "description": "Get help for a specific command",
        "usage": "/help <command>",
        "example": "/help /rule",
        "category": "system",
        "action": "get_help"
    },
    "/add-command": {
        "description": "Add a new custom slash command",
        "usage": "/add-command <name> <description> <action>",
        "example": "/add-command /deploy 'Deploy to production' deploy_prod",
        "category": "system",
        "action": "add_command"
    },
    "/remove-command": {
        "description": "Remove a custom slash command",
        "usage": "/remove-command <name>",
        "example": "/remove-command /deploy",
        "category": "system",
        "action": "remove_command"
    },
    
    # Project Management
    "/context": {
        "description": "Get current session and project context",
        "usage": "/context",
        "example": "/context",
        "category": "project",
        "action": "get_context"
    },
    "/project": {
        "description": "Set or get current project information",
        "usage": "/project [name] [description]",
        "example": "/project MyApp 'Flutter e-commerce app'",
        "category": "project",
        "action": "project_info"
    },
    "/workspace": {
        "description": "Manage workspace settings and preferences",
        "usage": "/workspace [setting] [value]",
        "example": "/workspace theme dark",
        "category": "project",
        "action": "workspace_setting"
    }
}

# Google Custom Search API configuration
GOOGLE_API_KEY = "***REMOVED-GOOGLE-API-KEY***"
GOOGLE_SEARCH_ENGINE_ID = "948e280aa8f4544c5"  # From your CSE script

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)  # Optional GitHub token for higher rate limits
GITHUB_SEARCH_MAX_RESULTS = 10

# Domain prioritization for reputable sources - REFINED FOR HIGHEST QUALITY
PRIORITY_DOMAINS = {
    # Tier 1: Official Documentation & Style Guides (The Source of Truth)
    "tier_1_official": [
        "docs.flutter.dev", "flutter.dev", "dart.dev", "api.flutter.dev", "api.dart.dev",
        "docs.python.org", "python.org", "peps.python.org",
        "developer.mozilla.org", "nodejs.org", "web.dev",
        "react.dev", "reactjs.org", "vuejs.org", "angular.dev", "svelte.dev",
        "docs.microsoft.com", "developer.apple.com", "developers.google.com",
        "aws.amazon.com", "cloud.google.com", "azure.microsoft.com",
        "kubernetes.io", "docker.com", "golang.org", "rust-lang.org",
        "typescriptlang.org", "postgresql.org", "mongodb.com/docs"
    ],
    # Tier 2: Curated Educational Platforms & Expert Blogs (High-Quality Learning)
    "tier_2_educational": [
        "freecodecamp.org", "realpython.com", "digitalocean.com",
        "web.dev", "smashingmagazine.com", "martinfowler.com",
        "css-tricks.com", "a11yproject.com", "webhint.io"
    ],
    # Tier 3: Reputable Q&A and Official Repositories (High-Quality Community Content)
    "tier_3_community": [
        "stackoverflow.com", "github.com"  # Will add quality filters
    ],
    # Tier 4: General Tech Blogs (Variable Quality - Use with Caution)
    "tier_4_blogs": [
        "medium.com", "dev.to", "hashnode.com", "codecademy.com"
    ],
    # Tier 5: News & Updates (For Current Events Only)
    "tier_5_news": [
        "techcrunch.com", "arstechnica.com", "theverge.com",
        "9to5google.com", "androidcentral.com", "engadget.com"
    ]
}

DEBUG_VERBOSE = os.getenv("DEBUG_VERBOSE", "False").lower() == "true"

LOG_LEVEL = logging.DEBUG if DEBUG_VERBOSE else logging.INFO
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if DEBUG_VERBOSE: logger.info("DEBUG_VERBOSE mode is ON.")
logger.info(f"Default Model: {DEFAULT_MODEL}")
logger.info(f"RAG Keywords for Langchain Agent: {RAG_KEYWORDS}")
logger.info("🧠 Advanced MCP Server with Memory System starting...")

executor: Optional[ThreadPoolExecutor] = None
shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global executor
    logger.info("Advanced MCP Server with Memory starting up...")
    app.state.loop = asyncio.get_running_loop() 
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="LangchainTool")
    
    # Initialize memory system
    try:
        memory_system = get_memory_system()
        logger.info("🧠 Memory system initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize memory system: {e}")
        
    logger.info("Advanced MCP Server started successfully.")
    yield
    logger.info("Advanced MCP Server shutting down...")
    shutdown_event.set() 
    if executor:
        logger.info("Shutting down ThreadPoolExecutor for Langchain tools...")
        executor.shutdown(wait=False)
        start_time = time.time()
        active_threads_count = len(executor._threads) if hasattr(executor, '_threads') and executor._threads else 0
        grace_period = 15 
        while active_threads_count > 0 and (time.time() - start_time) < grace_period:
            await asyncio.sleep(0.5)
            if hasattr(executor, '_threads') and executor._threads:
                active_threads_count = sum(1 for t in executor._threads if t.is_alive())
            else: active_threads_count = 0
        if active_threads_count > 0: logger.warning(f"{active_threads_count} agent threads still active.")
        else: logger.info("All agent threads appear to have completed.")
    logger.info("Advanced MCP Server shutdown process complete.")

app = FastAPI(title="Advanced MCP Server with Memory", lifespan=lifespan)

def os_signal_handler(signum, frame):
    logger.info(f"Received OS signal {signum}, setting shutdown_event...")
    shutdown_event.set()

signal.signal(signal.SIGINT, os_signal_handler)
signal.signal(signal.SIGTERM, os_signal_handler)

# ===== MEMORY TOOLS =====

class MemoryContextSchema(BaseModel):
    query: str = Field(description="Semantic search query for retrieving relevant context from memory", default="")
    include_long_term: bool = Field(description="Whether to include long-term semantic search results", default=True)

class MemorySaveSchema(BaseModel):
    messages: List[Dict[str, str]] = Field(description="List of chat message objects, each with 'role' and 'content' keys. Example: [{'role': 'user', 'content': 'Hello'}, {'role': 'assistant', 'content': 'Hi there!'}]")
    tags: Optional[Dict[str, str]] = Field(description="Optional tags for categorization like {'domain': 'programming', 'language': 'python'}", default=None)

class MemoryRuleSchema(BaseModel):
    rule: str = Field(description="The rule or preference text. Example: 'I prefer detailed explanations' or 'Always use TypeScript for web projects'")
    category: str = Field(description="Category like 'preference', 'coding_style', 'communication', etc.", default="preference")

class WebSearchSchema(BaseModel):
    query: str = Field(description="Search query for web search using Google/Bing. Be specific and include relevant keywords.")
    max_results: int = Field(description="Maximum number of search results to return", default=5)

class SandboxExecuteSchema(BaseModel):
    code: str = Field(description="Python code to execute in the secure sandbox environment. Must be valid Python syntax.")

class SandboxDebugSchema(BaseModel):
    code: str = Field(description="Python code to debug in the sandbox with detailed execution analysis.")
    expected_output: Optional[str] = Field(description="Expected output for comparison", default=None)

class LangchainMemoryContextTool(LangchainBaseTool):
    name: str = "get_memory_context"
    description: str = "Retrieves conversation context from the 3-tier memory system (Redis short-term, MongoDB profile, ChromaDB long-term). Use this to recall previous conversations, user preferences, and relevant semantic memories."
    args_schema: Type[BaseModel] = MemoryContextSchema

    def _run(self, query: str = "", include_long_term: bool = True) -> str:
        logger.info(f"🧠 Memory Context Tool: query='{query}', include_long_term={include_long_term}")
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
            logger.error(f"❌ Memory Context Tool error: {e}")
            return f"Memory context error: {str(e)}"

    async def _arun(self, query: str = "", include_long_term: bool = True) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, query, include_long_term)

class LangchainMemorySaveTool(LangchainBaseTool):
    name: str = "save_interaction_to_memory"
    description: str = "Saves conversation messages to memory. ONLY use this to store actual chat messages for recall. For user preferences or rules, use add_permanent_rule instead. Input requires 'messages' as a list of message objects like [{'role': 'user', 'content': 'text'}]."
    args_schema: Type[BaseModel] = MemorySaveSchema

    def _run(self, messages: List[Dict[str, str]], tags: Optional[Dict[str, str]] = None) -> str:
        logger.info(f"🧠 Memory Save Tool: {len(messages)} messages, tags={tags}")
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
            logger.error(f"❌ Memory Save Tool error: {e}")
            return f"Memory save error: {str(e)}"

    async def _arun(self, messages: List[Dict[str, str]], tags: Optional[Dict[str, str]] = None) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        
        # Handle case where LangChain passes JSON string instead of parsed list
        if isinstance(messages, str):
            import json
            messages = json.loads(messages)
            
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, messages, tags)

class LangchainMemoryRuleTool(LangchainBaseTool):
    name: str = "add_permanent_rule"
    description: str = "Adds a permanent rule or preference to user profile. USE THIS for user preferences like 'I prefer detailed explanations' or behavior requests. Input: rule='text of the rule/preference', category='preference'."
    args_schema: Type[BaseModel] = MemoryRuleSchema

    def _run(self, rule: str, category: str = "general") -> str:
        logger.info(f"🧠 Memory Rule Tool: rule='{rule}', category='{category}'")
        try:
            result = mcp_add_permanent_rule(rule, category)
            if result["status"] == "success":
                return f"Rule added successfully: [{category}] {rule}\nRule ID: {result['rule_id']}"
            else:
                return f"Failed to add rule: {result.get('error', 'Unknown error')}"
        except Exception as e:
            logger.error(f"❌ Memory Rule Tool error: {e}")
            return f"Memory rule error: {str(e)}"

    async def _arun(self, rule: str, category: str = "general") -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, rule, category)

class LangchainMemoryStatsTool(LangchainBaseTool):
    name: str = "get_memory_stats"
    description: str = "Gets diagnostic information about the memory system status and usage statistics."
    args_schema: Type[BaseModel] = BaseModel

    def _run(self) -> str:
        logger.info("🧠 Memory Stats Tool called")
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
                return f"Failed to get memory stats: {result.get('error', 'Unknown error')}"
        except Exception as e:
            logger.error(f"❌ Memory Stats Tool error: {e}")
            return f"Memory stats error: {str(e)}"

    async def _arun(self) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run)

# ===== SANDBOX TOOLS =====

class LangchainSandboxExecuteTool(LangchainBaseTool):
    name: str = "execute_python_sandbox"
    description: str = (
        "Executes Python code in a secure, isolated sandbox environment. "
        "Use this tool to test code snippets, debug errors, verify logic, perform calculations, or answer 'what does this code do?' questions. "
        "The code must be valid Python syntax. Returns stdout, stderr, and execution status. "
        "IMPORTANT: Use this tool to verify any complex code before presenting it as a final answer."
    )
    args_schema: Type[BaseModel] = SandboxExecuteSchema

    def _run(self, code: str) -> str:
        logger.info(f"🔒 Sandbox Execute Tool: Executing code in sandbox")
        try:
            result = execute_code(code)
            
            # Format result for LLM consumption
            output_parts = []
            
            if result['success']:
                output_parts.append("✅ Code executed successfully")
                if result['stdout']:
                    output_parts.append(f"Output:\n{result['stdout']}")
                if result['stderr']:
                    output_parts.append(f"Warnings/Info:\n{result['stderr']}")
            else:
                output_parts.append("❌ Code execution failed")
                if result['stderr']:
                    output_parts.append(f"Error:\n{result['stderr']}")
                if result['stdout']:
                    output_parts.append(f"Partial Output:\n{result['stdout']}")
            
            output_parts.append(f"Execution time: {result['execution_time']:.2f}s")
            output_parts.append(f"Method: {result['method']}")
            
            if result.get('validation', {}).get('warnings'):
                output_parts.append(f"Validation warnings: {'; '.join(result['validation']['warnings'])}")
            
            return "\n\n".join(output_parts)
            
        except Exception as e:
            logger.error(f"❌ Sandbox Execute Tool error: {e}")
            return f"Sandbox execution error: {str(e)}"

    async def _arun(self, code: str) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, code)

class LangchainSandboxDebugTool(LangchainBaseTool):
    name: str = "debug_python_sandbox"
    description: str = (
        "Debug Python code in sandbox with detailed analysis and optional expected output comparison. "
        "Use this when you need comprehensive debugging information, performance analysis, or to compare actual vs expected output. "
        "Provides detailed execution report including timing, return codes, and validation warnings."
    )
    args_schema: Type[BaseModel] = SandboxDebugSchema

    def _run(self, code: str, expected_output: Optional[str] = None) -> str:
        logger.info(f"🔒 Sandbox Debug Tool: Debugging code in sandbox")
        try:
            result = debug_code(code, expected_output)
            return result
        except Exception as e:
            logger.error(f"❌ Sandbox Debug Tool error: {e}")
            return f"Sandbox debug error: {str(e)}"

    async def _arun(self, code: str, expected_output: Optional[str] = None) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, code, expected_output)

class LangchainSandboxStatsTool(LangchainBaseTool):
    name: str = "get_sandbox_stats"
    description: str = "Gets diagnostic information about the sandbox system status, configuration, and health."
    args_schema: Type[BaseModel] = BaseModel

    def _run(self) -> str:
        logger.info("🔒 Sandbox Stats Tool called")
        try:
            result = get_sandbox_stats()
            if result["status"] == "success":
                stats = result["stats"]
                summary = "Sandbox System Statistics:\n"
                summary += f"• Available: {stats['sandbox_available']}\n"
                summary += f"• Subprocess support: {stats['subprocess_available']}\n"
                summary += f"• Timeout: {stats['timeout_seconds']}s\n"
                summary += f"• Max output size: {stats['max_output_size']} chars\n"
                summary += f"• Max memory: {stats['max_memory_mb']} MB\n"
                summary += f"• Test execution: {'✅' if stats['test_execution'] else '❌'}\n"
                summary += f"• Base directory: {stats['base_directory']}\n"
                summary += f"• Security: {stats['allowed_imports_count']} allowed, {stats['blocked_imports_count']} blocked imports"
                return summary
            else:
                return f"Failed to get sandbox stats: {result.get('error', 'Unknown error')}"
        except Exception as e:
            logger.error(f"❌ Sandbox Stats Tool error: {e}")
            return f"Sandbox stats error: {str(e)}"

    async def _arun(self) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run)

# ===== WEB SEARCH TOOL =====

class LangchainWebSearchTool(LangchainBaseTool):
    name: str = "search_web"
    description: str = (
        "Searches the web and returns HIGH-QUALITY, AUTHORITATIVE content from trusted sources. "
        "Prioritizes official documentation, expert educational content, and reputable community sources. "
        "Returns actual scraped content, not just search result summaries. "
        "Use for: current information, latest versions, authoritative guides, official best practices."
    )
    args_schema: Type[BaseModel] = WebSearchSchema

    def _run(self, query: str, max_results: int = 3) -> str:
        logger.info(f"🔍 High-Quality Web Search: query='{query}', max_results={max_results}")
        try:
            # Get initial search results
            search_results = self._get_search_results(query, max_results * 3)
            
            if not search_results:
                return f"No search results found for query: '{query}'"
            
            # Find highest quality source using tiered approach
            best_content = self._find_and_scrape_best_source(search_results, query)
            
            if best_content:
                return best_content
            else:
                return f"No high-quality authoritative sources found for: '{query}'. Try refining your search terms or asking about established topics covered in official documentation."
            
        except Exception as e:
            logger.error(f"🔍 Web Search Tool error: {e}")
            return f"Web search failed: {str(e)}"
    
    def _get_search_results(self, query: str, max_results: int) -> List[Dict]:
        """Get search results from Google Custom Search API"""
        try:
            if not GOOGLE_API_KEY:
                logger.warning("Google Custom Search API key not configured")
                return []
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': GOOGLE_API_KEY,
                'cx': GOOGLE_SEARCH_ENGINE_ID,
                'q': query,
                'num': min(max_results, 10),  # Google allows max 10 per request
                'safe': 'medium'
            }
            
            logger.debug(f"🔍 Google Custom Search API call: {query}")
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 403:
                logger.error("Google Custom Search API: Quota exceeded or invalid API key")
                return []
            elif response.status_code == 429:
                logger.error("Google Custom Search API: Rate limit exceeded")
                return []
            
            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                logger.info(f"🔍 Google Custom Search: No results found for '{query}'")
                return []
            
            results = []
            for item in items:
                results.append({
                    'title': item.get('title', ''),
                    'body': item.get('snippet', ''),
                    'href': item.get('link', ''),
                    'display_link': item.get('displayLink', '')
                })
            
            logger.info(f"🔍 Google Custom Search: Found {len(results)} results for '{query}'")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Custom Search API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Google Custom Search failed: {e}")
            return []
    
    def _search_bing(self, query: str, max_results: int) -> List[Dict]:
        """Search using Bing Search API (if configured) or web scraping"""
        try:
            # Check if Bing Search API is configured
            bing_api_key = os.getenv("BING_SEARCH_API_KEY")
            
            if bing_api_key:
                return self._search_bing_api(query, max_results, bing_api_key)
            else:
                # Fallback to simple web scraping of Bing
                return self._search_bing_scrape(query, max_results)
                
        except Exception as e:
            logger.debug(f"Bing search failed: {e}")
            return []
    
    def _search_bing_api(self, query: str, max_results: int, api_key: str) -> List[Dict]:
        """Search using official Bing Search API"""
        try:
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {'Ocp-Apim-Subscription-Key': api_key}
            params = {
                'q': query,
                'count': min(max_results, 50),  # Bing allows up to 50
                'responseFilter': 'Webpages'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            web_pages = data.get('webPages', {}).get('value', [])
            
            results = []
            for page in web_pages:
                results.append({
                    'title': page.get('name', ''),
                    'body': page.get('snippet', ''),
                    'href': page.get('url', '')
                })
            
            logger.info(f"🔍 Bing API Search: Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.debug(f"Bing API search failed: {e}")
            return []
    
    def _search_bing_scrape(self, query: str, max_results: int) -> List[Dict]:
        """Fallback: scrape Bing search results (less reliable but works without API keys)"""
        try:
            import urllib.parse
            from bs4 import BeautifulSoup
            
            # Encode the query for URL
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://www.bing.com/search?q={encoded_query}&count={min(max_results, 10)}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Find search results in Bing's HTML structure
            for result_div in soup.find_all('li', class_='b_algo')[:max_results]:
                title_elem = result_div.find('h2')
                if not title_elem:
                    continue
                    
                link_elem = title_elem.find('a')
                if not link_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                href = link_elem.get('href', '')
                
                # Find description
                desc_elem = result_div.find('p') or result_div.find('div', class_='b_caption')
                body = desc_elem.get_text(strip=True) if desc_elem else ""
                
                if title and href:
                    results.append({
                        'title': title,
                        'body': body,
                        'href': href
                    })
            
            logger.info(f"🔍 Bing Scrape Search: Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.debug(f"Bing scrape search failed: {e}")
            return []
    
    def _prioritize_by_domain(self, results: List[Dict], query: str) -> List[Dict]:
        """Prioritize search results based on domain reputation and query context"""
        from urllib.parse import urlparse
        
        # Detect query context for domain-specific prioritization
        query_lower = query.lower()
        tech_context = self._detect_tech_context(query_lower)
        
        # Score and sort results
        scored_results = []
        for result in results:
            url = result.get('href', '')
            if not url:
                continue
                
            try:
                domain = urlparse(url).netloc.lower()
                # Remove www. prefix for matching
                domain = domain.replace('www.', '')
                
                score = self._calculate_domain_score(domain, tech_context, query_lower)
                
                # Add domain tier information to result
                tier = self._get_domain_tier(domain)
                result['_domain_tier'] = tier
                result['_score'] = score
                
                scored_results.append((score, result))
                
            except Exception as e:
                logger.debug(f"Error parsing URL {url}: {e}")
                # Keep result but with low score
                result['_domain_tier'] = 'other'
                result['_score'] = 0
                scored_results.append((0, result))
        
        # Sort by score (highest first) and return results
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [result for score, result in scored_results]
    
    def _detect_tech_context(self, query: str) -> str:
        """Detect the technology context from the query"""
        if any(term in query for term in ['flutter', 'dart', 'widget']):
            return 'flutter'
        elif any(term in query for term in ['python', 'django', 'flask', 'pip']):
            return 'python'
        elif any(term in query for term in ['javascript', 'nodejs', 'npm', 'react', 'vue']):
            return 'javascript'
        elif any(term in query for term in ['java', 'spring', 'maven', 'gradle']):
            return 'java'
        elif any(term in query for term in ['android', 'kotlin']):
            return 'android'
        elif any(term in query for term in ['ios', 'swift', 'xcode']):
            return 'ios'
        else:
            return 'general'
    
    def _get_domain_tier(self, domain: str) -> str:
        """Get the tier classification for a domain"""
        for tier, domains in PRIORITY_DOMAINS.items():
            if domain in domains:
                return tier
        return 'other'
    
    def _calculate_domain_score(self, domain: str, tech_context: str, query: str) -> int:
        """Calculate priority score for a domain based on context"""
        base_score = 0
        
        # Base scoring by tier
        tier = self._get_domain_tier(domain)
        if tier == 'tier_1_official':
            base_score = 1000
        elif tier == 'tier_2_community':
            base_score = 500
        elif tier == 'tier_3_news':
            base_score = 100
        else:
            base_score = 10
        
        # Context-specific bonuses
        context_bonus = 0
        
        # Technology-specific domain bonuses
        if tech_context == 'flutter':
            if domain in ['docs.flutter.dev', 'flutter.dev', 'dart.dev']:
                context_bonus = 500
            elif domain == 'stackoverflow.com':
                context_bonus = 200
        elif tech_context == 'python':
            if domain in ['docs.python.org', 'python.org']:
                context_bonus = 500
            elif domain == 'stackoverflow.com':
                context_bonus = 200
        elif tech_context == 'javascript':
            if domain in ['developer.mozilla.org', 'nodejs.org', 'reactjs.org', 'vuejs.org']:
                context_bonus = 500
            elif domain == 'stackoverflow.com':
                context_bonus = 200
        
        # Special handling for GitHub - higher for code-related queries
        if domain == 'github.com' and any(term in query for term in ['example', 'code', 'repository', 'library']):
            context_bonus = 300
        
        # News queries get bonus for news sites
        if any(term in query for term in ['news', 'announcement', 'release', 'update']) and tier == 'tier_3_news':
            context_bonus = 200
            
        # StackOverflow gets bonus for problem-solving queries
        if domain == 'stackoverflow.com' and any(term in query for term in ['error', 'problem', 'how to', 'fix', 'debug']):
            context_bonus = 300
        
        return base_score + context_bonus

    def _find_and_scrape_best_source(self, search_results: List[Dict], query: str) -> Optional[str]:
        """Find and scrape the best source from search results with improved error handling"""
        # Define priority domains
        PRIORITY_DOMAINS = {
            "tier_1_official": ["docs.python.org", "dart.dev", "docs.flutter.dev", "api.flutter.dev", "fastapi.tiangolo.com"],
            "tier_2_educational": ["realpython.com", "developer.mozilla.org", "w3schools.com"], 
            "tier_3_community": ["stackoverflow.com", "github.com", "reddit.com"],
            "tier_4_blogs": ["medium.com", "dev.to", "hashnode.com"]
        }
        
        tier_order = ["tier_1_official", "tier_2_educational", "tier_3_community", "tier_4_blogs"]
        failed_sources = []
        partial_content = []
        
        for tier_name in tier_order:
            tier_domains = PRIORITY_DOMAINS[tier_name]
            for result in search_results:
                href = result.get('href', '')
                if not href:
                    continue
                
                from urllib.parse import urlparse
                try:
                    domain = urlparse(href).netloc.replace('www.', '')
                    if any(tier_domain in domain for tier_domain in tier_domains):
                        logger.info(f"🏆 Found {tier_name} source: {domain}")
                        content = self._scrape_content(href, result.get('title', ''), tier_name)
                        
                        if content:
                            if content.startswith("❌"):  # Error message from scraping
                                failed_sources.append(f"{domain}: {content}")
                                continue
                            elif len(content.strip()) > 200:  # Good content threshold
                                logger.info(f"✅ Successfully scraped from {tier_name}: {domain}")
                                return content
                            else:
                                partial_content.append(f"{domain}: {content[:100]}...")
                        
                        logger.warning(f"⚠️ No usable content from {domain}")
                        
                except Exception as e:
                    logger.debug(f"Error parsing URL {href}: {e}")
                    failed_sources.append(f"{href}: Parse error")
                    continue
        
        # If no good sources found, return summary of what was tried
        if failed_sources or partial_content:
            summary = f"No high-quality authoritative sources found for: '{query}'. "
            summary += "Connection issues encountered:\n"
            
            for error in failed_sources[:3]:  # Show first 3 failures
                summary += f"• {error}\n"
                
            if partial_content:
                summary += "\nLimited content found:\n"
                for partial in partial_content[:2]:
                    summary += f"• {partial}\n"
            
            summary += "Try refining your search terms or asking about established topics covered in official documentation."
            return summary
        
        return None

    def _scrape_content(self, url: str, title: str, tier: str) -> Optional[str]:
        """Scrape content from URL with improved error handling"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            logger.info(f"🔗 Scraping content from: {url}")
            
            # Try with SSL verification first, then without if it fails
            for verify_ssl in [True, False]:
                try:
                    response = requests.get(url, headers=headers, timeout=15, verify=verify_ssl)
                    response.raise_for_status()
                    break
                except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                    if verify_ssl:
                        logger.warning(f"SSL error for {url}, retrying without SSL verification")
                        continue
                    else:
                        raise e
            
            soup = BeautifulSoup(response.text, 'html.parser')
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Try multiple content selectors
            content_selectors = [
                'main', 'article', '.content', '.post-content', '.entry-content', 
                '.article-content', '#content', '.page-content', 'body'
            ]
            
            content_area = None
            for selector in content_selectors:
                content_area = soup.select_one(selector)
                if content_area:
                    break
            
            if content_area:
                text = content_area.get_text(separator='\n', strip=True)
                # Clean up excessive whitespace
                text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
                
                if len(text) > 3000:
                    text = text[:3000] + "\n\n... (content truncated)"
                
                tier_indicator = {
                    "tier_1_official": "🏛️ **OFFICIAL DOCUMENTATION**",
                    "tier_2_educational": "🎓 **EDUCATIONAL CONTENT**", 
                    "tier_3_community": "👥 **COMMUNITY CONTENT**",
                    "tier_4_blogs": "📝 **BLOG CONTENT**"
                }.get(tier, "🌐 **WEB CONTENT**")
                
                return f"{tier_indicator}\n**Source**: {title}\n**URL**: {url}\n\n{text}"
            return None
            
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL error scraping {url}: {e}")
            return f"❌ SSL connection failed for {url}"
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error scraping {url}: {e}")
            return f"❌ Connection failed for {url}"
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout scraping {url}: {e}")
            return f"❌ Request timeout for {url}"
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None

    async def _arun(self, query: str, max_results: int = 5) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, query, max_results)

# ===== GIT OPERATIONS TOOLS =====

class GitStatusSchema(BaseModel):
    directory: str = Field(description="Directory path to check git status (defaults to current directory)", default=".")

class GitDiffSchema(BaseModel):
    directory: str = Field(description="Directory path for git diff (defaults to current directory)", default=".")
    file_path: Optional[str] = Field(description="Specific file to diff (optional)", default=None)
    staged: bool = Field(description="Show staged changes only", default=False)

class GitCommitSchema(BaseModel):
    directory: str = Field(description="Directory path for git commit (defaults to current directory)", default=".")
    message: str = Field(description="Commit message")
    add_all: bool = Field(description="Add all changes before committing", default=False)

class GitBranchSchema(BaseModel):
    directory: str = Field(description="Directory path for git operations (defaults to current directory)", default=".")
    action: str = Field(description="Branch action: 'list', 'create', 'checkout', 'delete'")
    branch_name: Optional[str] = Field(description="Branch name for create/checkout/delete operations", default=None)

class GitLogSchema(BaseModel):
    directory: str = Field(description="Directory path for git log (defaults to current directory)", default=".")
    limit: int = Field(description="Number of commits to show", default=10)
    oneline: bool = Field(description="Show one line per commit", default=True)

class LangchainGitStatusTool(LangchainBaseTool):
    name: str = "git_status"
    description: str = "Shows the current git status of a repository, including modified files, staged changes, and untracked files."
    args_schema: Type[BaseModel] = GitStatusSchema

    def _run(self, directory: str = ".") -> str:
        logger.info(f"🔧 Git Status Tool: directory='{directory}'")
        try:
            # Use explicit git path and inherit environment
            result = subprocess.run(
                ["/usr/bin/git", "status", "--porcelain"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30,
                env=os.environ
            )
            
            if result.returncode != 0:
                return f"Git status failed: {result.stderr.strip()}"
            
            output = result.stdout.strip()
            if not output:
                return "Working tree clean - no changes to commit"
            
            # Parse porcelain output for better formatting
            lines = output.split('\n')
            modified = []
            staged = []
            untracked = []
            
            for line in lines:
                if len(line) >= 3:
                    status = line[:2]
                    filename = line[3:]
                    
                    if status[0] != ' ' and status[0] != '?':
                        staged.append(f"  {filename}")
                    if status[1] != ' ':
                        if status[1] == '?':
                            untracked.append(f"  {filename}")
                        else:
                            modified.append(f"  {filename}")
            
            summary = "Git Status Summary:\n"
            if staged:
                summary += f"\n📋 Staged for commit:\n" + "\n".join(staged)
            if modified:
                summary += f"\n✏️ Modified (not staged):\n" + "\n".join(modified)
            if untracked:
                summary += f"\n❓ Untracked files:\n" + "\n".join(untracked)
            
            return summary
            
        except subprocess.TimeoutExpired:
            return "Git status timed out"
        except FileNotFoundError:
            return "Git command not found - ensure git is installed"
        except Exception as e:
            logger.error(f"🔧 Git Status Tool error: {e}")
            return f"Git status error: {str(e)}"

    async def _arun(self, directory: str = ".") -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory)

class LangchainGitDiffTool(LangchainBaseTool):
    name: str = "git_diff"
    description: str = "Shows git diff of changes in the repository. Can show unstaged changes, staged changes, or diff for specific files."
    args_schema: Type[BaseModel] = GitDiffSchema

    def _run(self, directory: str = ".", file_path: Optional[str] = None, staged: bool = False) -> str:
        logger.info(f"🔧 Git Diff Tool: directory='{directory}', file='{file_path}', staged={staged}")
        try:
            cmd = ["/usr/bin/git", "diff"]
            if staged:
                cmd.append("--staged")
            if file_path:
                cmd.append("--")
                cmd.append(file_path)
            
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                env=os.environ,
                timeout=60
            )
            
            if result.returncode != 0:
                return f"Git diff failed: {result.stderr.strip()}"
            
            output = result.stdout.strip()
            if not output:
                return "No changes to show"
            
            # Limit output size for readability
            if len(output) > 5000:
                output = output[:5000] + "\n\n... (diff truncated - too long)"
            
            diff_type = "staged changes" if staged else "unstaged changes"
            file_info = f" for {file_path}" if file_path else ""
            
            return f"Git diff ({diff_type}{file_info}):\n\n{output}"
            
        except subprocess.TimeoutExpired:
            return "Git diff timed out"
        except FileNotFoundError:
            return "Git command not found - ensure git is installed"
        except Exception as e:
            logger.error(f"🔧 Git Diff Tool error: {e}")
            return f"Git diff error: {str(e)}"

    async def _arun(self, directory: str = ".", file_path: Optional[str] = None, staged: bool = False) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory, file_path, staged)

class LangchainGitCommitTool(LangchainBaseTool):
    name: str = "git_commit"
    description: str = "Creates a git commit with the specified message. Can optionally add all changes before committing."
    args_schema: Type[BaseModel] = GitCommitSchema

    def _run(self, directory: str = ".", message: str = "", add_all: bool = False) -> str:
        logger.info(f"🔧 Git Commit Tool: directory='{directory}', add_all={add_all}")
        try:
            if not message.strip():
                return "Commit message cannot be empty"
            
            # Add all changes if requested
            if add_all:
                add_result = subprocess.run(
                    ["/usr/bin/git", "add", "."],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=os.environ
                )
                if add_result.returncode != 0:
                    return f"Git add failed: {add_result.stderr.strip()}"
            
            # Create commit
            result = subprocess.run(
                ["/usr/bin/git", "commit", "-m", message],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=60,
                env=os.environ
            )
            
            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "nothing to commit" in stderr:
                    return "Nothing to commit - working tree clean"
                return f"Git commit failed: {stderr}"
            
            # Get commit hash
            hash_result = subprocess.run(
                ["/usr/bin/git", "rev-parse", "HEAD"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10,
                env=os.environ
            )
            
            commit_hash = hash_result.stdout.strip()[:8] if hash_result.returncode == 0 else "unknown"
            
            return f"✅ Commit successful!\nCommit: {commit_hash}\nMessage: {message}"
            
        except subprocess.TimeoutExpired:
            return "Git commit timed out"
        except FileNotFoundError:
            return "Git command not found - ensure git is installed"
        except Exception as e:
            logger.error(f"🔧 Git Commit Tool error: {e}")
            return f"Git commit error: {str(e)}"

    async def _arun(self, directory: str = ".", message: str = "", add_all: bool = False) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory, message, add_all)

class LangchainGitBranchTool(LangchainBaseTool):
    name: str = "git_branch"
    description: str = "Manages git branches. Actions: 'list' (show all branches), 'create' (new branch), 'checkout' (switch branch), 'delete' (remove branch)."
    args_schema: Type[BaseModel] = GitBranchSchema

    def _run(self, directory: str = ".", action: str = "list", branch_name: Optional[str] = None) -> str:
        logger.info(f"🔧 Git Branch Tool: directory='{directory}', action='{action}', branch='{branch_name}'")
        try:
            if action == "list":
                result = subprocess.run(
                    ["/usr/bin/git", "branch", "-a"],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=os.environ
                )
                if result.returncode != 0:
                    return f"Git branch list failed: {result.stderr.strip()}"
                
                branches = result.stdout.strip()
                if not branches:
                    return "No branches found"
                
                return f"Git branches:\n{branches}"
                
            elif action == "create":
                if not branch_name:
                    return "Branch name required for create action"
                
                result = subprocess.run(
                    ["/usr/bin/git", "checkout", "-b", branch_name],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=os.environ
                )
                if result.returncode != 0:
                    return f"Git branch create failed: {result.stderr.strip()}"
                
                return f"✅ Created and switched to branch '{branch_name}'"
                
            elif action == "checkout":
                if not branch_name:
                    return "Branch name required for checkout action"
                
                result = subprocess.run(
                    ["/usr/bin/git", "checkout", branch_name],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=os.environ
                )
                if result.returncode != 0:
                    return f"Git checkout failed: {result.stderr.strip()}"
                
                return f"✅ Switched to branch '{branch_name}'"
                
            elif action == "delete":
                if not branch_name:
                    return "Branch name required for delete action"
                
                result = subprocess.run(
                    ["/usr/bin/git", "branch", "-d", branch_name],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=os.environ
                )
                if result.returncode != 0:
                    return f"Git branch delete failed: {result.stderr.strip()}"
                
                return f"✅ Deleted branch '{branch_name}'"
                
            else:
                return f"Unknown action '{action}'. Use: list, create, checkout, delete"
            
        except subprocess.TimeoutExpired:
            return "Git branch operation timed out"
        except FileNotFoundError:
            return "Git command not found - ensure git is installed"
        except Exception as e:
            logger.error(f"🔧 Git Branch Tool error: {e}")
            return f"Git branch error: {str(e)}"

    async def _arun(self, directory: str = ".", action: str = "list", branch_name: Optional[str] = None) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory, action, branch_name)

class LangchainGitLogTool(LangchainBaseTool):
    name: str = "git_log"
    description: str = "Shows git commit history with configurable limit and format options."
    args_schema: Type[BaseModel] = GitLogSchema

    def _run(self, directory: str = ".", limit: int = 10, oneline: bool = True) -> str:
        logger.info(f"🔧 Git Log Tool: directory='{directory}', limit={limit}, oneline={oneline}")
        try:
            cmd = ["/usr/bin/git", "log", f"--max-count={limit}"]
            if oneline:
                cmd.append("--oneline")
            else:
                cmd.append("--pretty=format:%h - %an, %ar : %s")
            
            result = subprocess.run(
                cmd,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30,
                env=os.environ
            )
            
            if result.returncode != 0:
                return f"Git log failed: {result.stderr.strip()}"
            
            output = result.stdout.strip()
            if not output:
                return "No commits found"
            
            return f"Git commit history (last {limit} commits):\n\n{output}"
            
        except subprocess.TimeoutExpired:
            return "Git log timed out"
        except FileNotFoundError:
            return "Git command not found - ensure git is installed"
        except Exception as e:
            logger.error(f"🔧 Git Log Tool error: {e}")
            return f"Git log error: {str(e)}"

    async def _arun(self, directory: str = ".", limit: int = 10, oneline: bool = True) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory, limit, oneline)

# ===== GITHUB API TOOLS =====

class GitHubRepoSearchSchema(BaseModel):
    query: str = Field(description="Search query for GitHub repositories. Include language, topic, or specific terms.")
    language: Optional[str] = Field(description="Programming language filter (e.g., python, javascript, dart)", default=None)
    max_results: int = Field(description="Maximum number of repositories to return", default=5)

class GitHubIssueSearchSchema(BaseModel):
    repository: str = Field(description="Repository in format 'owner/repo' (e.g., 'facebook/react')")
    state: str = Field(description="Issue state: 'open', 'closed', or 'all'", default="open")
    max_results: int = Field(description="Maximum number of issues to return", default=5)

class GitHubReleaseSchema(BaseModel):
    repository: str = Field(description="Repository in format 'owner/repo' (e.g., 'flutter/flutter')")
    max_results: int = Field(description="Maximum number of releases to return", default=5)

# ===== REPOSITORY ANALYSIS SCHEMAS =====

class RepoExploreSchema(BaseModel):
    directory: str = Field(description="Directory path to explore (default: current directory)", default=".")
    max_depth: int = Field(description="Maximum depth to explore", default=3)
    include_files: bool = Field(description="Whether to include files in output", default=True)

class DependencyAnalysisSchema(BaseModel):
    directory: str = Field(description="Directory path to analyze (default: current directory)", default=".")
    file_types: Optional[str] = Field(description="Comma-separated file types to analyze (e.g., 'package.json,pubspec.yaml,requirements.txt')", default=None)

class CodeMetricsSchema(BaseModel):
    directory: str = Field(description="Directory path to analyze (default: current directory)", default=".")
    language: Optional[str] = Field(description="Programming language to focus on", default=None)

# ===== DEVELOPMENT HELPER SCHEMAS =====

class PackageSearchSchema(BaseModel):
    query: str = Field(description="Package name or search terms")
    language: str = Field(description="Programming language/ecosystem (npm, pip, pub, cargo, maven, etc.)")
    max_results: int = Field(description="Maximum number of results to return", default=5)

class BuildCommandSchema(BaseModel):
    directory: str = Field(description="Directory path to analyze for build configuration", default=".")
    action: str = Field(description="Build action: 'detect', 'run', 'test', 'lint', 'format', 'clean'", default="detect")
    command: Optional[str] = Field(description="Specific command to run (when action='run')", default=None)

class ProjectScaffoldSchema(BaseModel):
    project_type: str = Field(description="Type of project to create (flutter, react, python, node, etc.)")
    name: str = Field(description="Project name")
    directory: str = Field(description="Directory to create project in", default=".")
    template: Optional[str] = Field(description="Specific template or framework variant", default=None)

class AutoLinterSchema(BaseModel):
    directory: str = Field(description="Directory path to analyze/fix", default=".")
    action: str = Field(description="Action: 'analyze', 'fix', 'format', 'suggest', 'check'", default="analyze")
    language: Optional[str] = Field(description="Language to focus on (auto-detected if not specified)", default=None)
    auto_fix: bool = Field(description="Automatically apply fixes where possible", default=False)

# ===== AUTO-LINTER INTEGRATION TOOL =====

class LangchainAutoLinterTool(LangchainBaseTool):
    name: str = "auto_linter_analyzer"
    description: str = "Integrates with VS Code extension auto-linters and fixers for multiple languages. Knows about Flutter analyze, dart fix, ESLint, Prettier, etc."
    args_schema: Type[BaseModel] = AutoLinterSchema

    def _run(self, directory: str = ".", action: str = "analyze", language: Optional[str] = None, auto_fix: bool = False) -> str:
        logger.info(f"🔧 Auto-Linter: directory='{directory}', action='{action}', language='{language}', auto_fix={auto_fix}")
        try:
            from pathlib import Path
            import subprocess
            
            path = Path(directory).resolve()
            if not path.exists():
                return f"Directory does not exist: {directory}"
            
            # Auto-detect language if not specified
            if not language:
                language = self._detect_project_language(path)
            
            if action == "analyze":
                return self._run_analysis(path, language)
            elif action == "fix":
                return self._run_auto_fix(path, language, auto_fix)
            elif action == "format":
                return self._run_formatting(path, language)
            elif action == "suggest":
                return self._generate_suggestions(path, language)
            elif action == "check":
                return self._run_comprehensive_check(path, language)
            else:
                return f"Invalid action '{action}'. Use: analyze, fix, format, suggest, check"
                
        except Exception as e:
            logger.error(f"🔧 Auto-Linter error: {e}")
            return f"Auto-linter operation failed: {str(e)}"
    
    def _detect_project_language(self, path: Path) -> str:
        """Auto-detect the primary language of the project"""
        # Check for project files to determine language
        if (path / 'pubspec.yaml').exists():
            return 'flutter'
        elif (path / 'package.json').exists():
            # Check if it's React, Vue, etc.
            try:
                import json
                with open(path / 'package.json', 'r') as f:
                    package_data = json.load(f)
                dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
                
                if 'react' in dependencies:
                    return 'react'
                elif 'vue' in dependencies:
                    return 'vue'
                elif '@angular/core' in dependencies:
                    return 'angular'
                else:
                    return 'javascript'
            except:
                return 'javascript'
        elif (path / 'requirements.txt').exists() or (path / 'setup.py').exists():
            return 'python'
        elif (path / 'Cargo.toml').exists():
            return 'rust'
        elif (path / 'go.mod').exists():
            return 'go'
        elif (path / 'pom.xml').exists() or (path / 'build.gradle').exists():
            return 'java'
        else:
            return 'unknown'
    
    def _run_analysis(self, path: Path, language: str) -> str:
        """Run language-specific analysis tools"""
        results = []
        
        if language == 'flutter':
            results.extend(self._flutter_analysis(path))
        elif language in ['javascript', 'react', 'vue', 'angular']:
            results.extend(self._javascript_analysis(path))
        elif language == 'python':
            results.extend(self._python_analysis(path))
        elif language == 'rust':
            results.extend(self._rust_analysis(path))
        elif language == 'go':
            results.extend(self._go_analysis(path))
        elif language == 'java':
            results.extend(self._java_analysis(path))
        else:
            return f"❌ Auto-linter not configured for language: {language}"
        
        if not results:
            return f"✅ No issues found or linting tools not available for {language}"
        
        summary = f"🔧 Auto-Linter Analysis Results for {language.title()}:\n\n"
        summary += "\n".join(results)
        
        return summary
    
    def _flutter_analysis(self, path: Path) -> List[str]:
        """Run Flutter/Dart specific analysis"""
        results = []
        
        # Flutter analyze
        try:
            result = subprocess.run(
                ["flutter", "analyze"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                results.append("✅ **Flutter Analyze**: No issues found")
            else:
                issues = result.stdout.strip()
                if issues:
                    results.append(f"⚠️ **Flutter Analyze Issues**:\n```\n{issues}\n```")
                    results.append("💡 **Auto-fix available**: Run `dart fix --apply` to automatically fix some issues")
        except subprocess.TimeoutExpired:
            results.append("⏰ **Flutter Analyze**: Timed out")
        except FileNotFoundError:
            results.append("❌ **Flutter not found**: Install Flutter SDK")
        except Exception as e:
            results.append(f"❌ **Flutter Analyze Error**: {str(e)}")
        
        # Dart analyze
        try:
            result = subprocess.run(
                ["dart", "analyze"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                issues = result.stdout.strip()
                if issues and "flutter analyze" not in issues.lower():
                    results.append(f"⚠️ **Dart Analyze Issues**:\n```\n{issues}\n```")
        except:
            pass  # Flutter analyze likely covers this
        
        # Check for pubspec.yaml issues
        try:
            with open(path / 'pubspec.yaml', 'r') as f:
                content = f.read()
                if 'flutter:' not in content:
                    results.append("⚠️ **Pubspec Warning**: No Flutter configuration found")
        except:
            pass
        
        return results
    
    def _javascript_analysis(self, path: Path) -> List[str]:
        """Run JavaScript/Node.js specific analysis"""
        results = []
        
        # ESLint
        try:
            result = subprocess.run(
                ["npx", "eslint", ".", "--format", "compact"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                results.append("✅ **ESLint**: No issues found")
            else:
                issues = result.stdout.strip()
                if issues:
                    results.append(f"⚠️ **ESLint Issues**:\n```\n{issues[:1000]}{'...' if len(issues) > 1000 else ''}\n```")
                    results.append("💡 **Auto-fix available**: Run `npx eslint . --fix` to automatically fix some issues")
        except subprocess.TimeoutExpired:
            results.append("⏰ **ESLint**: Timed out")
        except FileNotFoundError:
            results.append("📝 **ESLint**: Not configured (install with `npm install eslint`)")
        except Exception as e:
            results.append(f"❌ **ESLint Error**: {str(e)}")
        
        # Prettier check
        try:
            result = subprocess.run(
                ["npx", "prettier", "--check", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                results.append("✅ **Prettier**: Code formatting is consistent")
            else:
                results.append("⚠️ **Prettier**: Code formatting inconsistencies found")
                results.append("💡 **Auto-fix available**: Run `npx prettier --write .` to format all files")
        except FileNotFoundError:
            results.append("📝 **Prettier**: Not configured")
        except:
            pass
        
        # TypeScript check
        if (path / 'tsconfig.json').exists():
            try:
                result = subprocess.run(
                    ["npx", "tsc", "--noEmit"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    results.append("✅ **TypeScript**: No type errors")
                else:
                    errors = result.stdout.strip()
                    if errors:
                        results.append(f"⚠️ **TypeScript Errors**:\n```\n{errors[:1000]}{'...' if len(errors) > 1000 else ''}\n```")
            except:
                pass
        
        return results
    
    def _python_analysis(self, path: Path) -> List[str]:
        """Run Python specific analysis"""
        results = []
        
        # Flake8
        try:
            result = subprocess.run(
                ["python", "-m", "flake8", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                results.append("✅ **Flake8**: No style issues found")
            else:
                issues = result.stdout.strip()
                if issues:
                    results.append(f"⚠️ **Flake8 Issues**:\n```\n{issues[:1000]}{'...' if len(issues) > 1000 else ''}\n```")
                    results.append("💡 **Auto-fix available**: Run `python -m autopep8 --in-place --recursive .`")
        except FileNotFoundError:
            results.append("📝 **Flake8**: Not installed (install with `pip install flake8`)")
        except Exception as e:
            results.append(f"❌ **Flake8 Error**: {str(e)}")
        
        # Black formatter check
        try:
            result = subprocess.run(
                ["python", "-m", "black", "--check", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                results.append("✅ **Black**: Code formatting is consistent")
            else:
                results.append("⚠️ **Black**: Code formatting inconsistencies found")
                results.append("💡 **Auto-fix available**: Run `python -m black .` to format all files")
        except FileNotFoundError:
            results.append("📝 **Black**: Not installed")
        except:
            pass
        
        # MyPy type checking
        try:
            result = subprocess.run(
                ["python", "-m", "mypy", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                results.append("✅ **MyPy**: No type errors")
            else:
                errors = result.stdout.strip()
                if errors:
                    results.append(f"⚠️ **MyPy Type Errors**:\n```\n{errors[:1000]}{'...' if len(errors) > 1000 else ''}\n```")
        except FileNotFoundError:
            results.append("📝 **MyPy**: Not installed")
        except:
            pass
        
        return results
    
    def _rust_analysis(self, path: Path) -> List[str]:
        """Run Rust specific analysis"""
        results = []
        
        # Clippy
        try:
            result = subprocess.run(
                ["cargo", "clippy", "--", "-D", "warnings"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                results.append("✅ **Clippy**: No linting issues found")
            else:
                issues = result.stderr.strip()
                if issues:
                    results.append(f"⚠️ **Clippy Issues**:\n```\n{issues[:1000]}{'...' if len(issues) > 1000 else ''}\n```")
                    results.append("💡 **Auto-fix available**: Run `cargo clippy --fix` for automatic fixes")
        except FileNotFoundError:
            results.append("❌ **Cargo not found**: Install Rust toolchain")
        except Exception as e:
            results.append(f"❌ **Clippy Error**: {str(e)}")
        
        # Rustfmt check
        try:
            result = subprocess.run(
                ["cargo", "fmt", "--check"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                results.append("✅ **Rustfmt**: Code formatting is consistent")
            else:
                results.append("⚠️ **Rustfmt**: Code formatting inconsistencies found")
                results.append("💡 **Auto-fix available**: Run `cargo fmt` to format all files")
        except:
            pass
        
        return results
    
    def _go_analysis(self, path: Path) -> List[str]:
        """Run Go specific analysis"""
        results = []
        
        # Go fmt check
        try:
            result = subprocess.run(
                ["gofmt", "-l", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if not result.stdout.strip():
                results.append("✅ **Gofmt**: Code formatting is consistent")
            else:
                files = result.stdout.strip()
                results.append(f"⚠️ **Gofmt**: Files need formatting:\n```\n{files}\n```")
                results.append("💡 **Auto-fix available**: Run `gofmt -w .` to format all files")
        except FileNotFoundError:
            results.append("❌ **Go not found**: Install Go toolchain")
        except Exception as e:
            results.append(f"❌ **Gofmt Error**: {str(e)}")
        
        # Go vet
        try:
            result = subprocess.run(
                ["go", "vet", "./..."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                results.append("✅ **Go Vet**: No issues found")
            else:
                issues = result.stderr.strip()
                if issues:
                    results.append(f"⚠️ **Go Vet Issues**:\n```\n{issues}\n```")
        except:
            pass
        
        return results
    
    def _java_analysis(self, path: Path) -> List[str]:
        """Run Java specific analysis"""
        results = []
        
        # For Java, we'd typically integrate with tools like:
        # - Checkstyle
        # - SpotBugs
        # - PMD
        # These would typically be run through build tools like Maven/Gradle
        
        if (path / 'pom.xml').exists():
            results.append("📝 **Maven Project Detected**: Use `mvn checkstyle:check` for style analysis")
        elif (path / 'build.gradle').exists():
            results.append("📝 **Gradle Project Detected**: Use `./gradlew check` for analysis")
        else:
            results.append("📝 **Java Project**: Configure Checkstyle/SpotBugs for analysis")
        
        return results
    
    def _run_auto_fix(self, path: Path, language: str, auto_fix: bool) -> str:
        """Run auto-fix tools for the detected language"""
        if not auto_fix:
            return self._suggest_auto_fix_commands(language)
        
        results = []
        
        if language == 'flutter':
            results.extend(self._flutter_auto_fix(path))
        elif language in ['javascript', 'react', 'vue', 'angular']:
            results.extend(self._javascript_auto_fix(path))
        elif language == 'python':
            results.extend(self._python_auto_fix(path))
        elif language == 'rust':
            results.extend(self._rust_auto_fix(path))
        elif language == 'go':
            results.extend(self._go_auto_fix(path))
        
        if not results:
            return f"No auto-fix tools configured for {language}"
        
        return f"🔧 Auto-Fix Results for {language.title()}:\n\n" + "\n".join(results)
    
    def _suggest_auto_fix_commands(self, language: str) -> str:
        """Suggest auto-fix commands without running them"""
        suggestions = {
            'flutter': [
                "dart fix --apply",
                "dart format .",
                "flutter packages get"
            ],
            'javascript': [
                "npx eslint . --fix",
                "npx prettier --write .",
                "npm audit fix"
            ],
            'python': [
                "python -m black .",
                "python -m autopep8 --in-place --recursive .",
                "python -m isort ."
            ],
            'rust': [
                "cargo clippy --fix",
                "cargo fmt"
            ],
            'go': [
                "gofmt -w .",
                "go mod tidy"
            ]
        }
        
        commands = suggestions.get(language, [])
        if not commands:
            return f"No auto-fix suggestions available for {language}"
        
        result = f"💡 **Suggested Auto-Fix Commands for {language.title()}:**\n\n"
        for cmd in commands:
            result += f"   • `{cmd}`\n"
        
        result += f"\n🚀 **Run with auto_fix=True to execute automatically**"
        return result
    
    def _flutter_auto_fix(self, path: Path) -> List[str]:
        """Run Flutter auto-fix tools"""
        results = []
        
        # Dart fix
        try:
            result = subprocess.run(
                ["dart", "fix", "--apply"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if "No fixes to apply" in output:
                    results.append("✅ **Dart Fix**: No fixes needed")
                else:
                    results.append(f"🔧 **Dart Fix Applied**:\n```\n{output}\n```")
            else:
                results.append(f"❌ **Dart Fix Failed**: {result.stderr.strip()}")
        except Exception as e:
            results.append(f"❌ **Dart Fix Error**: {str(e)}")
        
        # Dart format
        try:
            result = subprocess.run(
                ["dart", "format", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                results.append("✅ **Dart Format**: Code formatted successfully")
            else:
                results.append(f"❌ **Dart Format Failed**: {result.stderr.strip()}")
        except Exception as e:
            results.append(f"❌ **Dart Format Error**: {str(e)}")
        
        return results
    
    def _javascript_auto_fix(self, path: Path) -> List[str]:
        """Run JavaScript auto-fix tools"""
        results = []
        
        # ESLint fix
        try:
            result = subprocess.run(
                ["npx", "eslint", ".", "--fix"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            results.append("🔧 **ESLint**: Auto-fix completed")
            if result.stderr:
                results.append(f"ℹ️ **ESLint Output**: {result.stderr.strip()}")
        except Exception as e:
            results.append(f"❌ **ESLint Fix Error**: {str(e)}")
        
        # Prettier format
        try:
            result = subprocess.run(
                ["npx", "prettier", "--write", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            results.append("✅ **Prettier**: Code formatted successfully")
        except Exception as e:
            results.append(f"❌ **Prettier Error**: {str(e)}")
        
        return results
    
    def _python_auto_fix(self, path: Path) -> List[str]:
        """Run Python auto-fix tools"""
        results = []
        
        # Black formatter
        try:
            result = subprocess.run(
                ["python", "-m", "black", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            results.append("✅ **Black**: Code formatted successfully")
        except Exception as e:
            results.append(f"❌ **Black Error**: {str(e)}")
        
        # AutoPEP8
        try:
            result = subprocess.run(
                ["python", "-m", "autopep8", "--in-place", "--recursive", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            results.append("🔧 **AutoPEP8**: PEP8 fixes applied")
        except Exception as e:
            results.append(f"❌ **AutoPEP8 Error**: {str(e)}")
        
        return results
    
    def _rust_auto_fix(self, path: Path) -> List[str]:
        """Run Rust auto-fix tools"""
        results = []
        
        # Clippy fix
        try:
            result = subprocess.run(
                ["cargo", "clippy", "--fix", "--allow-dirty"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            results.append("🔧 **Clippy**: Auto-fixes applied")
        except Exception as e:
            results.append(f"❌ **Clippy Fix Error**: {str(e)}")
        
        # Rustfmt
        try:
            result = subprocess.run(
                ["cargo", "fmt"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            results.append("✅ **Rustfmt**: Code formatted successfully")
        except Exception as e:
            results.append(f"❌ **Rustfmt Error**: {str(e)}")
        
        return results
    
    def _go_auto_fix(self, path: Path) -> List[str]:
        """Run Go auto-fix tools"""
        results = []
        
        # Gofmt
        try:
            result = subprocess.run(
                ["gofmt", "-w", "."],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            results.append("✅ **Gofmt**: Code formatted successfully")
        except Exception as e:
            results.append(f"❌ **Gofmt Error**: {str(e)}")
        
        # Go mod tidy
        try:
            result = subprocess.run(
                ["go", "mod", "tidy"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            results.append("🔧 **Go Mod**: Dependencies tidied")
        except Exception as e:
            results.append(f"❌ **Go Mod Error**: {str(e)}")
        
        return results
    
    def _run_formatting(self, path: Path, language: str) -> str:
        """Run formatting tools only"""
        return self._run_auto_fix(path, language, auto_fix=True)
    
    def _generate_suggestions(self, path: Path, language: str) -> str:
        """Generate intelligent suggestions based on project analysis"""
        suggestions = []
        
        # Check for missing configuration files
        if language == 'flutter':
            if not (path / 'analysis_options.yaml').exists():
                suggestions.append("📝 **Missing analysis_options.yaml**: Add linter rules for better code quality")
            if not (path / '.gitignore').exists():
                suggestions.append("📝 **Missing .gitignore**: Add Flutter-specific gitignore")
        
        elif language in ['javascript', 'react', 'vue']:
            if not (path / '.eslintrc.js').exists() and not (path / '.eslintrc.json').exists():
                suggestions.append("📝 **Missing ESLint config**: Add .eslintrc.js for consistent code style")
            if not (path / '.prettierrc').exists():
                suggestions.append("📝 **Missing Prettier config**: Add .prettierrc for code formatting")
        
        elif language == 'python':
            if not (path / 'setup.cfg').exists() and not (path / 'pyproject.toml').exists():
                suggestions.append("📝 **Missing config**: Add setup.cfg or pyproject.toml for tool configuration")
        
        # VS Code extension suggestions
        vscode_extensions = self._get_recommended_vscode_extensions(language)
        if vscode_extensions:
            suggestions.append(f"💡 **Recommended VS Code Extensions**:\n{vscode_extensions}")
        
        if not suggestions:
            suggestions.append("✅ **Project looks well-configured** for auto-linting and fixing")
        
        return f"💡 **Project Improvement Suggestions for {language.title()}:**\n\n" + "\n".join(suggestions)
    
    def _get_recommended_vscode_extensions(self, language: str) -> str:
        """Get recommended VS Code extensions for the language"""
        extensions = {
            'flutter': [
                "Dart-Code.flutter (Flutter support)",
                "Dart-Code.dart-code (Dart support)",
                "alexisvt.flutter-snippets (Flutter snippets)"
            ],
            'javascript': [
                "dbaeumer.vscode-eslint (ESLint)",
                "esbenp.prettier-vscode (Prettier)",
                "bradlc.vscode-tailwindcss (Tailwind CSS)"
            ],
            'react': [
                "dbaeumer.vscode-eslint (ESLint)",
                "esbenp.prettier-vscode (Prettier)",
                "dsznajder.es7-react-js-snippets (React snippets)"
            ],
            'python': [
                "ms-python.python (Python)",
                "ms-python.flake8 (Flake8)",
                "ms-python.black-formatter (Black)"
            ],
            'rust': [
                "rust-lang.rust-analyzer (Rust Analyzer)",
                "vadimcn.vscode-lldb (LLDB Debugger)"
            ],
            'go': [
                "golang.go (Go)",
                "ms-vscode.vscode-go (Go tools)"
            ]
        }
        
        ext_list = extensions.get(language, [])
        if not ext_list:
            return ""
        
        result = ""
        for ext in ext_list:
            result += f"     • {ext}\n"
        
        return result
    
    def _run_comprehensive_check(self, path: Path, language: str) -> str:
        """Run comprehensive analysis including all available tools"""
        results = []
        
        # Run analysis
        analysis_result = self._run_analysis(path, language)
        results.append(f"## 🔍 Analysis Results\n{analysis_result}")
        
        # Generate suggestions
        suggestions = self._generate_suggestions(path, language)
        results.append(f"\n## 💡 Suggestions\n{suggestions}")
        
        # Show available auto-fixes
        auto_fix_commands = self._suggest_auto_fix_commands(language)
        results.append(f"\n## 🔧 Available Auto-Fixes\n{auto_fix_commands}")
        
        return "\n".join(results)

    async def _arun(self, directory: str = ".", action: str = "analyze", language: Optional[str] = None, auto_fix: bool = False) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory, action, language, auto_fix)

# ===== SLASH COMMAND PROCESSOR =====

class SlashCommandProcessor:
    """Handles slash command parsing and execution"""
    
    def __init__(self):
        self.commands = DEFAULT_SLASH_COMMANDS.copy()
        self._load_custom_commands()
    
    def _load_custom_commands(self):
        """Load custom commands from memory"""
        try:
            # Get custom commands from memory
            custom_commands = mcp_get_context("custom_slash_commands")
            if custom_commands and isinstance(custom_commands, dict):
                for cmd_name, cmd_data in custom_commands.items():
                    if cmd_name.startswith('/') and isinstance(cmd_data, dict):
                        self.commands[cmd_name] = cmd_data
        except Exception as e:
            logger.debug(f"No custom commands found in memory: {e}")
    
    def is_slash_command(self, message: str) -> bool:
        """Check if message is a slash command"""
        return message.strip().startswith('/')
    
    def parse_command(self, message: str) -> Dict[str, Any]:
        """Parse slash command into components"""
        parts = message.strip().split()
        if not parts or not parts[0].startswith('/'):
            return {"valid": False, "error": "Not a valid slash command"}
        
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if command not in self.commands:
            return {
                "valid": False, 
                "error": f"Unknown command '{command}'. Use /commands to see available commands."
            }
        
        return {
            "valid": True,
            "command": command,
            "args": args,
            "raw_args": " ".join(args),
            "config": self.commands[command]
        }
    
    async def execute_command(self, parsed_command: Dict[str, Any]) -> str:
        """Execute a parsed slash command"""
        if not parsed_command.get("valid"):
            return f"❌ {parsed_command.get('error', 'Invalid command')}"
        
        command = parsed_command["command"]
        args = parsed_command["args"]
        raw_args = parsed_command["raw_args"]
        config = parsed_command["config"]
        action = config["action"]
        
        try:
            # Route to appropriate handler based on action
            if action == "save_rule":
                return await self._handle_save_rule(raw_args)
            elif action == "save_memory":
                return await self._handle_save_memory(raw_args)
            elif action == "get_memory":
                return await self._handle_get_memory(raw_args)
            elif action == "delete_memory":
                return await self._handle_delete_memory(raw_args)
            elif action == "get_stats":
                return await self._handle_get_stats()
            elif action == "build_command":
                return await self._handle_build_command(args)
            elif action == "package_search":
                return await self._handle_package_search(args)
            elif action == "repo_analysis":
                return await self._handle_repo_analysis(args)
            elif action == "git_status":
                return await self._handle_git_status()
            elif action == "git_commit":
                return await self._handle_git_commit(raw_args)
            elif action == "git_branch":
                return await self._handle_git_branch(args)
            elif action == "list_commands":
                return self._handle_list_commands(args)
            elif action == "get_help":
                return self._handle_get_help(args)
            elif action == "add_command":
                return await self._handle_add_command(args)
            elif action == "remove_command":
                return await self._handle_remove_command(args)
            elif action == "get_context":
                return await self._handle_get_context()
            elif action == "project_info":
                return await self._handle_project_info(args)
            elif action == "workspace_setting":
                return await self._handle_workspace_setting(args)
            elif action == "correct":
                return await self._handle_correct(raw_args)
            elif action == "fix":
                return await self._handle_fix(raw_args)
            else:
                return f"❌ Action '{action}' not implemented yet"
                
        except Exception as e:
            logger.error(f"Slash command execution error: {e}")
            return f"❌ Error executing {command}: {str(e)}"
    
    # Memory Management Handlers
    async def _handle_save_rule(self, rule_text: str) -> str:
        if not rule_text:
            return "❌ Please provide a rule to save. Usage: /rule <rule_text>"
        
        try:
            result = mcp_save_rule(rule_text)
            return f"✅ Rule saved: {rule_text}"
        except Exception as e:
            return f"❌ Failed to save rule: {str(e)}"
    
    async def _handle_save_memory(self, info: str) -> str:
        if not info:
            return "❌ Please provide information to remember. Usage: /remember <information>"
        
        try:
            tags = {"type": "manual_save", "source": "slash_command"}
            result = mcp_save_interaction([{"role": "user", "content": f"REMEMBER: {info}"}], tags)
            return f"✅ Saved to memory: {info}"
        except Exception as e:
            return f"❌ Failed to save to memory: {str(e)}"
    
    async def _handle_get_memory(self, query: str) -> str:
        if not query:
            return "❌ Please provide a search query. Usage: /recall <query>"
        
        try:
            result = mcp_get_memory_context(query)
            if result:
                return f"🧠 Memory results for '{query}':\n\n{result}"
            else:
                return f"🤔 No memory found for '{query}'"
        except Exception as e:
            return f"❌ Failed to retrieve memory: {str(e)}"
    
    async def _handle_delete_memory(self, query: str) -> str:
        if not query:
            return "❌ Please specify what to forget. Usage: /forget <query>"
        
        try:
            # For now, just save a note about what to forget
            result = mcp_save_interaction([{"role": "user", "content": f"FORGET: {query}"}], {"type": "forget_request"})
            return f"📝 Noted request to forget: {query}"
        except Exception as e:
            return f"❌ Failed to process forget request: {str(e)}"
    
    async def _handle_correct(self, correction_text: str) -> str:
        """Handle /correct command to store AI correction"""
        if not correction_text:
            return "❌ Please provide a correction. Usage: /correct <correction_text>"
        
        try:
            # Get the last AI response from Redis (Tier 1 - Working Memory)
            context = mcp_get_context()
            if not context.get("status") == "success" or not context.get("context", {}).get("short_term"):
                return "❌ No recent AI response found to correct"
            
            # Find the most recent AI response
            recent_messages = context["context"]["short_term"]
            last_ai_response = None
            
            for interaction in reversed(recent_messages):
                messages = interaction.get("messages", [])
                for message in reversed(messages):
                    if message.get("role") == "assistant":
                        last_ai_response = message.get("content")
                        break
                if last_ai_response:
                    break
            
            if not last_ai_response:
                return "❌ No recent AI response found to correct"
            
            # Store the correction
            result = mcp_add_correction(last_ai_response, correction_text)
            
            if result.get("status") == "success":
                return f"✅ Correction stored (ID: {result.get('correction_id')}). I will remember this for future responses."
            else:
                return f"❌ Failed to store correction: {result.get('error')}"
                
        except Exception as e:
            return f"❌ Failed to process correction: {str(e)}"
    
    async def _handle_fix(self, correction_text: str) -> str:
        """Handle /fix command (alias for /correct)"""
        return await self._handle_correct(correction_text)
    
    async def _handle_get_stats(self) -> str:
        try:
            stats = mcp_get_memory_stats()
            return f"📊 System Statistics:\n\n{stats}"
        except Exception as e:
            return f"❌ Failed to get stats: {str(e)}"
    
    # Development Handlers
    async def _handle_build_command(self, args: List[str]) -> str:
        try:
            tool = LangchainBuildCommandTool()
            action = args[0] if args else "detect"
            command = " ".join(args[1:]) if len(args) > 1 else None
            return await tool._arun(action=action, command=command)
        except Exception as e:
            return f"❌ Build command error: {str(e)}"
    
    async def _handle_package_search(self, args: List[str]) -> str:
        if len(args) < 2:
            return "❌ Usage: /package <ecosystem> <query>"
        
        try:
            tool = LangchainPackageSearchTool()
            language = args[0]
            query = " ".join(args[1:])
            return await tool._arun(query=query, language=language)
        except Exception as e:
            return f"❌ Package search error: {str(e)}"
    
    async def _handle_repo_analysis(self, args: List[str]) -> str:
        try:
            analysis_type = args[0] if args else "structure"
            if analysis_type in ["structure", "explore"]:
                tool = LangchainRepoExploreTool()
                return await tool._arun()
            elif analysis_type in ["dependencies", "deps"]:
                tool = LangchainDependencyAnalysisTool()
                return await tool._arun()
            elif analysis_type in ["metrics", "stats"]:
                tool = LangchainCodeMetricsTool()
                return await tool._arun()
            else:
                return "❌ Analysis type must be: structure, dependencies, or metrics"
        except Exception as e:
            return f"❌ Analysis error: {str(e)}"
    
    # Git Handlers
    async def _handle_git_status(self) -> str:
        try:
            tool = LangchainGitStatusTool()
            return await tool._arun()
        except Exception as e:
            return f"❌ Git status error: {str(e)}"
    
    async def _handle_git_commit(self, message: str) -> str:
        if not message:
            return "❌ Please provide a commit message. Usage: /commit <message>"
        
        try:
            tool = LangchainGitCommitTool()
            return await tool._arun(message=message)
        except Exception as e:
            return f"❌ Git commit error: {str(e)}"
    
    async def _handle_git_branch(self, args: List[str]) -> str:
        try:
            tool = LangchainGitBranchTool()
            action = args[0] if args else "list"
            branch_name = args[1] if len(args) > 1 else None
            return await tool._arun(action=action, branch_name=branch_name)
        except Exception as e:
            return f"❌ Git branch error: {str(e)}"
    
    # System Handlers
    def _handle_list_commands(self, args: List[str]) -> str:
        category_filter = args[0] if args else None
        
        if category_filter:
            filtered_commands = {k: v for k, v in self.commands.items() 
                               if v.get("category") == category_filter}
            if not filtered_commands:
                available_categories = set(cmd.get("category") for cmd in self.commands.values())
                return f"❌ No commands found for category '{category_filter}'. Available categories: {', '.join(available_categories)}"
            commands_to_show = filtered_commands
        else:
            commands_to_show = self.commands
        
        # Group by category
        by_category = {}
        for cmd, config in commands_to_show.items():
            category = config.get("category", "other")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append((cmd, config))
        
        result = "📋 Available Slash Commands:\n\n"
        for category, commands in sorted(by_category.items()):
            result += f"**{category.title()}:**\n"
            for cmd, config in sorted(commands):
                result += f"  {cmd} - {config['description']}\n"
            result += "\n"
        
        result += "💡 Use /help <command> for detailed usage information"
        return result
    
    def _handle_get_help(self, args: List[str]) -> str:
        if not args:
            return "❌ Please specify a command. Usage: /help <command>"
        
        command = args[0]
        if not command.startswith('/'):
            command = '/' + command
        
        if command not in self.commands:
            return f"❌ Command '{command}' not found. Use /commands to see available commands."
        
        config = self.commands[command]
        help_text = f"📖 Help for {command}:\n\n"
        help_text += f"**Description:** {config['description']}\n"
        help_text += f"**Usage:** {config['usage']}\n"
        help_text += f"**Example:** {config['example']}\n"
        help_text += f"**Category:** {config['category']}"
        
        return help_text
    
    async def _handle_add_command(self, args: List[str]) -> str:
        if len(args) < 3:
            return "❌ Usage: /add-command <name> <description> <action>"
        
        name = args[0]
        if not name.startswith('/'):
            name = '/' + name
        
        description = args[1].strip('"\'')
        action = args[2]
        
        # Create new command configuration
        new_command = {
            "description": description,
            "usage": f"{name} [args]",
            "example": f"{name} example",
            "category": "custom",
            "action": action
        }
        
        # Add to current commands
        self.commands[name] = new_command
        
        # Save to memory
        try:
            custom_commands = mcp_get_memory_context("custom_slash_commands") or {}
            custom_commands[name] = new_command
            mcp_set_key_value("custom_slash_commands", custom_commands)
            return f"✅ Added custom command {name}: {description}"
        except Exception as e:
            return f"⚠️ Command added to session but failed to save to memory: {str(e)}"
    
    async def _handle_remove_command(self, args: List[str]) -> str:
        if not args:
            return "❌ Usage: /remove-command <name>"
        
        name = args[0]
        if not name.startswith('/'):
            name = '/' + name
        
        if name not in self.commands:
            return f"❌ Command '{name}' not found"
        
        if self.commands[name].get("category") != "custom":
            return f"❌ Cannot remove built-in command '{name}'"
        
        # Remove from current commands
        del self.commands[name]
        
        # Update memory
        try:
            custom_commands = mcp_get_memory_context("custom_slash_commands") or {}
            if name in custom_commands:
                del custom_commands[name]
            mcp_save_interaction([{"role": "system", "content": f"Custom slash commands: {json.dumps(custom_commands)}"}], 
                             {"type": "custom_slash_commands", "key": "custom_slash_commands"})
            return f"✅ Removed custom command {name}"
        except Exception as e:
            return f"⚠️ Command removed from session but failed to update memory: {str(e)}"
    
    # Project Management Handlers
    async def _handle_get_context(self) -> str:
        try:
            context_info = []
            
            # Get session context
            global session_context
            if hasattr(session_context, 'current_session'):
                session = session_context.current_session
                context_info.append(f"**Session Info:**")
                context_info.append(f"  Primary Domain: {session.get('primary_domain', 'Not detected')}")
                context_info.append(f"  Active Language: {session.get('active_language', 'Not detected')}")
                context_info.append(f"  Ongoing Task: {session.get('ongoing_task', 'Not detected')}")
                context_info.append(f"  User Level: {session.get('user_expertise_level', 'Unknown')}")
                context_info.append(f"  Conversation Depth: {session.get('conversation_depth', 0)}")
            
            # Get project context from memory
            project_info = mcp_get_memory_context("current_project")
            if project_info:
                context_info.append(f"\n**Project Info:**")
                context_info.append(f"  {project_info}")
            
            return "📋 Current Context:\n\n" + "\n".join(context_info) if context_info else "📋 No context information available"
        except Exception as e:
            return f"❌ Failed to get context: {str(e)}"
    
    async def _handle_project_info(self, args: List[str]) -> str:
        if not args:
            # Get current project info
            try:
                project_info = mcp_get_memory_context("current_project")
                return f"📂 Current Project: {project_info}" if project_info else "📂 No project information set"
            except Exception as e:
                return f"❌ Failed to get project info: {str(e)}"
        
        # Set project info
        project_name = args[0]
        project_desc = " ".join(args[1:]) if len(args) > 1 else ""
        
        try:
            project_info = f"{project_name}"
            if project_desc:
                project_info += f" - {project_desc}"
            
            mcp_set_key_value("current_project", project_info)
            return f"✅ Set project: {project_info}"
        except Exception as e:
            return f"❌ Failed to set project info: {str(e)}"
    
    async def _handle_workspace_setting(self, args: List[str]) -> str:
        if not args:
            try:
                settings = mcp_get_memory_context("workspace_settings")
                return f"⚙️ Workspace Settings: {settings}" if settings else "⚙️ No workspace settings configured"
            except Exception as e:
                return f"❌ Failed to get workspace settings: {str(e)}"
        
        if len(args) < 2:
            return "❌ Usage: /workspace <setting> <value>"
        
        setting = args[0]
        value = " ".join(args[1:])
        
        try:
            settings = mcp_get_memory_context("workspace_settings") or {}
            if isinstance(settings, str):
                settings = {}
            settings[setting] = value
            
            mcp_set_key_value("workspace_settings", settings)
            return f"✅ Set workspace setting {setting} = {value}"
        except Exception as e:
            return f"❌ Failed to set workspace setting: {str(e)}"

# Global slash command processor
slash_processor = SlashCommandProcessor()

class LangchainGitHubRepoSearchTool(LangchainBaseTool):
    name: str = "search_github_repositories"
    description: str = "Searches GitHub for repositories based on query, language, and other criteria. Useful for finding projects, libraries, or examples."
    args_schema: Type[BaseModel] = GitHubRepoSearchSchema

    def _run(self, query: str, language: Optional[str] = None, max_results: int = 5) -> str:
        logger.info(f"🔍 GitHub Repo Search: query='{query}', language='{language}', max_results={max_results}")
        try:
            # Limit max_results to prevent abuse
            max_results = min(max_results, GITHUB_SEARCH_MAX_RESULTS)
            
            # Build search query
            search_query = query
            if language:
                search_query += f" language:{language}"
            
            # Prepare headers
            headers = {"Accept": "application/vnd.github.v3+json"}
            if GITHUB_TOKEN:
                headers["Authorization"] = f"token {GITHUB_TOKEN}"
            
            # Make API request
            url = f"{GITHUB_API_BASE}/search/repositories"
            params = {
                "q": search_query,
                "sort": "stars",
                "order": "desc",
                "per_page": max_results
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            repositories = data.get("items", [])
            
            if not repositories:
                return f"No repositories found for query: '{query}'"
            
            # Format results
            results = []
            for i, repo in enumerate(repositories, 1):
                name = repo.get("full_name", "Unknown")
                description = repo.get("description", "No description")
                stars = repo.get("stargazers_count", 0)
                language = repo.get("language", "Unknown")
                url = repo.get("html_url", "")
                updated = repo.get("updated_at", "").split("T")[0] if repo.get("updated_at") else "Unknown"
                
                results.append(
                    f"{i}. **{name}** ⭐ {stars:,}\n"
                    f"   Language: {language} | Updated: {updated}\n"
                    f"   {description}\n"
                    f"   {url}\n"
                )
            
            summary = f"GitHub repository search results for '{query}':\n\n" + "\n".join(results)
            logger.info(f"🔍 GitHub Repo Search: Found {len(repositories)} repositories")
            return summary
            
        except requests.exceptions.RequestException as e:
            logger.error(f"🔍 GitHub Repo Search API error: {e}")
            return f"GitHub API error: {str(e)}"
        except Exception as e:
            logger.error(f"🔍 GitHub Repo Search error: {e}")
            return f"GitHub repository search failed: {str(e)}"

    async def _arun(self, query: str, language: Optional[str] = None, max_results: int = 5) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, query, language, max_results)

class LangchainGitHubIssuesTool(LangchainBaseTool):
    name: str = "search_github_issues"
    description: str = "Searches for issues in a specific GitHub repository. Useful for finding bugs, feature requests, or project status."
    args_schema: Type[BaseModel] = GitHubIssueSearchSchema

    def _run(self, repository: str, state: str = "open", max_results: int = 5) -> str:
        logger.info(f"📋 GitHub Issues Search: repo='{repository}', state='{state}', max_results={max_results}")
        try:
            # Validate repository format
            if "/" not in repository:
                return "Repository must be in format 'owner/repo' (e.g., 'facebook/react')"
            
            # Limit max_results
            max_results = min(max_results, GITHUB_SEARCH_MAX_RESULTS)
            
            # Prepare headers
            headers = {"Accept": "application/vnd.github.v3+json"}
            if GITHUB_TOKEN:
                headers["Authorization"] = f"token {GITHUB_TOKEN}"
            
            # Make API request
            url = f"{GITHUB_API_BASE}/repos/{repository}/issues"
            params = {
                "state": state,
                "per_page": max_results,
                "sort": "updated",
                "direction": "desc"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            issues = response.json()
            
            if not issues:
                return f"No {state} issues found in repository: {repository}"
            
            # Format results
            results = []
            for i, issue in enumerate(issues, 1):
                number = issue.get("number", "Unknown")
                title = issue.get("title", "No title")
                state_emoji = "🟢" if issue.get("state") == "open" else "🔴"
                labels = [label.get("name", "") for label in issue.get("labels", [])]
                labels_str = f"[{', '.join(labels[:3])}]" if labels else ""
                url = issue.get("html_url", "")
                updated = issue.get("updated_at", "").split("T")[0] if issue.get("updated_at") else "Unknown"
                
                # Check if it's a pull request
                is_pr = issue.get("pull_request") is not None
                type_indicator = "🔀 PR" if is_pr else "📋 Issue"
                
                results.append(
                    f"{i}. {state_emoji} {type_indicator} #{number}: {title}\n"
                    f"   {labels_str} | Updated: {updated}\n"
                    f"   {url}\n"
                )
            
            summary = f"GitHub {state} issues/PRs for {repository}:\n\n" + "\n".join(results)
            logger.info(f"📋 GitHub Issues Search: Found {len(issues)} issues")
            return summary
            
        except requests.exceptions.RequestException as e:
            logger.error(f"📋 GitHub Issues API error: {e}")
            return f"GitHub API error: {str(e)}"
        except Exception as e:
            logger.error(f"📋 GitHub Issues error: {e}")
            return f"GitHub issues search failed: {str(e)}"

    async def _arun(self, repository: str, state: str = "open", max_results: int = 5) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, repository, state, max_results)

class LangchainGitHubReleasesTool(LangchainBaseTool):
    name: str = "get_github_releases"
    description: str = "Gets recent releases and version information for a GitHub repository. Useful for tracking updates and changelog."
    args_schema: Type[BaseModel] = GitHubReleaseSchema

    def _run(self, repository: str, max_results: int = 5) -> str:
        logger.info(f"🚀 GitHub Releases: repo='{repository}', max_results={max_results}")
        try:
            # Validate repository format
            if "/" not in repository:
                return "Repository must be in format 'owner/repo' (e.g., 'flutter/flutter')"
            
            # Limit max_results
            max_results = min(max_results, GITHUB_SEARCH_MAX_RESULTS)
            
            # Prepare headers
            headers = {"Accept": "application/vnd.github.v3+json"}
            if GITHUB_TOKEN:
                headers["Authorization"] = f"token {GITHUB_TOKEN}"
            
            # Make API request
            url = f"{GITHUB_API_BASE}/repos/{repository}/releases"
            params = {"per_page": max_results}
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            releases = response.json()
            
            if not releases:
                return f"No releases found for repository: {repository}"
            
            # Format results
            results = []
            for i, release in enumerate(releases, 1):
                tag_name = release.get("tag_name", "Unknown")
                name = release.get("name", tag_name)
                published = release.get("published_at", "").split("T")[0] if release.get("published_at") else "Unknown"
                prerelease = "🔄 Pre-release" if release.get("prerelease") else "✅ Stable"
                draft = " (Draft)" if release.get("draft") else ""
                url = release.get("html_url", "")
                
                # Get body preview (first 150 chars)
                body = release.get("body", "No release notes")
                body_preview = body[:150] + "..." if len(body) > 150 else body
                
                results.append(
                    f"{i}. **{name}** ({tag_name}) {prerelease}{draft}\n"
                    f"   Published: {published}\n"
                    f"   {body_preview}\n"
                    f"   {url}\n"
                )
            
            summary = f"GitHub releases for {repository}:\n\n" + "\n".join(results)
            logger.info(f"🚀 GitHub Releases: Found {len(releases)} releases")
            return summary
            
        except requests.exceptions.RequestException as e:
            logger.error(f"🚀 GitHub Releases API error: {e}")
            return f"GitHub API error: {str(e)}"
        except Exception as e:
            logger.error(f"🚀 GitHub Releases error: {e}")
            return f"GitHub releases search failed: {str(e)}"

    async def _arun(self, repository: str, max_results: int = 5) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, repository, max_results)

# ===== REPOSITORY ANALYSIS TOOLS =====

class LangchainRepoExploreTool(LangchainBaseTool):
    name: str = "explore_repository_structure"
    description: str = "Explores and analyzes the structure of a repository or directory. Shows file tree, identifies project type, and provides overview."
    args_schema: Type[BaseModel] = RepoExploreSchema

    def _run(self, directory: str = ".", max_depth: int = 3, include_files: bool = True) -> str:
        logger.info(f"📁 Repo Explorer: directory='{directory}', max_depth={max_depth}")
        try:
            import os
            from pathlib import Path
            
            path = Path(directory).resolve()
            if not path.exists():
                return f"Directory does not exist: {directory}"
            
            # Analyze project type
            project_type = self._detect_project_type(path)
            
            # Generate file tree
            tree_output = self._generate_tree(path, max_depth, include_files)
            
            # Get basic stats
            stats = self._get_directory_stats(path, max_depth)
            
            result = f"📁 Repository Structure Analysis for: {path.name}\n"
            result += f"📂 Path: {path}\n"
            result += f"🏷️ Project Type: {project_type}\n\n"
            result += f"📊 Statistics:\n"
            result += f"   • Total directories: {stats['dirs']}\n"
            result += f"   • Total files: {stats['files']}\n"
            result += f"   • Primary languages: {', '.join(stats['languages'][:3])}\n\n"
            result += f"🌳 Directory Structure:\n{tree_output}"
            
            return result
            
        except Exception as e:
            logger.error(f"📁 Repo Explorer error: {e}")
            return f"Repository exploration failed: {str(e)}"
    
    def _detect_project_type(self, path: Path) -> str:
        """Detect the type of project based on files present"""
        project_indicators = {
            "Flutter/Dart": ["pubspec.yaml", "lib/main.dart"],
            "Node.js": ["package.json", "node_modules"],
            "Python": ["requirements.txt", "setup.py", "pyproject.toml", "__pycache__"],
            "React": ["package.json", "src/App.js", "src/App.tsx"],
            "Next.js": ["next.config.js", "pages", "app"],
            "Vue.js": ["vue.config.js", "src/App.vue"],
            "Django": ["manage.py", "settings.py"],
            "FastAPI": ["main.py", "requirements.txt"],
            "Go": ["go.mod", "main.go"],
            "Rust": ["Cargo.toml", "src/main.rs"],
            "Java": ["pom.xml", "build.gradle"],
            "C++": ["CMakeLists.txt", "Makefile"],
            "Git Repository": [".git"]
        }
        
        detected_types = []
        for project_type, indicators in project_indicators.items():
            if any((path / indicator).exists() for indicator in indicators):
                detected_types.append(project_type)
        
        return ", ".join(detected_types) if detected_types else "Unknown"
    
    def _generate_tree(self, path: Path, max_depth: int, include_files: bool, current_depth: int = 0, gitignore_patterns: set = None) -> str:
        """Generate a tree structure representation"""
        if current_depth >= max_depth:
            return ""
        
        # Load gitignore patterns on first call
        if gitignore_patterns is None:
            gitignore_patterns = self._load_gitignore_patterns(path)
        
        items = []
        ignore_patterns = {'.git', '.idea', '__pycache__', 'node_modules', '.flutter-plugins-dependencies', 'build'}
        
        try:
            for item in sorted(path.iterdir()):
                if item.name.startswith('.') and item.name not in {'.git', '.github', '.gitignore'}:
                    continue
                if item.name in ignore_patterns:
                    continue
                
                # Check gitignore patterns
                relative_path = str(item.relative_to(path))
                if self._is_ignored_by_gitignore(relative_path, gitignore_patterns, item.is_dir()):
                    continue
                
                indent = "  " * current_depth
                if item.is_dir():
                    items.append(f"{indent}📁 {item.name}/")
                    if current_depth < max_depth - 1:
                        subtree = self._generate_tree(item, max_depth, include_files, current_depth + 1, gitignore_patterns)
                        if subtree:
                            items.append(subtree)
                elif include_files and current_depth < max_depth - 1:
                    icon = self._get_file_icon(item.suffix)
                    items.append(f"{indent}{icon} {item.name}")
        except PermissionError:
            items.append(f"{'  ' * current_depth}❌ Permission denied")
        
        return "\n".join(items)
    
    def _get_file_icon(self, suffix: str) -> str:
        """Get emoji icon for file type"""
        icons = {
            '.py': '🐍', '.js': '📜', '.ts': '📘', '.dart': '🎯',
            '.java': '☕', '.cpp': '⚡', '.c': '⚡', '.go': '🐹',
            '.rs': '🦀', '.php': '🐘', '.rb': '💎', '.swift': '🦉',
            '.html': '🌐', '.css': '🎨', '.json': '📋', '.xml': '📄',
            '.md': '📝', '.txt': '📃', '.yaml': '⚙️', '.yml': '⚙️',
            '.lock': '🔒', '.gitignore': '🚫'
        }
        return icons.get(suffix.lower(), '📄')
    
    def _load_gitignore_patterns(self, repo_path: Path) -> set:
        """Load and parse .gitignore patterns from the repository"""
        patterns = set()
        gitignore_file = repo_path / '.gitignore'
        
        if gitignore_file.exists():
            try:
                with open(gitignore_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Remove leading slash if present
                            if line.startswith('/'):
                                line = line[1:]
                            patterns.add(line)
            except Exception:
                pass  # Ignore errors reading .gitignore
        
        return patterns
    
    def _is_ignored_by_gitignore(self, path: str, patterns: set, is_dir: bool) -> bool:
        """Check if a path should be ignored based on gitignore patterns"""
        if not patterns:
            return False
        
        # Normalize path separators
        path = path.replace('\\', '/')
        
        for pattern in patterns:
            if self._matches_gitignore_pattern(path, pattern, is_dir):
                return True
        
        return False
    
    def _matches_gitignore_pattern(self, path: str, pattern: str, is_dir: bool) -> bool:
        """Check if a path matches a gitignore pattern"""
        import fnmatch
        
        # Handle directory-only patterns (ending with /)
        if pattern.endswith('/'):
            if not is_dir:
                return False
            pattern = pattern[:-1]
        
        # Handle patterns with wildcards
        if '*' in pattern or '?' in pattern or '[' in pattern:
            # For wildcard patterns, check both the full path and just the filename
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.split('/')[-1], pattern):
                return True
        else:
            # For exact patterns, check if path matches exactly or ends with the pattern
            if path == pattern or path.endswith('/' + pattern) or path.split('/')[-1] == pattern:
                return True
        
        return False
    
    def _get_directory_stats(self, path: Path, max_depth: int) -> dict:
        """Get basic statistics about the directory"""
        stats = {'dirs': 0, 'files': 0, 'languages': []}
        language_count = {}
        gitignore_patterns = self._load_gitignore_patterns(path)
        
        def count_recursive(current_path: Path, depth: int):
            if depth >= max_depth:
                return
            
            try:
                for item in current_path.iterdir():
                    if item.name.startswith('.') or item.name in {'node_modules', '__pycache__', 'build'}:
                        continue
                    
                    # Check gitignore patterns
                    relative_path = str(item.relative_to(path))
                    if self._is_ignored_by_gitignore(relative_path, gitignore_patterns, item.is_dir()):
                        continue
                    
                    if item.is_dir():
                        stats['dirs'] += 1
                        count_recursive(item, depth + 1)
                    else:
                        stats['files'] += 1
                        suffix = item.suffix.lower()
                        if suffix:
                            language_count[suffix] = language_count.get(suffix, 0) + 1
            except PermissionError:
                pass
        
        count_recursive(path, 0)
        
        # Convert file extensions to languages
        ext_to_lang = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
            '.dart': 'Dart', '.java': 'Java', '.cpp': 'C++', '.c': 'C',
            '.go': 'Go', '.rs': 'Rust', '.php': 'PHP', '.rb': 'Ruby'
        }
        
        for ext, count in sorted(language_count.items(), key=lambda x: x[1], reverse=True):
            lang = ext_to_lang.get(ext, ext.upper().replace('.', ''))
            stats['languages'].append(f"{lang} ({count})")
        
        return stats

    async def _arun(self, directory: str = ".", max_depth: int = 3, include_files: bool = True) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory, max_depth, include_files)

class LangchainDependencyAnalysisTool(LangchainBaseTool):
    name: str = "analyze_project_dependencies"
    description: str = "Analyzes project dependencies from package files (package.json, pubspec.yaml, requirements.txt, etc.). Shows versions, vulnerabilities, and suggestions."
    args_schema: Type[BaseModel] = DependencyAnalysisSchema

    def _run(self, directory: str = ".", file_types: Optional[str] = None) -> str:
        logger.info(f"📦 Dependency Analyzer: directory='{directory}', types='{file_types}'")
        try:
            from pathlib import Path
            import json
            import yaml
            
            path = Path(directory).resolve()
            if not path.exists():
                return f"Directory does not exist: {directory}"
            
            # Define dependency files to analyze
            dep_files = {
                'package.json': self._analyze_npm_deps,
                'pubspec.yaml': self._analyze_flutter_deps,
                'requirements.txt': self._analyze_python_deps,
                'Pipfile': self._analyze_pipenv_deps,
                'Cargo.toml': self._analyze_rust_deps,
                'go.mod': self._analyze_go_deps,
                'pom.xml': self._analyze_maven_deps
            }
            
            # Filter by requested file types
            if file_types:
                requested_types = [t.strip() for t in file_types.split(',')]
                dep_files = {k: v for k, v in dep_files.items() if k in requested_types}
            
            results = []
            found_files = []
            
            for filename, analyzer in dep_files.items():
                file_path = path / filename
                if file_path.exists():
                    found_files.append(filename)
                    try:
                        analysis = analyzer(file_path)
                        results.append(f"📦 {filename}:\n{analysis}")
                    except Exception as e:
                        results.append(f"❌ {filename}: Error analyzing - {str(e)}")
            
            if not results:
                available_files = [f for f in dep_files.keys() if (path / f).exists()]
                if available_files:
                    return f"No dependency files found matching criteria. Available files: {', '.join(available_files)}"
                return "No dependency files found in directory"
            
            summary = f"🔍 Dependency Analysis for: {path.name}\n"
            summary += f"📂 Analyzed files: {', '.join(found_files)}\n\n"
            summary += "\n\n".join(results)
            
            return summary
            
        except Exception as e:
            logger.error(f"📦 Dependency Analyzer error: {e}")
            return f"Dependency analysis failed: {str(e)}"
    
    def _analyze_npm_deps(self, file_path: Path) -> str:
        """Analyze Node.js package.json dependencies"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            deps = data.get('dependencies', {})
            dev_deps = data.get('devDependencies', {})
            
            result = f"   Dependencies: {len(deps)}, DevDependencies: {len(dev_deps)}\n"
            
            if deps:
                result += "   🔗 Main Dependencies:\n"
                for name, version in list(deps.items())[:5]:
                    result += f"     • {name}: {version}\n"
                if len(deps) > 5:
                    result += f"     ... and {len(deps) - 5} more\n"
            
            if dev_deps:
                result += "   🛠️ Dev Dependencies:\n"
                for name, version in list(dev_deps.items())[:3]:
                    result += f"     • {name}: {version}\n"
                if len(dev_deps) > 3:
                    result += f"     ... and {len(dev_deps) - 3} more\n"
            
            return result
            
        except Exception as e:
            return f"Error reading package.json: {str(e)}"
    
    def _analyze_flutter_deps(self, file_path: Path) -> str:
        """Analyze Flutter pubspec.yaml dependencies"""
        try:
            import yaml
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
            
            deps = data.get('dependencies', {})
            dev_deps = data.get('dev_dependencies', {})
            
            # Remove flutter SDK dependency from count
            main_deps = {k: v for k, v in deps.items() if k != 'flutter'}
            
            result = f"   Dependencies: {len(main_deps)}, DevDependencies: {len(dev_deps)}\n"
            result += f"   Flutter SDK: {deps.get('flutter', 'Not specified')}\n"
            
            if main_deps:
                result += "   📱 Main Dependencies:\n"
                for name, version in list(main_deps.items())[:5]:
                    result += f"     • {name}: {version if version else 'any'}\n"
                if len(main_deps) > 5:
                    result += f"     ... and {len(main_deps) - 5} more\n"
            
            if dev_deps:
                result += "   🛠️ Dev Dependencies:\n"
                for name, version in list(dev_deps.items())[:3]:
                    result += f"     • {name}: {version if version else 'any'}\n"
                if len(dev_deps) > 3:
                    result += f"     ... and {len(dev_deps) - 3} more\n"
            
            return result
            
        except Exception as e:
            return f"Error reading pubspec.yaml: {str(e)}"
    
    def _analyze_python_deps(self, file_path: Path) -> str:
        """Analyze Python requirements.txt dependencies"""
        try:
            with open(file_path, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            deps = []
            for line in lines:
                if '==' in line or '>=' in line or '<=' in line:
                    deps.append(line)
                elif line:
                    deps.append(line)
            
            result = f"   Requirements: {len(deps)}\n"
            
            if deps:
                result += "   🐍 Python Dependencies:\n"
                for dep in deps[:8]:
                    result += f"     • {dep}\n"
                if len(deps) > 8:
                    result += f"     ... and {len(deps) - 8} more\n"
            
            return result
            
        except Exception as e:
            return f"Error reading requirements.txt: {str(e)}"
    
    def _analyze_pipenv_deps(self, file_path: Path) -> str:
        """Analyze Python Pipfile dependencies"""
        return "   Pipfile analysis not implemented yet"
    
    def _analyze_rust_deps(self, file_path: Path) -> str:
        """Analyze Rust Cargo.toml dependencies"""
        return "   Cargo.toml analysis not implemented yet"
    
    def _analyze_go_deps(self, file_path: Path) -> str:
        """Analyze Go go.mod dependencies"""
        return "   go.mod analysis not implemented yet"
    
    def _analyze_maven_deps(self, file_path: Path) -> str:
        """Analyze Java pom.xml dependencies"""
        return "   pom.xml analysis not implemented yet"

    async def _arun(self, directory: str = ".", file_types: Optional[str] = None) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory, file_types)

class LangchainCodeMetricsTool(LangchainBaseTool):
    name: str = "analyze_code_metrics"
    description: str = "Analyzes code metrics including lines of code, complexity, and language distribution. Provides project health insights."
    args_schema: Type[BaseModel] = CodeMetricsSchema

    def _run(self, directory: str = ".", language: Optional[str] = None) -> str:
        logger.info(f"📊 Code Metrics: directory='{directory}', language='{language}'")
        try:
            from pathlib import Path
            
            path = Path(directory).resolve()
            if not path.exists():
                return f"Directory does not exist: {directory}"
            
            metrics = self._calculate_metrics(path, language)
            
            result = f"📊 Code Metrics for: {path.name}\n\n"
            result += f"📈 Overview:\n"
            result += f"   • Total files analyzed: {metrics['total_files']}\n"
            result += f"   • Total lines of code: {metrics['total_lines']:,}\n"
            result += f"   • Non-empty lines: {metrics['code_lines']:,}\n"
            result += f"   • Comment lines: {metrics['comment_lines']:,}\n"
            result += f"   • Average file size: {metrics['avg_file_size']:.1f} lines\n\n"
            
            if metrics['languages']:
                result += "🗂️ Language Distribution:\n"
                for lang, stats in metrics['languages'].items():
                    percentage = (stats['lines'] / metrics['total_lines'] * 100) if metrics['total_lines'] > 0 else 0
                    result += f"   • {lang}: {stats['files']} files, {stats['lines']:,} lines ({percentage:.1f}%)\n"
                result += "\n"
            
            if metrics['largest_files']:
                result += "📄 Largest Files:\n"
                for file_info in metrics['largest_files'][:5]:
                    result += f"   • {file_info['name']}: {file_info['lines']:,} lines\n"
                result += "\n"
            
            result += f"🎯 Insights:\n"
            result += self._generate_insights(metrics)
            
            return result
            
        except Exception as e:
            logger.error(f"📊 Code Metrics error: {e}")
            return f"Code metrics analysis failed: {str(e)}"
    
    def _calculate_metrics(self, path: Path, target_language: Optional[str]) -> dict:
        """Calculate comprehensive code metrics"""
        metrics = {
            'total_files': 0,
            'total_lines': 0,
            'code_lines': 0,
            'comment_lines': 0,
            'avg_file_size': 0,
            'languages': {},
            'largest_files': []
        }
        
        # Load gitignore patterns for this repository
        gitignore_patterns = self._load_gitignore_patterns(path)
        
        # File extension to language mapping
        ext_to_lang = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
            '.dart': 'Dart', '.java': 'Java', '.cpp': 'C++', '.c': 'C',
            '.go': 'Go', '.rs': 'Rust', '.php': 'PHP', '.rb': 'Ruby',
            '.swift': 'Swift', '.kt': 'Kotlin', '.scala': 'Scala',
            '.html': 'HTML', '.css': 'CSS', '.scss': 'SCSS',
            '.vue': 'Vue', '.jsx': 'JSX', '.tsx': 'TSX'
        }
        
        # Comment patterns for different languages
        comment_patterns = {
            'Python': ['#'], 'JavaScript': ['//', '/*'], 'TypeScript': ['//', '/*'],
            'Dart': ['//', '/*'], 'Java': ['//', '/*'], 'C++': ['//', '/*'],
            'C': ['//', '/*'], 'Go': ['//', '/*'], 'Rust': ['//', '/*'],
            'PHP': ['//', '/*', '#'], 'Ruby': ['#'], 'Swift': ['//', '/*'],
            'HTML': ['<!--'], 'CSS': ['/*'], 'SCSS': ['//', '/*']
        }
        
        ignore_dirs = {'.git', '__pycache__', 'node_modules', 'build', '.idea', 'target', 'dist'}
        
        def analyze_file(file_path: Path) -> dict:
            """Analyze a single file for metrics"""
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                total_lines = len(lines)
                code_lines = 0
                comment_lines = 0
                
                ext = file_path.suffix.lower()
                language = ext_to_lang.get(ext, 'Other')
                patterns = comment_patterns.get(language, [])
                
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    
                    is_comment = any(stripped.startswith(pattern) for pattern in patterns)
                    if is_comment:
                        comment_lines += 1
                    else:
                        code_lines += 1
                
                return {
                    'total_lines': total_lines,
                    'code_lines': code_lines,
                    'comment_lines': comment_lines,
                    'language': language
                }
                
            except Exception:
                return None
        
        def walk_directory(current_path: Path, depth: int = 0):
            """Recursively walk directory and analyze files"""
            if depth > 10:  # Prevent excessive recursion
                return
                
            try:
                for item in current_path.iterdir():
                    if item.name.startswith('.') and item.name not in {'.github'}:
                        continue
                    if item.name in ignore_dirs:
                        continue
                    
                    # Check gitignore patterns
                    relative_path = str(item.relative_to(path))
                    if self._is_ignored_by_gitignore(relative_path, gitignore_patterns, item.is_dir()):
                        continue
                    
                    if item.is_dir():
                        walk_directory(item, depth + 1)
                    elif item.is_file():
                        ext = item.suffix.lower()
                        if not ext or ext in {'.pyc', '.class', '.o', '.so', '.dll'}:
                            continue
                        
                        # Filter by target language if specified
                        if target_language:
                            lang = ext_to_lang.get(ext, 'Other')
                            if lang.lower() != target_language.lower():
                                continue
                        
                        file_metrics = analyze_file(item)
                        if file_metrics:
                            metrics['total_files'] += 1
                            metrics['total_lines'] += file_metrics['total_lines']
                            metrics['code_lines'] += file_metrics['code_lines']
                            metrics['comment_lines'] += file_metrics['comment_lines']
                            
                            # Track by language
                            lang = file_metrics['language']
                            if lang not in metrics['languages']:
                                metrics['languages'][lang] = {'files': 0, 'lines': 0}
                            metrics['languages'][lang]['files'] += 1
                            metrics['languages'][lang]['lines'] += file_metrics['total_lines']
                            
                            # Track largest files
                            metrics['largest_files'].append({
                                'name': str(item.relative_to(path)),
                                'lines': file_metrics['total_lines']
                            })
                            
            except PermissionError:
                pass
        
        walk_directory(path)
        
        # Sort largest files and keep top 10
        metrics['largest_files'].sort(key=lambda x: x['lines'], reverse=True)
        metrics['largest_files'] = metrics['largest_files'][:10]
        
        # Calculate average file size
        if metrics['total_files'] > 0:
            metrics['avg_file_size'] = metrics['total_lines'] / metrics['total_files']
        
        return metrics
    
    def _generate_insights(self, metrics: dict) -> str:
        """Generate insights based on metrics"""
        insights = []
        
        # File size insights
        if metrics['avg_file_size'] > 500:
            insights.append("   • Large average file size - consider breaking down complex files")
        elif metrics['avg_file_size'] < 50:
            insights.append("   • Small average file size - good modular structure")
        
        # Comment ratio insights
        if metrics['total_lines'] > 0:
            comment_ratio = metrics['comment_lines'] / metrics['total_lines']
            if comment_ratio < 0.1:
                insights.append("   • Low comment ratio - consider adding more documentation")
            elif comment_ratio > 0.3:
                insights.append("   • High comment ratio - well documented codebase")
        
        # Language diversity insights
        if len(metrics['languages']) > 5:
            insights.append("   • Multi-language project - ensure consistent practices across languages")
        
        # Size category
        if metrics['total_lines'] > 100000:
            insights.append("   • Large codebase - consider using automated tools for maintenance")
        elif metrics['total_lines'] < 1000:
            insights.append("   • Small project - good for rapid development")
        
        return "\n".join(insights) if insights else "   • Code metrics look standard for this project size"
    
    def _load_gitignore_patterns(self, repo_path: Path) -> set:
        """Load and parse .gitignore patterns from the repository"""
        patterns = set()
        gitignore_file = repo_path / '.gitignore'
        
        if gitignore_file.exists():
            try:
                with open(gitignore_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Remove leading slash if present
                            if line.startswith('/'):
                                line = line[1:]
                            patterns.add(line)
            except Exception:
                pass  # Ignore errors reading .gitignore
        
        return patterns
    
    def _is_ignored_by_gitignore(self, path: str, patterns: set, is_dir: bool) -> bool:
        """Check if a path should be ignored based on gitignore patterns"""
        if not patterns:
            return False
        
        # Normalize path separators
        path = path.replace('\\', '/')
        
        for pattern in patterns:
            if self._matches_gitignore_pattern(path, pattern, is_dir):
                return True
        
        return False
    
    def _matches_gitignore_pattern(self, path: str, pattern: str, is_dir: bool) -> bool:
        """Check if a path matches a gitignore pattern"""
        import fnmatch
        
        # Handle directory-only patterns (ending with /)
        if pattern.endswith('/'):
            if not is_dir:
                return False
            pattern = pattern[:-1]
        
        # Handle patterns with wildcards
        if '*' in pattern or '?' in pattern or '[' in pattern:
            # For wildcard patterns, check both the full path and just the filename
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.split('/')[-1], pattern):
                return True
        else:
            # For exact patterns, check if path matches exactly or ends with the pattern
            if path == pattern or path.endswith('/' + pattern) or path.split('/')[-1] == pattern:
                return True
        
        return False

    async def _arun(self, directory: str = ".", language: Optional[str] = None) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory, language)

# ===== DEVELOPMENT HELPER TOOLS =====

class LangchainPackageSearchTool(LangchainBaseTool):
    name: str = "search_packages"
    description: str = "Searches for packages/libraries in various ecosystems (npm, pip, pub.dev, crates.io, etc.). Helps find dependencies and libraries for projects."
    args_schema: Type[BaseModel] = PackageSearchSchema

    def _run(self, query: str, language: str, max_results: int = 5) -> str:
        logger.info(f"📦 Package Search: query='{query}', language='{language}', max_results={max_results}")
        try:
            language_lower = language.lower()
            max_results = min(max_results, 10)  # Limit results
            
            # Route to appropriate package registry
            if language_lower in ["npm", "node", "javascript", "typescript", "js", "ts"]:
                return self._search_npm(query, max_results)
            elif language_lower in ["pip", "python", "py"]:
                return self._search_pypi(query, max_results)
            elif language_lower in ["pub", "dart", "flutter"]:
                return self._search_pub_dev(query, max_results)
            elif language_lower in ["cargo", "rust", "rs"]:
                return self._search_crates_io(query, max_results)
            elif language_lower in ["maven", "gradle", "java"]:
                return self._search_maven(query, max_results)
            else:
                return f"Package search not yet supported for '{language}'. Supported: npm, pip, pub, cargo, maven"
                
        except Exception as e:
            logger.error(f"📦 Package Search error: {e}")
            return f"Package search failed: {str(e)}"
    
    def _search_npm(self, query: str, max_results: int) -> str:
        """Search npm registry"""
        try:
            import requests
            url = f"https://registry.npmjs.org/-/v1/search?text={query}&size={max_results}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            packages = data.get('objects', [])
            
            if not packages:
                return f"No npm packages found for: {query}"
            
            results = []
            for i, pkg_obj in enumerate(packages, 1):
                pkg = pkg_obj.get('package', {})
                name = pkg.get('name', 'Unknown')
                description = pkg.get('description', 'No description')
                version = pkg.get('version', 'Unknown')
                
                # Get additional metrics
                links = pkg.get('links', {})
                npm_url = links.get('npm', f"https://www.npmjs.com/package/{name}")
                
                results.append(
                    f"{i}. **{name}** v{version}\n"
                    f"   {description}\n"
                    f"   📦 {npm_url}\n"
                )
            
            return f"📦 NPM Package Search Results for '{query}':\n\n" + "\n".join(results)
            
        except Exception as e:
            return f"NPM search error: {str(e)}"
    
    def _search_pypi(self, query: str, max_results: int) -> str:
        """Search PyPI registry"""
        try:
            import requests
            url = f"https://pypi.org/pypi/{query}/json"
            
            # Try exact match first
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                info = data.get('info', {})
                name = info.get('name', 'Unknown')
                version = info.get('version', 'Unknown')
                summary = info.get('summary', 'No description')
                home_page = info.get('home_page', f"https://pypi.org/project/{name}/")
                
                return (
                    f"🐍 PyPI Package Found for '{query}':\n\n"
                    f"**{name}** v{version}\n"
                    f"{summary}\n"
                    f"📦 {home_page}\n"
                )
                
            except requests.exceptions.HTTPError:
                # If exact match fails, return guidance for search
                return (
                    f"🐍 PyPI exact match not found for '{query}'.\n\n"
                    f"💡 Try searching at: https://pypi.org/search/?q={query.replace(' ', '+')}\n"
                    f"Or use: `pip search {query}` (if available)\n"
                )
                
        except Exception as e:
            return f"PyPI search error: {str(e)}"
    
    def _search_pub_dev(self, query: str, max_results: int) -> str:
        """Search pub.dev registry"""
        try:
            import requests
            url = f"https://pub.dev/api/search?q={query}&page=1"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            packages = data.get('packages', [])
            
            if not packages:
                return f"No pub.dev packages found for: {query}"
            
            results = []
            for i, pkg in enumerate(packages[:max_results], 1):
                name = pkg.get('package', 'Unknown')
                description = pkg.get('description', 'No description')
                
                # Construct pub.dev URL
                pub_url = f"https://pub.dev/packages/{name}"
                
                results.append(
                    f"{i}. **{name}**\n"
                    f"   {description}\n"
                    f"   🎯 {pub_url}\n"
                )
            
            return f"🎯 Pub.dev Package Search Results for '{query}':\n\n" + "\n".join(results)
            
        except Exception as e:
            return f"Pub.dev search error: {str(e)}"
    
    def _search_crates_io(self, query: str, max_results: int) -> str:
        """Search crates.io registry"""
        try:
            import requests
            url = f"https://crates.io/api/v1/crates?q={query}&per_page={max_results}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            crates = data.get('crates', [])
            
            if not crates:
                return f"No crates.io packages found for: {query}"
            
            results = []
            for i, crate in enumerate(crates, 1):
                name = crate.get('name', 'Unknown')
                description = crate.get('description', 'No description')
                max_version = crate.get('max_version', 'Unknown')
                
                crates_url = f"https://crates.io/crates/{name}"
                
                results.append(
                    f"{i}. **{name}** v{max_version}\n"
                    f"   {description}\n"
                    f"   🦀 {crates_url}\n"
                )
            
            return f"🦀 Crates.io Package Search Results for '{query}':\n\n" + "\n".join(results)
            
        except Exception as e:
            return f"Crates.io search error: {str(e)}"
    
    def _search_maven(self, query: str, max_results: int) -> str:
        """Search Maven Central"""
        try:
            import requests
            url = f"https://search.maven.org/solrsearch/select?q={query}&rows={max_results}&wt=json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            docs = data.get('response', {}).get('docs', [])
            
            if not docs:
                return f"No Maven packages found for: {query}"
            
            results = []
            for i, doc in enumerate(docs, 1):
                group_id = doc.get('g', 'Unknown')
                artifact_id = doc.get('a', 'Unknown')
                version = doc.get('latestVersion', doc.get('v', 'Unknown'))
                
                maven_url = f"https://search.maven.org/artifact/{group_id}/{artifact_id}/{version}/jar"
                
                results.append(
                    f"{i}. **{group_id}:{artifact_id}** v{version}\n"
                    f"   ☕ {maven_url}\n"
                )
            
            return f"☕ Maven Central Search Results for '{query}':\n\n" + "\n".join(results)
            
        except Exception as e:
            return f"Maven search error: {str(e)}"

    async def _arun(self, query: str, language: str, max_results: int = 5) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, query, language, max_results)

class LangchainBuildCommandTool(LangchainBaseTool):
    name: str = "project_build_commands"
    description: str = "Detects and executes build commands for projects. Can detect common build systems and run build, test, lint, or format commands."
    args_schema: Type[BaseModel] = BuildCommandSchema

    def _run(self, directory: str = ".", action: str = "detect", command: Optional[str] = None) -> str:
        logger.info(f"🔨 Build Commands: directory='{directory}', action='{action}', command='{command}'")
        try:
            from pathlib import Path
            import subprocess
            
            path = Path(directory).resolve()
            if not path.exists():
                return f"Directory does not exist: {directory}"
            
            if action == "detect":
                return self._detect_build_system(path)
            elif action == "run" and command:
                return self._run_command(path, command)
            elif action in ["test", "lint", "format", "clean"]:
                return self._run_standard_command(path, action)
            else:
                return f"Invalid action '{action}'. Use: detect, run, test, lint, format, clean"
                
        except Exception as e:
            logger.error(f"🔨 Build Commands error: {e}")
            return f"Build command operation failed: {str(e)}"
    
    def _detect_build_system(self, path: Path) -> str:
        """Detect build system and suggest commands"""
        build_files = {
            'package.json': self._analyze_npm_scripts,
            'pubspec.yaml': self._analyze_flutter_commands,
            'requirements.txt': self._analyze_python_commands,
            'setup.py': self._analyze_python_commands,
            'Cargo.toml': self._analyze_rust_commands,
            'pom.xml': self._analyze_maven_commands,
            'build.gradle': self._analyze_gradle_commands,
            'Makefile': self._analyze_makefile_commands,
            'CMakeLists.txt': self._analyze_cmake_commands
        }
        
        detected_systems = []
        suggestions = []
        
        for filename, analyzer in build_files.items():
            file_path = path / filename
            if file_path.exists():
                system_info = analyzer(file_path)
                detected_systems.append(system_info['name'])
                suggestions.extend(system_info['commands'])
        
        if not detected_systems:
            return "❌ No build system detected. Common files not found: package.json, pubspec.yaml, requirements.txt, Cargo.toml, pom.xml, etc."
        
        result = f"🔨 Build System Detection for: {path.name}\n\n"
        result += f"📋 Detected Systems: {', '.join(detected_systems)}\n\n"
        result += "💡 Available Commands:\n"
        
        for cmd in suggestions[:10]:  # Limit to 10 commands
            result += f"   • {cmd}\n"
        
        return result
    
    def _analyze_npm_scripts(self, file_path: Path) -> dict:
        """Analyze package.json scripts"""
        try:
            import json
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            scripts = data.get('scripts', {})
            commands = []
            
            # Common npm commands
            base_commands = ["npm install", "npm run build", "npm test", "npm start"]
            commands.extend(base_commands)
            
            # Custom scripts
            for script_name in scripts.keys():
                commands.append(f"npm run {script_name}")
            
            return {'name': 'Node.js/npm', 'commands': commands}
            
        except:
            return {'name': 'Node.js/npm', 'commands': ["npm install", "npm run build", "npm test"]}
    
    def _analyze_flutter_commands(self, file_path: Path) -> dict:
        """Analyze Flutter project commands"""
        commands = [
            "flutter pub get",
            "flutter build apk",
            "flutter build web",
            "flutter test",
            "flutter analyze",
            "flutter run",
            "dart format .",
            "dart analyze"
        ]
        return {'name': 'Flutter/Dart', 'commands': commands}
    
    def _analyze_python_commands(self, file_path: Path) -> dict:
        """Analyze Python project commands"""
        commands = [
            "pip install -r requirements.txt",
            "python -m pytest",
            "python -m flake8",
            "python -m black .",
            "python setup.py install",
            "python -m mypy ."
        ]
        return {'name': 'Python', 'commands': commands}
    
    def _analyze_rust_commands(self, file_path: Path) -> dict:
        """Analyze Rust project commands"""
        commands = [
            "cargo build",
            "cargo build --release",
            "cargo test",
            "cargo check",
            "cargo fmt",
            "cargo clippy",
            "cargo run"
        ]
        return {'name': 'Rust/Cargo', 'commands': commands}
    
    def _analyze_maven_commands(self, file_path: Path) -> dict:
        """Analyze Maven project commands"""
        commands = [
            "mvn clean compile",
            "mvn test",
            "mvn package",
            "mvn install",
            "mvn clean",
            "mvn verify"
        ]
        return {'name': 'Java/Maven', 'commands': commands}
    
    def _analyze_gradle_commands(self, file_path: Path) -> dict:
        """Analyze Gradle project commands"""
        commands = [
            "./gradlew build",
            "./gradlew test",
            "./gradlew clean",
            "./gradlew assemble",
            "./gradlew check"
        ]
        return {'name': 'Java/Gradle', 'commands': commands}
    
    def _analyze_makefile_commands(self, file_path: Path) -> dict:
        """Analyze Makefile commands"""
        commands = [
            "make",
            "make clean",
            "make test",
            "make install",
            "make all"
        ]
        return {'name': 'Make', 'commands': commands}
    
    def _analyze_cmake_commands(self, file_path: Path) -> dict:
        """Analyze CMake project commands"""
        commands = [
            "mkdir build && cd build",
            "cmake ..",
            "make",
            "cmake --build .",
            "ctest"
        ]
        return {'name': 'CMake', 'commands': commands}
    
    def _run_command(self, path: Path, command: str) -> str:
        """Execute a specific command"""
        try:
            import subprocess
            import shlex
            
            # Security: basic command validation
            dangerous_commands = ['rm -rf', 'del', 'format', 'shutdown', 'reboot']
            if any(dangerous in command.lower() for dangerous in dangerous_commands):
                return f"❌ Command blocked for security: {command}"
            
            result = subprocess.run(
                shlex.split(command),
                cwd=path,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            output = f"🔨 Command: {command}\n"
            output += f"📂 Directory: {path}\n"
            output += f"🔄 Exit Code: {result.returncode}\n\n"
            
            if result.stdout:
                output += f"📝 Output:\n{result.stdout}\n"
            
            if result.stderr:
                output += f"❌ Errors:\n{result.stderr}\n"
            
            if result.returncode == 0:
                output += "✅ Command completed successfully"
            else:
                output += "❌ Command failed"
            
            return output
            
        except subprocess.TimeoutExpired:
            return f"⏰ Command timed out after 2 minutes: {command}"
        except Exception as e:
            return f"❌ Command execution error: {str(e)}"
    
    def _run_standard_command(self, path: Path, action: str) -> str:
        """Run standard commands based on detected build system"""
        # Auto-detect and run appropriate command
        if (path / 'package.json').exists():
            commands = {
                'test': 'npm test',
                'lint': 'npm run lint',
                'format': 'npm run format',
                'clean': 'npm run clean'
            }
        elif (path / 'pubspec.yaml').exists():
            commands = {
                'test': 'flutter test',
                'lint': 'flutter analyze',
                'format': 'dart format .',
                'clean': 'flutter clean'
            }
        elif (path / 'Cargo.toml').exists():
            commands = {
                'test': 'cargo test',
                'lint': 'cargo clippy',
                'format': 'cargo fmt',
                'clean': 'cargo clean'
            }
        else:
            return f"❌ Cannot determine appropriate {action} command for this project type"
        
        command = commands.get(action)
        if not command:
            return f"❌ {action} command not available for this project type"
        
        return self._run_command(path, command)

    async def _arun(self, directory: str = ".", action: str = "detect", command: Optional[str] = None) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, directory, action, command)

# ===== EXISTING RAG TOOL =====

class QueryFlutterDocsSchema(BaseModel):
    query: str = Field(description="The technical question about Flutter or Dart for documentation lookup.")

class LangchainFlutterDocTool(LangchainBaseTool):
    name: str = "query_flutter_dart_documentation"
    description: str = "Queries a knowledge base of Flutter/Dart documentation to answer technical questions about Flutter or Dart. Use this for specific Flutter/Dart coding questions, error explanations, or finding documentation."
    args_schema: Type[BaseModel] = QueryFlutterDocsSchema

    def _run(self, query: str) -> str:
        logger.info(f"📚 RAG Tool: Received query: '{query}'")
        try:
            import requests
            response = requests.post(RAG_SERVER_ENDPOINT, params={"query": query, "limit": 5}, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            try:
                rag_json = response.json()
                if isinstance(rag_json, dict) and "results" in rag_json:
                    # Handle dual endpoint server response format
                    results = rag_json["results"]
                    if results:
                        result_text = f"📚 **Flutter/Dart Documentation Results** (Database: {rag_json.get('database', 'unknown')})\n\n"
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
            logger.info(f"📚 RAG Tool: Successfully retrieved documentation (length: {len(result_text)}).")
            return f"Documentation found for query '{query}':\n{result_text}"
        except Exception as e:
            logger.error(f"📚 RAG Tool: Error: {e}", exc_info=DEBUG_VERBOSE)
            return f"Error during RAG tool execution: {str(e)}"

    async def _arun(self, query: str) -> str:
        global executor
        if not executor: return "Error: Server config issue (executor missing)."
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, query)

# ===== ORCHESTRATOR LOGIC =====

# ===== SEQUENTIAL WORKFLOW ENGINE =====

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from enum import Enum

class StepStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class StepResult:
    """Result of a workflow step execution"""
    status: StepStatus
    data: Dict[str, Any]
    message: str
    next_step_recommendations: Optional[List[str]] = None
    should_stop_workflow: bool = False
    
    def is_success(self) -> bool:
        return self.status == StepStatus.COMPLETED
    
    def has_issues(self) -> bool:
        return self.data.get('issues_found', False) or self.data.get('errors', [])

class WorkflowStep(ABC):
    """Abstract base class for workflow steps"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = StepStatus.PENDING
        
    @abstractmethod
    async def execute(self, context: Dict[str, Any], previous_results: List[StepResult]) -> StepResult:
        """Execute the workflow step"""
        pass
    
    def should_skip(self, context: Dict[str, Any], previous_results: List[StepResult]) -> bool:
        """Determine if this step should be skipped based on context/previous results"""
        return False

class WorkflowEngine:
    """Manages sequential execution of workflow steps"""
    
    def __init__(self, workflow_name: str):
        self.workflow_name = workflow_name
        self.steps: List[WorkflowStep] = []
        self.execution_log: List[Dict[str, Any]] = []
        
    def add_step(self, step: WorkflowStep):
        """Add a step to the workflow"""
        self.steps.append(step)
        
    async def execute(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow sequentially"""
        logger.info(f"🔄 Starting workflow: {self.workflow_name}")
        
        context = initial_context.copy()
        step_results: List[StepResult] = []
        
        for i, step in enumerate(self.steps, 1):
            logger.info(f"📋 Step {i}/{len(self.steps)}: {step.name}")
            
            # Check if step should be skipped
            if step.should_skip(context, step_results):
                logger.info(f"⏭️ Skipping step: {step.name}")
                step.status = StepStatus.SKIPPED
                continue
                
            # Execute step
            step.status = StepStatus.IN_PROGRESS
            try:
                result = await step.execute(context, step_results)
                step.status = result.status
                step_results.append(result)
                
                # Log step execution
                self.execution_log.append({
                    "step_number": i,
                    "step_name": step.name,
                    "status": result.status.value,
                    "message": result.message,
                    "data_keys": list(result.data.keys()) if result.data else []
                })
                
                logger.info(f"✅ Step {i} completed: {result.message}")
                
                # Update context with step results
                context[f"step_{i}_result"] = result.data
                context["last_result"] = result.data
                
                # Check if workflow should stop early
                if result.should_stop_workflow:
                    logger.info(f"🛑 Workflow stopped early after step {i}: {result.message}")
                    break
                    
            except Exception as e:
                logger.error(f"❌ Step {i} failed: {str(e)}")
                step.status = StepStatus.FAILED
                step_results.append(StepResult(
                    status=StepStatus.FAILED,
                    data={"error": str(e)},
                    message=f"Step failed with error: {str(e)}"
                ))
                break
        
        # Generate final workflow result
        successful_steps = [r for r in step_results if r.is_success()]
        failed_steps = [r for r in step_results if r.status == StepStatus.FAILED]
        
        workflow_result = {
            "workflow_name": self.workflow_name,
            "total_steps": len(self.steps),
            "executed_steps": len(step_results),
            "successful_steps": len(successful_steps),
            "failed_steps": len(failed_steps),
            "execution_log": self.execution_log,
            "step_results": step_results,
            "final_context": context
        }
        
        logger.info(f"🏁 Workflow '{self.workflow_name}' completed: {len(successful_steps)}/{len(step_results)} steps successful")
        return workflow_result

# ===== CODE ANALYSIS WORKFLOW STEPS =====

class StaticAnalysisStep(WorkflowStep):
    """Step 1: Static code analysis using AutoLinter"""
    
    def __init__(self):
        super().__init__("Static Analysis", "Check for syntax issues, style violations, and obvious problems")
        
    async def execute(self, context: Dict[str, Any], previous_results: List[StepResult]) -> StepResult:
        code = context.get('code', '')
        if not code.strip():
            return StepResult(
                status=StepStatus.FAILED,
                data={"error": "No code provided"},
                message="No code found to analyze"
            )
        
        # Use AutoLinter tool
        linter_tool = LangchainAutoLinterTool()
        try:
            # Detect language from code or context
            language = context.get('language', 'auto')
            
            linter_result = await linter_tool._arun(
                code_content=code,
                language=language,
                auto_fix=False
            )
            
            # Parse linter results
            has_issues = "error" in linter_result.lower() or "warning" in linter_result.lower()
            
            return StepResult(
                status=StepStatus.COMPLETED,
                data={
                    "linter_output": linter_result,
                    "issues_found": has_issues,
                    "language_detected": language
                },
                message=f"Static analysis complete. Issues found: {has_issues}",
                next_step_recommendations=["focus_on_fixes"] if has_issues else ["proceed_to_architecture"]
            )
            
        except Exception as e:
            return StepResult(
                status=StepStatus.FAILED,
                data={"error": str(e)},
                message=f"Static analysis failed: {str(e)}"
            )

class CodeUnderstandingStep(WorkflowStep):
    """Step 2: Understand code patterns and best practices using RAG"""
    
    def __init__(self):
        super().__init__("Code Understanding", "Query documentation for relevant patterns and best practices")
        
    async def execute(self, context: Dict[str, Any], previous_results: List[StepResult]) -> StepResult:
        # Extract key information from code
        code = context.get('code', '')
        language = context.get('language', 'unknown')
        
        # Build RAG query based on detected patterns
        if 'flutter' in code.lower() or 'dart' in code.lower():
            query = f"Flutter Dart best practices for {self._extract_code_patterns(code)}"
        else:
            query = f"{language} best practices for {self._extract_code_patterns(code)}"
        
        # Use RAG tool
        rag_tool = LangchainFlutterDocTool()
        try:
            rag_result = await rag_tool._arun(query=query)
            
            return StepResult(
                status=StepStatus.COMPLETED,
                data={
                    "documentation_found": rag_result,
                    "query_used": query,
                    "patterns_detected": self._extract_code_patterns(code)
                },
                message="Code patterns analyzed and documentation retrieved",
                next_step_recommendations=["apply_best_practices"]
            )
            
        except Exception as e:
            return StepResult(
                status=StepStatus.COMPLETED,  # Non-critical failure
                data={
                    "error": str(e),
                    "fallback_analysis": "Using built-in knowledge"
                },
                message="RAG query failed, proceeding with built-in knowledge"
            )
    
    def _extract_code_patterns(self, code: str) -> str:
        """Extract key patterns from code for RAG query"""
        patterns = []
        code_lower = code.lower()
        
        if 'class' in code_lower and 'extends' in code_lower:
            patterns.append("class inheritance")
        if 'async' in code_lower or 'await' in code_lower:
            patterns.append("async programming")
        if 'visitor' in code_lower:
            patterns.append("visitor pattern")
        if 'factory' in code_lower:
            patterns.append("factory pattern")
            
        return " ".join(patterns) if patterns else "general code structure"

class ArchitectureReviewStep(WorkflowStep):
    """Step 3: Review architecture and dependencies"""
    
    def __init__(self):
        super().__init__("Architecture Review", "Analyze code structure and dependencies")
        
    async def execute(self, context: Dict[str, Any], previous_results: List[StepResult]) -> StepResult:
        code = context.get('code', '')
        
        # Use repository analysis tools if available
        repo_tool = LangchainRepoExploreTool()
        try:
            # Analyze code structure
            analysis_result = await repo_tool._arun(path=".", analysis_type="structure")
            
            return StepResult(
                status=StepStatus.COMPLETED,
                data={
                    "structure_analysis": analysis_result,
                    "architecture_assessment": self._assess_architecture(code)
                },
                message="Architecture analysis completed"
            )
            
        except Exception as e:
            # Fallback to basic analysis
            return StepResult(
                status=StepStatus.COMPLETED,
                data={
                    "basic_analysis": self._assess_architecture(code),
                    "detailed_analysis_failed": str(e)
                },
                message="Basic architecture analysis completed (detailed analysis failed)"
            )
    
    def _assess_architecture(self, code: str) -> Dict[str, Any]:
        """Basic architecture assessment"""
        assessment = {
            "complexity": "medium",
            "patterns_used": [],
            "potential_issues": []
        }
        
        # Count various metrics
        lines = code.split('\n')
        class_count = len([line for line in lines if 'class ' in line])
        method_count = len([line for line in lines if 'def ' in line or 'void ' in line])
        
        if class_count > 5:
            assessment["complexity"] = "high"
        elif class_count < 2:
            assessment["complexity"] = "low"
            
        if method_count > class_count * 10:
            assessment["potential_issues"].append("High method-to-class ratio")
            
        return assessment

class PerformanceAnalysisStep(WorkflowStep):
    """Step 4: Analyze performance and test functionality"""
    
    def __init__(self):
        super().__init__("Performance Analysis", "Test code execution and analyze performance")
        
    def should_skip(self, context: Dict[str, Any], previous_results: List[StepResult]) -> bool:
        # Skip if previous steps found critical syntax errors
        for result in previous_results:
            if result.data.get('issues_found') and 'syntax error' in result.message.lower():
                return True
        return False
        
    async def execute(self, context: Dict[str, Any], previous_results: List[StepResult]) -> StepResult:
        code = context.get('code', '')
        
        # Use sandbox for safe execution testing
        sandbox_tool = LangchainSandboxExecuteTool()
        try:
            # Create a simple test for the code
            test_result = await sandbox_tool._arun(
                code_to_run=self._create_basic_test(code),
                language="python"  # Default, should be detected
            )
            
            return StepResult(
                status=StepStatus.COMPLETED,
                data={
                    "execution_test": test_result,
                    "performance_metrics": self._extract_performance_metrics(test_result)
                },
                message="Performance analysis completed"
            )
            
        except Exception as e:
            return StepResult(
                status=StepStatus.COMPLETED,  # Non-critical
                data={
                    "execution_failed": str(e),
                    "static_performance_analysis": self._static_performance_analysis(code)
                },
                message="Dynamic testing failed, performed static analysis"
            )
    
    def _create_basic_test(self, code: str) -> str:
        """Create a basic test for the code"""
        return f"""
# Basic functionality test
{code}

# Test execution
try:
    print("Code compilation successful")
except Exception as e:
    print(f"Error: {{e}}")
"""
    
    def _extract_performance_metrics(self, test_result: str) -> Dict[str, Any]:
        """Extract basic performance metrics from test results"""
        return {
            "execution_successful": "error" not in test_result.lower(),
            "output_length": len(test_result),
            "contains_warnings": "warning" in test_result.lower()
        }
    
    def _static_performance_analysis(self, code: str) -> Dict[str, Any]:
        """Static performance analysis"""
        lines = code.split('\n')
        return {
            "total_lines": len(lines),
            "complexity_estimate": "high" if len(lines) > 200 else "medium" if len(lines) > 50 else "low",
            "nested_loops": code.count('for') + code.count('while'),
            "recursive_calls": "recursion" if "return " in code and any(func in code for func in ["def ", "function "]) else "none"
        }

class EnhancementStep(WorkflowStep):
    """Step 5: Suggest enhancements using memory and web search"""
    
    def __init__(self):
        super().__init__("Enhancement Suggestions", "Generate improvement recommendations")
        
    async def execute(self, context: Dict[str, Any], previous_results: List[StepResult]) -> StepResult:
        # Analyze all previous results to generate targeted enhancements
        enhancement_data = {
            "static_analysis_findings": [],
            "best_practice_suggestions": [],
            "architecture_improvements": [],
            "performance_optimizations": []
        }
        
        # Extract findings from previous steps
        for result in previous_results:
            if "linter_output" in result.data:
                enhancement_data["static_analysis_findings"].append(result.data["linter_output"])
            if "documentation_found" in result.data:
                enhancement_data["best_practice_suggestions"].append(result.data["documentation_found"])
            if "structure_analysis" in result.data:
                enhancement_data["architecture_improvements"].append(result.data["structure_analysis"])
            if "performance_metrics" in result.data:
                enhancement_data["performance_optimizations"].append(result.data["performance_metrics"])
        
        return StepResult(
            status=StepStatus.COMPLETED,
            data=enhancement_data,
            message="Enhancement analysis completed"
        )

class FinalReportStep(WorkflowStep):
    """Step 6: Generate comprehensive analysis report"""
    
    def __init__(self):
        super().__init__("Final Report", "Synthesize all findings into actionable recommendations")
        
    async def execute(self, context: Dict[str, Any], previous_results: List[StepResult]) -> StepResult:
        # Synthesize all previous results
        report_sections = {
            "executive_summary": "",
            "critical_issues": [],
            "improvement_recommendations": [],
            "best_practices_to_adopt": [],
            "next_steps": []
        }
        
        # Analyze each step result
        critical_issues = []
        recommendations = []
        
        for i, result in enumerate(previous_results, 1):
            if result.has_issues():
                critical_issues.extend(result.data.get('errors', []))
            
            if result.next_step_recommendations:
                recommendations.extend(result.next_step_recommendations)
        
        report_sections["critical_issues"] = critical_issues
        report_sections["improvement_recommendations"] = recommendations
        
        # Generate executive summary
        if critical_issues:
            report_sections["executive_summary"] = f"Analysis found {len(critical_issues)} critical issues requiring immediate attention."
        else:
            report_sections["executive_summary"] = "Code analysis completed successfully with recommendations for enhancement."
        
        return StepResult(
            status=StepStatus.COMPLETED,
            data=report_sections,
            message="Comprehensive analysis report generated",
            should_stop_workflow=True  # This is the final step
        )

# ===== WORKFLOW FACTORY =====

def create_code_analysis_workflow() -> WorkflowEngine:
    """Create the 6-step code analysis workflow"""
    workflow = WorkflowEngine("Code Analysis Workflow")
    
    # Add steps in sequence
    workflow.add_step(StaticAnalysisStep())
    workflow.add_step(CodeUnderstandingStep())
    workflow.add_step(ArchitectureReviewStep())
    workflow.add_step(PerformanceAnalysisStep())
    workflow.add_step(EnhancementStep())
    workflow.add_step(FinalReportStep())
    
    return workflow

class SessionContext:
    """Tracks ongoing session context for intelligent Layer 1 tagging"""
    def __init__(self):
        self.current_session = {
            "primary_domain": None,
            "active_language": None,
            "ongoing_task": None,
            "established_concepts": set(),
            "conversation_depth": 0,
            "user_expertise_level": "unknown",  # beginner, intermediate, advanced
            "session_start_time": time.time()
        }
        self.conversation_patterns = []
    
    def update_from_messages(self, messages: List[Dict]):
        """Update session context based on conversation history"""
        if not messages:
            return
            
        self.current_session["conversation_depth"] = len(messages)
        
        # Analyze conversation patterns
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        assistant_messages = [msg for msg in messages if msg.get("role") == "assistant"]
        
        if user_messages:
            # Determine expertise level from question complexity
            recent_user_content = " ".join([msg.get("content", "") for msg in user_messages[-3:]])
            self._analyze_expertise_level(recent_user_content)
            
            # Track established concepts
            self._extract_ongoing_concepts(recent_user_content)
            
            # Determine primary domain persistence
            self._analyze_domain_consistency(user_messages)
            
            # Track task progression
            self._analyze_task_progression(user_messages, assistant_messages)
    
    def _analyze_expertise_level(self, content: str):
        """Determine user expertise from conversation complexity"""
        content_lower = content.lower()
        
        beginner_indicators = ["how do i", "what is", "basic", "simple", "beginner", "new to", "first time"]
        advanced_indicators = ["optimize", "performance", "architecture", "scalability", "design pattern", "best practice"]
        
        beginner_score = sum(1 for indicator in beginner_indicators if indicator in content_lower)
        advanced_score = sum(1 for indicator in advanced_indicators if indicator in content_lower)
        
        if advanced_score > beginner_score and advanced_score >= 2:
            self.current_session["user_expertise_level"] = "advanced"
        elif beginner_score > advanced_score and beginner_score >= 2:
            self.current_session["user_expertise_level"] = "beginner"
        else:
            self.current_session["user_expertise_level"] = "intermediate"
    
    def _extract_ongoing_concepts(self, content: str):
        """Extract and maintain set of concepts being discussed"""
        content_lower = content.lower()
        
        concept_keywords = {
            "state_management": ["state", "bloc", "provider", "riverpod", "redux"],
            "async_programming": ["async", "await", "future", "stream", "isolate"],
            "navigation": ["navigation", "routing", "navigator", "route", "page"],
            "ui_components": ["widget", "component", "ui", "layout", "design"],
            "data_persistence": ["database", "storage", "cache", "local", "persist"],
            "api_integration": ["api", "http", "rest", "graphql", "endpoint"],
            "testing": ["test", "unit test", "widget test", "integration test"],
            "performance": ["performance", "optimization", "memory", "cpu", "lag"]
        }
        
        for concept, keywords in concept_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                self.current_session["established_concepts"].add(concept)
    
    def _analyze_domain_consistency(self, user_messages: List[Dict]):
        """Determine if user is consistently working in a domain"""
        if len(user_messages) < 3:
            return
            
        recent_content = " ".join([msg.get("content", "") for msg in user_messages[-5:]])
        
        domain_scores = {
            "flutter_mobile": ["flutter", "dart", "widget", "mobile", "app"],
            "web_development": ["web", "html", "css", "javascript", "frontend"],
            "backend": ["api", "server", "backend", "database", "endpoint"],
            "ai_ml": ["ai", "ml", "machine learning", "neural", "model"]
        }
        
        scores = {}
        for domain, keywords in domain_scores.items():
            scores[domain] = sum(1 for keyword in keywords if keyword in recent_content.lower())
        
        if scores:
            primary_domain = max(scores, key=scores.get)
            if scores[primary_domain] >= 3:  # Consistent mention
                self.current_session["primary_domain"] = primary_domain
    
    def _analyze_task_progression(self, user_messages: List[Dict], assistant_messages: List[Dict]):
        """Analyze what kind of task user is working on"""
        if not user_messages:
            return
            
        recent_user = " ".join([msg.get("content", "") for msg in user_messages[-3:]])
        recent_assistant = " ".join([msg.get("content", "") for msg in assistant_messages[-3:]])
        
        # Look for task progression patterns
        if "error" in recent_user.lower() or "problem" in recent_user.lower():
            self.current_session["ongoing_task"] = "debugging"
        elif "how to" in recent_user.lower() or "tutorial" in recent_user.lower():
            self.current_session["ongoing_task"] = "learning"
        elif "create" in recent_user.lower() or "build" in recent_user.lower():
            self.current_session["ongoing_task"] = "development"
        elif len(recent_assistant) > len(recent_user) * 2:  # Long explanations
            self.current_session["ongoing_task"] = "explanation"

# Global session context
session_context = SessionContext()

def extract_layer1_tags(user_message: str, conversation_context: List[Dict]) -> Dict[str, str]:
    """
    Layer 1 Manual Tagging: Real-time context-aware tagging by the Orchestrator.
    
    This analyzes the current session context, conversation patterns, and user behavior
    to generate intelligent tags that reflect the actual programming context and task.
    """
    global session_context
    
    # Update session context with full conversation
    session_context.update_from_messages(conversation_context)
    
    tags = {}
    user_message_lower = user_message.lower()
    session = session_context.current_session
    
    # ===== DOMAIN TAGGING (based on session consistency) =====
    if session["primary_domain"]:
        # Use established session domain
        if session["primary_domain"] == "flutter_mobile":
            tags["domain"] = "programming"
            tags["subdomain"] = "mobile_development"
            tags["framework"] = "flutter"
        elif session["primary_domain"] == "web_development":
            tags["domain"] = "programming"
            tags["subdomain"] = "web_development"
        elif session["primary_domain"] == "backend":
            tags["domain"] = "programming"
            tags["subdomain"] = "backend_development"
        elif session["primary_domain"] == "ai_ml":
            tags["domain"] = "programming"
            tags["subdomain"] = "ai_ml"
    else:
        # Fallback to message-level detection
        if any(keyword in user_message_lower for keyword in ["flutter", "dart", "widget"]):
            tags["domain"] = "programming"
            tags["subdomain"] = "mobile_development"
            tags["framework"] = "flutter"
        elif any(keyword in user_message_lower for keyword in ["api", "backend", "server"]):
            tags["domain"] = "programming"
            tags["subdomain"] = "backend_development"
    
    # ===== LANGUAGE TAGGING (session-aware) =====
    if session["active_language"]:
        tags["language"] = session["active_language"]
    else:
        # Detect from current message
        for language in PROGRAMMING_LANGUAGES:
            if language in user_message_lower:
                tags["language"] = language
                session_context.current_session["active_language"] = language
                break
    
    # ===== TASK TAGGING (based on session progression) =====
    if session["ongoing_task"]:
        tags["task"] = session["ongoing_task"]
    else:
        # Message-level task detection
        if any(keyword in user_message_lower for keyword in ["error", "bug", "fix", "debug"]):
            tags["task"] = "debugging"
        elif any(keyword in user_message_lower for keyword in ["how to", "tutorial", "learn"]):
            tags["task"] = "learning"
        elif any(keyword in user_message_lower for keyword in ["create", "build", "make"]):
            tags["task"] = "development"
        elif any(keyword in user_message_lower for keyword in ["explain", "what is", "understand"]):
            tags["task"] = "explanation"
    
    # ===== CONCEPT TAGGING (from established session concepts) =====
    if session["established_concepts"]:
        # Use the most relevant established concept
        for concept in session["established_concepts"]:
            if concept.replace("_", " ") in user_message_lower or concept.replace("_", "") in user_message_lower:
                tags["concept"] = concept
                break
        
        # If no direct match, use the primary concept
        if "concept" not in tags and session["established_concepts"]:
            tags["concept"] = list(session["established_concepts"])[0]
    
    # ===== EXPERTISE LEVEL =====
    tags["user_level"] = session["user_expertise_level"]
    
    # ===== SESSION METADATA =====
    tags["conversation_depth"] = str(session["conversation_depth"])
    tags["session_duration"] = str(int(time.time() - session["session_start_time"]))
    
    # ===== CONTEXT-SPECIFIC ENHANCEMENTS =====
    
    # If this is a follow-up question, mark it
    if session["conversation_depth"] > 2:
        recent_topics = []
        for msg in conversation_context[-3:]:
            if msg.get("role") == "user":
                recent_topics.extend(msg.get("content", "").lower().split())
        
        # Check for follow-up indicators
        if any(word in user_message_lower for word in ["also", "additionally", "furthermore", "and", "another"]):
            tags["interaction_type"] = "follow_up"
        elif any(word in user_message_lower for word in ["but", "however", "instead", "different"]):
            tags["interaction_type"] = "clarification"
        elif any(word in user_message_lower for word in ["thanks", "thank you", "got it", "understood"]):
            tags["interaction_type"] = "acknowledgment"
    
    # ===== WEB SEARCH INDICATORS =====
    if any(keyword in user_message_lower for keyword in WEB_SEARCH_KEYWORDS):
        tags["search_type"] = "web_search"
        
        # Detect what kind of web search this might be
        if any(word in user_message_lower for word in ["news", "latest", "recent", "current"]):
            tags["search_intent"] = "current_information"
        elif any(word in user_message_lower for word in ["price", "cost", "buy", "product"]):
            tags["search_intent"] = "product_research"
        elif any(word in user_message_lower for word in ["tutorial", "guide", "how to"]):
            tags["search_intent"] = "learning_resource"
        else:
            tags["search_intent"] = "general_information"
    
    # ===== GIT/DEVELOPMENT WORKFLOW INDICATORS =====
    if any(keyword in user_message_lower for keyword in GIT_KEYWORDS):
        tags["tool_type"] = "git_operations"
        
        # Detect specific Git operation types
        if any(word in user_message_lower for word in ["status", "check"]):
            tags["git_operation"] = "status_check"
        elif any(word in user_message_lower for word in ["commit", "save"]):
            tags["git_operation"] = "commit"
        elif any(word in user_message_lower for word in ["branch", "checkout", "switch"]):
            tags["git_operation"] = "branch_management"
        elif any(word in user_message_lower for word in ["diff", "changes", "compare"]):
            tags["git_operation"] = "diff_analysis"
        elif any(word in user_message_lower for word in ["log", "history"]):
            tags["git_operation"] = "history_review"
        elif any(word in user_message_lower for word in ["push", "pull", "sync"]):
            tags["git_operation"] = "remote_sync"
        else:
            tags["git_operation"] = "general"
    
    if any(keyword in user_message_lower for keyword in GITHUB_KEYWORDS):
        tags["tool_type"] = "github_api"
        
        # Detect GitHub operation types
        if any(word in user_message_lower for word in ["issue", "bug", "feature request"]):
            tags["github_operation"] = "issue_management"
        elif any(word in user_message_lower for word in ["pull request", "pr", "merge"]):
            tags["github_operation"] = "pull_request"
        elif any(word in user_message_lower for word in ["release", "version", "tag"]):
            tags["github_operation"] = "release_management"
        elif any(word in user_message_lower for word in ["search", "find", "repository"]):
            tags["github_operation"] = "repository_search"
        else:
            tags["github_operation"] = "general"
    
    if any(keyword in user_message_lower for keyword in REPO_ANALYSIS_KEYWORDS):
        tags["tool_type"] = "repository_analysis"
        
        # Detect repository analysis operation types
        if any(word in user_message_lower for word in ["explore", "structure", "tree", "files"]):
            tags["analysis_operation"] = "structure_exploration"
        elif any(word in user_message_lower for word in ["dependencies", "package", "requirements"]):
            tags["analysis_operation"] = "dependency_analysis"
        elif any(word in user_message_lower for word in ["metrics", "statistics", "code analysis", "lines"]):
            tags["analysis_operation"] = "code_metrics"
        else:
            tags["analysis_operation"] = "general"
    
    # Development helpers detection
    if any(keyword in user_message_lower for keyword in PACKAGE_SEARCH_KEYWORDS):
        tags["tool_type"] = "package_search"
        
        # Detect package ecosystem
        if any(word in user_message_lower for word in ["npm", "node", "javascript"]):
            tags["package_ecosystem"] = "npm"
        elif any(word in user_message_lower for word in ["pip", "python"]):
            tags["package_ecosystem"] = "pypi"
        elif any(word in user_message_lower for word in ["pub", "dart", "flutter"]):
            tags["package_ecosystem"] = "pub_dev"
        elif any(word in user_message_lower for word in ["cargo", "rust"]):
            tags["package_ecosystem"] = "crates_io"
        elif any(word in user_message_lower for word in ["maven", "java"]):
            tags["package_ecosystem"] = "maven"
        else:
            tags["package_ecosystem"] = "general"
    
    if any(keyword in user_message_lower for keyword in BUILD_COMMAND_KEYWORDS):
        tags["tool_type"] = "build_commands"
        
        # Detect build operation types
        if any(word in user_message_lower for word in ["build", "compile"]):
            tags["build_operation"] = "build"
        elif any(word in user_message_lower for word in ["test", "spec", "unit"]):
            tags["build_operation"] = "testing"
        elif any(word in user_message_lower for word in ["lint", "format", "style"]):
            tags["build_operation"] = "code_quality"
        elif any(word in user_message_lower for word in ["deploy", "ci", "cd", "pipeline"]):
            tags["build_operation"] = "deployment"
        elif any(word in user_message_lower for word in ["run", "execute", "command"]):
            tags["build_operation"] = "execution"
        else:
            tags["build_operation"] = "detection"
    
    # Auto-linter detection
    if any(keyword in user_message_lower for keyword in AUTO_LINTER_KEYWORDS):
        tags["tool_type"] = "auto_linter"
        
        # Detect linter operation types
        if any(word in user_message_lower for word in ["analyze", "check", "lint"]):
            tags["linter_operation"] = "analysis"
        elif any(word in user_message_lower for word in ["fix", "auto fix", "repair"]):
            tags["linter_operation"] = "auto_fix"
        elif any(word in user_message_lower for word in ["format", "style", "prettier"]):
            tags["linter_operation"] = "formatting"
        elif any(word in user_message_lower for word in ["quality", "best practices", "standards"]):
            tags["linter_operation"] = "quality_check"
        else:
            tags["linter_operation"] = "general"
        
        # Detect specific linter tools mentioned
        if any(word in user_message_lower for word in ["flutter analyze", "dart"]):
            tags["linter_tool"] = "flutter_dart"
        elif any(word in user_message_lower for word in ["eslint", "javascript", "react"]):
            tags["linter_tool"] = "eslint"
        elif any(word in user_message_lower for word in ["prettier"]):
            tags["linter_tool"] = "prettier"
        elif any(word in user_message_lower for word in ["flake8", "black", "mypy", "python"]):
            tags["linter_tool"] = "python_tools"
        elif any(word in user_message_lower for word in ["clippy", "rust"]):
            tags["linter_tool"] = "rust_clippy"
        else:
            tags["linter_tool"] = "auto_detect"
    
    # Mark complex vs simple questions
    if len(user_message.split()) > 20 or any(word in user_message_lower for word in ["complex", "advanced", "detailed"]):
        tags["complexity"] = "high"
    elif len(user_message.split()) < 8:
        tags["complexity"] = "low" 
    else:
        tags["complexity"] = "medium"
    
    logger.info(f"🏷️ Layer 1 Context-Aware Tags: {tags}")
    logger.info(f"📊 Session Context: domain={session['primary_domain']}, task={session['ongoing_task']}, level={session['user_expertise_level']}")
    
    return tags

def build_master_prompt_with_memory(base_prompt: str, user_message: str) -> str:
    """
    Master Prompt Template: Integrates Memory System (Tier 1 + Tier 2) with base prompt
    
    Args:
        base_prompt: The base ReAct or other prompt template
        user_message: Current user message for context retrieval
        
    Returns:
        Enhanced prompt with memory context
    """
    try:
        from mcp_memory import mcp_get_context, mcp_get_corrections
        
        # Get memory context (Tier 1: Redis recent context + Tier 2: MongoDB profile)
        memory_result = mcp_get_context(user_message, include_long_term=False)
        
        if memory_result.get("status") != "success":
            logger.warning(f"⚠️ Memory context retrieval failed: {memory_result.get('error', 'unknown')}")
            return base_prompt
            
        context = memory_result.get("context", {})
        short_term = context.get("short_term", [])
        profile = context.get("profile", {})
        
        # Get relevant corrections from MongoDB
        corrections = mcp_get_corrections(limit=3)
        
        # Build memory-enhanced prompt
        memory_sections = []
        
        # Add user profile (Tier 2: Rules & Preferences)
        if profile:
            rules = profile.get("rules", [])
            preferences = profile.get("preferences", {})
            
            if rules:
                rules_text = "\n".join([f"- {rule.get('rule', rule)}" for rule in rules[:5]])
                memory_sections.append(f"**User Rules & Preferences:**\n{rules_text}")
                
            if preferences:
                prefs_text = "\n".join([f"- {k}: {v}" for k, v in preferences.items() if k != "_id"])
                if prefs_text:
                    memory_sections.append(f"**Preferences:**\n{prefs_text}")
        
        # Add recent conversation context (Tier 1: Redis)
        if short_term:
            recent_context = []
            for interaction in short_term[-3:]:  # Last 3 interactions
                messages = interaction.get("messages", [])
                for msg in messages[-2:]:  # Last 2 messages per interaction
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")[:150]  # Truncate for brevity
                    recent_context.append(f"{role}: {content}...")
            
            if recent_context:
                context_text = "\n".join(recent_context)
                memory_sections.append(f"**Recent Context:**\n{context_text}")
        
        # Add learning from corrections
        if corrections:
            correction_lessons = []
            for correction in corrections:
                ai_resp = correction.get("ai_response", "")[:100]
                user_correction = correction.get("user_correction", "")[:100]
                topic = correction.get("topic", "general")
                correction_lessons.append(f"Topic: {topic}\n  My mistake: {ai_resp}...\n  Correction: {user_correction}...")
            
            if correction_lessons:
                lessons_text = "\n\n".join(correction_lessons)
                memory_sections.append(f"**Learn from Past Mistakes:**\n{lessons_text}")
        
        # Combine into enhanced prompt
        if memory_sections:
            memory_context = "\n\n".join(memory_sections)
            
            # Get the original template text and enhance it
            original_template = base_prompt.template if hasattr(base_prompt, 'template') else str(base_prompt)
            enhanced_template = f"""{original_template}

IMPORTANT CONTEXT FROM MEMORY SYSTEM:
{memory_context}

Use this memory context to provide personalized, consistent responses that respect user preferences and learn from past interactions."""
            
            # Create new PromptTemplate with enhanced content
            from langchain.prompts import PromptTemplate
            enhanced_prompt = PromptTemplate(
                input_variables=base_prompt.input_variables if hasattr(base_prompt, 'input_variables') else ['tools', 'tool_names', 'agent_scratchpad', 'input'],
                template=enhanced_template
            )
            
            logger.info(f"🧠 Enhanced prompt with memory context: {len(memory_sections)} sections")
            return enhanced_prompt
        else:
            logger.info("💭 No memory context available, using base prompt")
            return base_prompt
            
    except Exception as e:
        logger.error(f"❌ Master Prompt Template error: {e}")
        return base_prompt

def is_title_generation_request(user_message: str) -> bool:
    """Detect if this is Continue's automatic title generation request"""
    user_message_lower = user_message.lower()
    title_indicators = [
        "please reply with a title",
        "give a title for the chat",
        "3-4 words in length",
        "title for the chat that is",
        "no additional text or explanation"
    ]
    return any(indicator in user_message_lower for indicator in title_indicators)

def should_use_memory_tools(user_message: str) -> bool:
    """Determine if memory tools should be made available to the agent"""
    # Skip memory tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in MEMORY_KEYWORDS)

def should_use_rag_tools(user_message: str) -> bool:
    """Determine if RAG tools should be made available to the agent"""
    # Skip RAG tools for title generation requests  
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in RAG_KEYWORDS)

def should_use_web_search(user_message: str) -> bool:
    """Determine if web search tools should be made available to the agent"""
    # Skip web search for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    
    # Check for explicit web search keywords
    if any(keyword in user_message_lower for keyword in WEB_SEARCH_KEYWORDS):
        return True
    
    # Check for temporal indicators (recent/current information)
    temporal_indicators = ["latest", "recent", "current", "new", "today", "this year", "2024", "2025"]
    if any(indicator in user_message_lower for indicator in temporal_indicators):
        return True
    
    # Check for information-seeking patterns
    info_patterns = ["what's happening", "what's new", "tell me about", "news about", "find information"]
    if any(pattern in user_message_lower for pattern in info_patterns):
        return True
    
    return False

def should_use_git_tools(user_message: str) -> bool:
    """Determine if Git tools should be made available to the agent"""
    # Skip Git tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in GIT_KEYWORDS)

def should_use_github_tools(user_message: str) -> bool:
    """Determine if GitHub API tools should be made available to the agent"""
    # Skip GitHub tools for title generation requests  
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in GITHUB_KEYWORDS)

def should_use_dev_workflow_tools(user_message: str) -> bool:
    """Determine if development workflow tools should be made available to the agent"""
    # Skip dev tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    # Check both package search and build command keywords
    return any(keyword in user_message_lower for keyword in PACKAGE_SEARCH_KEYWORDS + BUILD_COMMAND_KEYWORDS)

def should_use_repo_analysis_tools(user_message: str) -> bool:
    """Determine if repository analysis tools should be made available to the agent"""
    # Skip repo analysis tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in REPO_ANALYSIS_KEYWORDS)

def should_use_auto_linter_tools(user_message: str) -> bool:
    """Determine if auto-linter tools should be made available to the agent"""
    # Skip auto-linter tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in AUTO_LINTER_KEYWORDS)

def should_use_sandbox_tools(user_message: str) -> bool:
    """Determine if sandbox tools should be made available to the agent"""
    # Skip sandbox tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    
    # Check for explicit sandbox/execution keywords
    if any(keyword in user_message_lower for keyword in SANDBOX_KEYWORDS):
        return True
    
    # Check for calculation requests
    if any(keyword in user_message_lower for keyword in CALCULATION_KEYWORDS):
        return True
    
    # Check for code verification patterns
    verification_patterns = ["does this work", "test this", "verify", "what happens", "output", "result"]
    if any(pattern in user_message_lower for pattern in verification_patterns):
        return True
    
    # Check if message contains code blocks (likely needs testing)
    if "```" in user_message or "def " in user_message or "print(" in user_message:
        return True
    
    return False

def should_use_naming_conventions(user_message: str) -> bool:
    """Determine if the request is about applying naming conventions"""
    if is_title_generation_request(user_message):
        return False
    
    user_message_lower = user_message.lower()
    
    naming_keywords = [
        "naming convention", "correct naming", "use correct naming",
        "proper naming", "rename", "naming standards", "naming style",
        "camelcase", "snake_case", "pascalcase", "kebab-case"
    ]
    
    return any(keyword in user_message_lower for keyword in naming_keywords)

def should_use_code_analysis_workflow(user_message: str) -> bool:
    """Determine if the request requires sequential code analysis workflow"""
    if is_title_generation_request(user_message):
        return False
    
    user_message_lower = user_message.lower()
    
    # Check for code analysis keywords
    analysis_keywords = [
        "analyze", "examine", "review", "refactor", "suggest improvements",
        "code analysis", "optimize", "best practices", "clean up",
        "architecture review", "performance review", "suggestions"
    ]
    
    # Check for code presence (code blocks or file extensions)
    has_code = ("```" in user_message or 
                any(ext in user_message_lower for ext in [".py", ".dart", ".js", ".java", ".cpp", ".c", ".go", ".rs"]))
    
    # Check for analysis request patterns
    has_analysis_request = any(keyword in user_message_lower for keyword in analysis_keywords)
    
    # Require both code presence and analysis request
    return has_code and has_analysis_request

def extract_code_from_message(user_message: str) -> Dict[str, Any]:
    """Extract code and metadata from user message"""
    context = {
        "code": "",
        "language": "auto",
        "filename": None,
        "analysis_request": ""
    }
    
    # Extract code blocks
    if "```" in user_message:
        # Find first code block
        start_idx = user_message.find("```")
        if start_idx != -1:
            # Check if language is specified
            newline_after_backticks = user_message.find("\n", start_idx)
            if newline_after_backticks != -1:
                potential_lang = user_message[start_idx + 3:newline_after_backticks].strip()
                if potential_lang and len(potential_lang) < 20:  # Reasonable language name
                    context["language"] = potential_lang
                    code_start = newline_after_backticks + 1
                else:
                    code_start = start_idx + 3
            else:
                code_start = start_idx + 3
            
            # Find end of code block
            end_idx = user_message.find("```", code_start)
            if end_idx != -1:
                context["code"] = user_message[code_start:end_idx].strip()
    
    # Extract filename if mentioned
    for ext in [".py", ".dart", ".js", ".java", ".cpp", ".c", ".go", ".rs"]:
        if ext in user_message:
            # Find potential filename
            words = user_message.split()
            for word in words:
                if ext in word and not word.startswith("http"):
                    context["filename"] = word.strip(".,!?\"'")
                    # Infer language from extension
                    ext_to_lang = {
                        ".py": "python", ".dart": "dart", ".js": "javascript",
                        ".java": "java", ".cpp": "cpp", ".c": "c", 
                        ".go": "go", ".rs": "rust"
                    }
                    context["language"] = ext_to_lang.get(ext, "auto")
                    break
    
    # Extract analysis request type
    user_message_lower = user_message.lower()
    if "refactor" in user_message_lower:
        context["analysis_request"] = "refactor"
    elif "optimize" in user_message_lower or "performance" in user_message_lower:
        context["analysis_request"] = "optimize"
    elif "analyze" in user_message_lower or "examine" in user_message_lower:
        context["analysis_request"] = "analyze"
    else:
        context["analysis_request"] = "general"
    
    return context

def strip_thoughts_from_content(content_to_process: str) -> str:
    final_speakable_content = ""
    while True:
        start_think_idx = content_to_process.find('<think>')
        end_think_idx = content_to_process.find('</think>')
        if start_think_idx != -1 and end_think_idx != -1 and start_think_idx < end_think_idx:
            final_speakable_content += content_to_process[:start_think_idx]
            if DEBUG_VERBOSE:
                thought = content_to_process[start_think_idx : end_think_idx + len('</think>')]
                logger.debug(f"Stripping thought: {thought[:100]}...")
            content_to_process = content_to_process[end_think_idx + len('</think>'):]
        elif start_think_idx != -1 and end_think_idx == -1 and len(content_to_process) > start_think_idx + 7: 
            final_speakable_content += content_to_process[:start_think_idx]
            if DEBUG_VERBOSE: logger.debug(f"Partial thought start detected, content before: '{final_speakable_content}', buffering rest: '{content_to_process[start_think_idx:100]}'")
            content_to_process = "" 
            break
        else: 
            final_speakable_content += content_to_process
            break
    return final_speakable_content.strip()

async def generate_openai_compatible_response(content: str, model_name: str):
    """
    Generate OpenAI-compatible streaming response for slash commands and simple responses
    """
    request_id = f"chatcmpl-slash-{int(time.time())}"
    
    # Split content into words for streaming
    words = content.split()
    for i, word in enumerate(words):
        chunk = {
            "id": f"{request_id}-{i+1}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name,
            "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.02)  # Small delay for smooth streaming
    
    # Send final chunk
    final_chunk = {
        "id": f"{request_id}-final",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"

async def stream_langchain_agent_response(agent_executor_instance: AgentExecutor, input_messages: List[Dict[str, str]], model_name_used: str, request_id_prefix_str: str):
    """
    Invokes the ReAct agent with memory integration, gets the complete final answer, 
    and then streams it back to the client.
    """
    lc_messages_history = []
    user_input_for_agent = ""

    for msg in input_messages:
        if msg["role"] == "user":
            lc_messages_history.append(HumanMessage(content=msg["content"]))
            user_input_for_agent = msg["content"]
        elif msg["role"] == "assistant":
            lc_messages_history.append(AIMessage(content=msg["content"]))

    # Extract Layer 1 tags for potential memory saving
    layer1_tags = extract_layer1_tags(user_input_for_agent, input_messages)

    # For ReAct, it's more reliable to pass the full history.
    agent_input_data = {"input": user_input_for_agent, "chat_history": lc_messages_history}

    try:
        logger.info(f"🤖 Invoking ReAct agent for query: '{user_input_for_agent}'")
        
        # Use .ainvoke() to get the final result reliably.
        result = await agent_executor_instance.ainvoke(agent_input_data)
        final_answer = result.get("output", "[Agent did not return a final answer.]")
        logger.info(f"🤖 ReAct agent finished. Final Answer length: {len(final_answer)}")

        # Save the interaction to memory with Layer 1 tags
        try:
            interaction_messages = input_messages + [{"role": "assistant", "content": final_answer}]
            save_result = mcp_save_interaction(interaction_messages, layer1_tags)
            if save_result["status"] == "success":
                logger.info(f"💾 Interaction saved to memory: {save_result['interaction_id']}")
            else:
                logger.warning(f"⚠️ Failed to save interaction: {save_result.get('error')}")
        except Exception as e:
            logger.error(f"❌ Memory save error: {e}")

        # Stream the final answer word-by-word for a good user experience.
        for word in final_answer.split():
            sse_chunk = {
                "id": f"{request_id_prefix_str}-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model_name_used,
                "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None }]
            }
            yield f"data: {json.dumps(sse_chunk)}\n\n"
            await asyncio.sleep(0.05)

        # Send the final DONE message.
        final_sse_chunk = {
            "id": f"{request_id_prefix_str}-final",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name_used,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
        }
        yield f"data: {json.dumps(final_sse_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"🤖 Langchain Agent Path Streaming ({request_id_prefix_str}): Error during agent execution: {e}", exc_info=True)
        error_message = f"[Agent Error: {e}]"
        error_chunk = {"choices": [{"delta": {"content": error_message}, "finish_reason": "error"}]}
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"

async def stream_direct_from_ollama(messages: List[Dict[str, str]], model_name: str, request_id_prefix: str):
    """
    Direct streaming from Ollama with memory integration for simple conversations
    """
    api_url = f"{OLLAMA_OPENAI_BASE}/chat/completions"
    payload = { "model": model_name, "messages": messages, "stream": True, "temperature": float(os.getenv("LLM_TEMPERATURE_DIRECT", "0.7"))}
    logger.info(f"💬 Direct Path ({request_id_prefix}): Streaming from Ollama model '{model_name}'. API: {api_url}")

    chunk_count = 0
    has_sent_content = False
    accumulated_content_for_current_thought_block = "" 
    full_response = ""  # Collect full response for memory saving
    
    try:
        async with aconnect_sse(httpx.AsyncClient(timeout=DIRECT_OLLAMA_TIMEOUT), "POST", api_url, json=payload) as event_source:
            async for sse_event in event_source.aiter_sse():
                if shutdown_event.is_set(): break
                if sse_event.event == "message":
                    if sse_event.data.strip() == "[DONE]": break
                    try:
                        chunk_data = json.loads(sse_event.data)
                        delta_content_raw = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content")
                        finish_reason_ollama = chunk_data.get("choices", [{}])[0].get("finish_reason")
                        if delta_content_raw is not None:
                            content_to_process = delta_content_raw
                            full_response += content_to_process  # Accumulate for memory
                            accumulated_content_for_current_thought_block += content_to_process
                            temp_speakable_buffer = ""
                            while True:
                                start_think_idx = accumulated_content_for_current_thought_block.find('<think>')
                                end_think_idx = accumulated_content_for_current_thought_block.find('</think>')
                                if start_think_idx != -1 and end_think_idx != -1 and start_think_idx < end_think_idx:
                                    temp_speakable_buffer += accumulated_content_for_current_thought_block[:start_think_idx] 
                                    if DEBUG_VERBOSE: logger.debug(f"Direct Path ({request_id_prefix}): Stripping thought: {accumulated_content_for_current_thought_block[start_think_idx : end_think_idx + len('</think>')][:100]}")
                                    accumulated_content_for_current_thought_block = accumulated_content_for_current_thought_block[end_think_idx + len('</think>'):]
                                elif start_think_idx != -1 and end_think_idx == -1 :
                                    temp_speakable_buffer += accumulated_content_for_current_thought_block[:start_think_idx]
                                    accumulated_content_for_current_thought_block = accumulated_content_for_current_thought_block[start_think_idx:]
                                    break 
                                else:
                                    temp_speakable_buffer += accumulated_content_for_current_thought_block
                                    accumulated_content_for_current_thought_block = ""
                                    break
                            final_speakable_content = temp_speakable_buffer 
                            if final_speakable_content:
                                chunk_count += 1
                                has_sent_content = True
                                sse_chunk = {"id": f"{request_id_prefix}-{chunk_count}", "object": "chat.completion.chunk", "created": int(time.time()), "model": model_name, "choices": [{"index": 0, "delta": {"content": final_speakable_content}, "finish_reason": None }]}
                                yield f"data: {json.dumps(sse_chunk)}\n\n"
                                await asyncio.sleep(0.01)
                        if finish_reason_ollama: 
                            if accumulated_content_for_current_thought_block.strip() and not accumulated_content_for_current_thought_block.strip().startswith("<think"):
                                yield f"data: {json.dumps({'id': f'{request_id_prefix}-{chunk_count+1}', 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model_name, 'choices': [{'index': 0, 'delta': {'content': accumulated_content_for_current_thought_block.strip()}, 'finish_reason': None }]})}\n\n"
                            break 
                    except Exception as e_parse: logger.error(f"Direct Path ({request_id_prefix}): Error parsing Ollama line: {e_parse} - Data: '{sse_event.data}'")
    except Exception as e_stream: logger.error(f"Direct Path ({request_id_prefix}): Unexpected error: {e_stream}", exc_info=DEBUG_VERBOSE)

    # Save direct conversation to memory if we have content (skip for title generation)
    if full_response and messages:
        try:
            # Extract user message to check if it's a title request
            user_message = ""
            if messages and messages[-1].get("role") == "user":
                user_message = messages[-1].get("content", "")
            
            # Skip saving title generation requests to memory
            if not is_title_generation_request(user_message):
                layer1_tags = extract_layer1_tags(user_message, messages)
                
                # Save the complete conversation
                interaction_messages = messages + [{"role": "assistant", "content": strip_thoughts_from_content(full_response)}]
                save_result = mcp_save_interaction(interaction_messages, layer1_tags)
                if save_result["status"] == "success":
                    logger.info(f"💾 Direct conversation saved to memory: {save_result['interaction_id']}")
                else:
                    logger.warning(f"⚠️ Failed to save direct conversation: {save_result.get('error')}")
            else:
                logger.info("📝 Skipping memory save for title generation request")
        except Exception as e:
            logger.error(f"❌ Memory save error for direct path: {e}")

    if not has_sent_content and chunk_count == 0: logger.warning(f"Direct Path ({request_id_prefix}): No content streamed.")
    final_sse_chunk = {"id": f"{request_id_prefix}-final", "object": "chat.completion.chunk", "created": int(time.time()), "model": model_name, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop" }]}
    yield f"data: {json.dumps(final_sse_chunk)}\n\n"
    yield "data: [DONE]\n\n"
    logger.info(f"Direct Path ({request_id_prefix}): Streamed {chunk_count} direct chunks. Sent DONE.")

@app.post("/api/chat")
async def chat_proxy(request: Request):
    try:
        request_body = await request.json()
        requested_model_name = request_body.get('model', DEFAULT_MODEL) 
        messages = request_body.get('messages', []) 
        if not messages: raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
        logger.info(f"🔄 Chat Request: Model='{requested_model_name}', Msgs={len(messages)}")
        last_user_message_content = ""
        original_user_message = ""
        if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
            content = messages[-1].get("content")
            if isinstance(content, str): 
                original_user_message = content
                last_user_message_content = content.lower()
        
        # Check for slash commands first
        global slash_processor
        if slash_processor.is_slash_command(original_user_message):
            logger.info(f"⚡ Slash Command Detected: {original_user_message}")
            try:
                parsed_command = slash_processor.parse_command(original_user_message)
                command_result = await slash_processor.execute_command(parsed_command)
                
                # Return slash command result directly
                return StreamingResponse(
                    generate_openai_compatible_response(command_result, requested_model_name),
                    media_type="text/plain"
                )
            except Exception as e:
                logger.error(f"⚡ Slash Command Error: {e}")
                error_msg = f"❌ Slash command error: {str(e)}"
                return StreamingResponse(
                    generate_openai_compatible_response(error_msg, requested_model_name),
                    media_type="text/plain"
                )
        
        # Orchestrator Logic: Decide which tools to use
        is_title_request = is_title_generation_request(last_user_message_content)
        use_naming_conventions = should_use_naming_conventions(original_user_message)
        use_code_analysis_workflow = should_use_code_analysis_workflow(original_user_message)
        use_memory_tools = should_use_memory_tools(last_user_message_content)
        use_rag_tools = should_use_rag_tools(last_user_message_content)
        use_web_search = should_use_web_search(last_user_message_content)
        use_git_tools = should_use_git_tools(last_user_message_content)
        use_github_tools = should_use_github_tools(last_user_message_content)
        use_dev_workflow_tools = should_use_dev_workflow_tools(last_user_message_content)
        use_repo_analysis_tools = should_use_repo_analysis_tools(last_user_message_content)
        use_auto_linter_tools = should_use_auto_linter_tools(last_user_message_content)
        use_sandbox_tools = should_use_sandbox_tools(last_user_message_content)
        use_langchain_agent = use_memory_tools or use_rag_tools or use_web_search or use_git_tools or use_github_tools or use_dev_workflow_tools or use_repo_analysis_tools or use_auto_linter_tools or use_sandbox_tools
        
        if is_title_request:
            logger.info(f"📝 Orchestrator Decision: Title generation request detected - routing to direct path")
        elif use_naming_conventions:
            logger.info(f"📝 Orchestrator Decision: Naming conventions request detected - loading conventions guide")
        elif use_code_analysis_workflow:
            logger.info(f"🔄 Orchestrator Decision: Code analysis workflow detected - using sequential analysis")
        else:
            logger.info(f"🧠 Orchestrator Decision: NamingConv={use_naming_conventions}, CodeWorkflow={use_code_analysis_workflow}, Memory={use_memory_tools}, RAG={use_rag_tools}, WebSearch={use_web_search}, Git={use_git_tools}, GitHub={use_github_tools}, DevWorkflow={use_dev_workflow_tools}, RepoAnalysis={use_repo_analysis_tools}, AutoLinter={use_auto_linter_tools}, Sandbox={use_sandbox_tools}, Agent={use_langchain_agent}")
        
        request_id_base = int(time.time())

        # NAMING CONVENTIONS PATH
        if use_naming_conventions:
            logger.info("📝 Chat Path: Loading naming conventions guide.")
            try:
                # Read the naming conventions file
                with open("/mnt/caseSSD/mcp_server_project/name_conv.md", "r") as f:
                    conventions_content = f.read()
                
                # Create a response that includes the conventions and applies them to any code in the message
                code_context = extract_code_from_message(original_user_message)
                
                response_content = f"""# 📝 Naming Conventions Applied

{conventions_content}

---

"""
                
                # If there's code in the message, apply conventions to it
                if code_context["code"].strip():
                    language = code_context["language"]
                    response_content += f"""## Your Code with Correct Naming Conventions

**Detected Language**: {language}

**Original Code**:
```{language}
{code_context["code"]}
```

**Naming Convention Guidelines for {language.title()}**:
"""
                    
                    # Add language-specific guidelines
                    if language.lower() in ['dart', 'flutter']:
                        response_content += """
- Variables/functions/methods → `camelCase`
- Classes/types/enums → `PascalCase`  
- Constants → `lowerCamelCase`
- Files/directories → `snake_case`
"""
                    elif language.lower() == 'python':
                        response_content += """
- Variables/functions/methods → `snake_case`
- Classes → `PascalCase`
- Constants → `SCREAMING_SNAKE_CASE`
- Files/modules → `snake_case`
"""
                    elif language.lower() in ['javascript', 'typescript', 'js', 'ts']:
                        response_content += """
- Variables/functions → `camelCase`
- Classes/interfaces → `PascalCase`
- Constants → `SCREAMING_SNAKE_CASE` or `camelCase`
- Files → `camelCase` or `kebab-case`
"""
                else:
                    response_content += "\n*Include code in your message for specific naming convention application.*"
                
                return StreamingResponse(
                    generate_openai_compatible_response(response_content, requested_model_name),
                    media_type="text/plain"
                )
                
            except FileNotFoundError:
                error_msg = "❌ Naming conventions file not found. Please ensure name_conv.md exists in the project directory."
                return StreamingResponse(
                    generate_openai_compatible_response(error_msg, requested_model_name),
                    media_type="text/plain"
                )
            except Exception as e:
                logger.error(f"❌ Naming conventions error: {str(e)}")
                error_msg = f"❌ Error loading naming conventions: {str(e)}"
                return StreamingResponse(
                    generate_openai_compatible_response(error_msg, requested_model_name),
                    media_type="text/plain"
                )

        # CODE ANALYSIS WORKFLOW PATH
        elif use_code_analysis_workflow:
            logger.info("🔄 Chat Path: Using Sequential Code Analysis Workflow.")
            
            # Extract code and context from message
            code_context = extract_code_from_message(original_user_message)
            
            if not code_context["code"].strip():
                # No code found in code blocks, return error
                error_msg = "❌ Code analysis requested but no code found in your message. Please include code in ```code``` blocks."
                return StreamingResponse(
                    generate_openai_compatible_response(error_msg, requested_model_name),
                    media_type="text/plain"
                )
            
            # Create and execute workflow
            workflow = create_code_analysis_workflow()
            
            try:
                # Add user query to context
                code_context["user_query"] = original_user_message
                code_context["conversation_context"] = messages if isinstance(messages, list) else []
                
                # Execute workflow
                workflow_result = await workflow.execute(code_context)
                
                # Format workflow results into a comprehensive response
                response_content = f"""# 🔍 Sequential Code Analysis Results

## Executive Summary
{workflow_result.get('final_context', {}).get('step_6_result', {}).get('executive_summary', 'Analysis completed successfully.')}

## Analysis Steps Completed
"""
                
                # Add step-by-step results
                for step_log in workflow_result.get('execution_log', []):
                    status_emoji = "✅" if step_log['status'] == 'completed' else "❌" if step_log['status'] == 'failed' else "⏭️"
                    response_content += f"{status_emoji} **Step {step_log['step_number']}: {step_log['step_name']}**\n"
                    response_content += f"   {step_log['message']}\n\n"
                
                # Add detailed findings
                final_context = workflow_result.get('final_context', {})
                step_6_result = final_context.get('step_6_result', {})
                
                if step_6_result.get('critical_issues'):
                    response_content += "## 🚨 Critical Issues\n"
                    for issue in step_6_result['critical_issues']:
                        response_content += f"- {issue}\n"
                    response_content += "\n"
                
                if step_6_result.get('improvement_recommendations'):
                    response_content += "## 💡 Recommendations\n"
                    for rec in step_6_result['improvement_recommendations']:
                        response_content += f"- {rec}\n"
                    response_content += "\n"
                
                # Add static analysis details if available
                step_1_result = final_context.get('step_1_result', {})
                if step_1_result.get('linter_output'):
                    response_content += "## 🔍 Static Analysis Details\n"
                    response_content += f"```\n{step_1_result['linter_output']}\n```\n\n"
                
                # Add workflow summary
                response_content += f"""## 📊 Workflow Summary
- **Total Steps**: {workflow_result.get('total_steps', 0)}
- **Executed Steps**: {workflow_result.get('executed_steps', 0)}
- **Successful Steps**: {workflow_result.get('successful_steps', 0)}
- **Failed Steps**: {workflow_result.get('failed_steps', 0)}

*Analysis completed using sequential workflow engine*"""
                
                return StreamingResponse(
                    generate_openai_compatible_response(response_content, requested_model_name),
                    media_type="text/plain"
                )
                
            except Exception as e:
                logger.error(f"❌ Code Analysis Workflow Error: {str(e)}")
                error_msg = f"❌ Code analysis workflow failed: {str(e)}\n\nFalling back to standard agent mode..."
                
                # Fall through to normal agent execution as backup
                use_langchain_agent = True
                logger.info("🔄 Falling back to standard agent mode after workflow failure")
        
        if use_langchain_agent:
            logger.info("🤖 Chat Path: Using Langchain Agent with selected tools.")
            agent_llm_model = requested_model_name 
            
            llm = ChatOllama(
                model=agent_llm_model, 
                base_url=OLLAMA_API_BASE, 
                temperature=float(os.getenv("LLM_TEMPERATURE_AGENT", "0.7"))
            )
            
            # Build tool list based on orchestrator decision
            tools = []
            if use_memory_tools:
                tools.extend([
                    LangchainMemoryContextTool(),
                    LangchainMemorySaveTool(), 
                    LangchainMemoryRuleTool(),
                    LangchainMemoryStatsTool()
                ])
                logger.info("🧠 Added memory tools to agent")
            
            if use_rag_tools:
                tools.append(LangchainFlutterDocTool())
                logger.info("📚 Added RAG tool to agent")
            
            if use_web_search:
                tools.append(LangchainWebSearchTool())
                logger.info("🔍 Added web search tool to agent")
            
            if use_git_tools:
                tools.extend([
                    LangchainGitStatusTool(),
                    LangchainGitDiffTool(),
                    LangchainGitCommitTool(),
                    LangchainGitBranchTool(),
                    LangchainGitLogTool()
                ])
                logger.info("🔧 Added Git tools to agent")
            
            if use_github_tools:
                tools.extend([
                    LangchainGitHubRepoSearchTool(),
                    LangchainGitHubIssuesTool(),
                    LangchainGitHubReleasesTool()
                ])
                logger.info("🐙 Added GitHub tools to agent")
            
            if use_repo_analysis_tools:
                tools.extend([
                    LangchainRepoExploreTool(),
                    LangchainDependencyAnalysisTool(),
                    LangchainCodeMetricsTool()
                ])
                logger.info("📊 Added repository analysis tools to agent")
            
            if use_dev_workflow_tools:
                tools.extend([
                    LangchainPackageSearchTool(),
                    LangchainBuildCommandTool()
                ])
                logger.info("🔧 Added development workflow tools to agent")
            
            if use_auto_linter_tools:
                tools.append(LangchainAutoLinterTool())
                logger.info("🔍 Added auto-linter tool to agent")
            
            if use_sandbox_tools:
                tools.extend([
                    LangchainSandboxExecuteTool(),
                    LangchainSandboxDebugTool(),
                    LangchainSandboxStatsTool()
                ])
                logger.info("🔒 Added sandbox tools to agent")
            
            # Get base ReAct prompt and enhance with memory context
            base_prompt = hub.pull("hwchase17/react")
            user_message = messages[-1]["content"] if messages else ""
            prompt = build_master_prompt_with_memory(base_prompt, user_message)
            
            # Create agent with selected tools
            agent = create_react_agent(llm, tools, prompt)
            agent_executor = AgentExecutor(
                agent=agent, 
                tools=tools, 
                verbose=True, 
                handle_parsing_errors="Check messages and try to recover, or output the parsing error directly to the user."
            )
            
            return StreamingResponse( 
                stream_langchain_agent_response(agent_executor, messages, agent_llm_model, f"chatcmpl-agent-{request_id_base}"), 
                media_type="text/event-stream", 
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*", "X-Accel-Buffering": "no"}
            )
        else:
            logger.info(f"💬 Chat Path: No special tools needed. Using Direct Ollama path with model '{requested_model_name}'.")
            return StreamingResponse( 
                stream_direct_from_ollama(messages, requested_model_name, f"chatcmpl-direct-{request_id_base}"), 
                media_type="text/event-stream", 
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*", "X-Accel-Buffering": "no"}
            )
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Outer chat endpoint error: {e}", exc_info=DEBUG_VERBOSE)
        return JSONResponse(status_code=500, content={"detail": f"Chat processing failed: {str(e)}"})

# --- OpenAI Compatible Endpoints ---
@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_API_BASE}/api/tags")
            response.raise_for_status()
            ollama_models = response.json()
            
            # Convert to OpenAI format
            models = []
            for model in ollama_models.get('models', []):
                models.append({
                    "id": model['name'],
                    "object": "model", 
                    "created": int(time.time()),
                    "owned_by": "ollama"
                })
            
            return {"object": "list", "data": models}
        except Exception as e:
            logger.error(f"Models endpoint error: {e}", exc_info=DEBUG_VERBOSE)
            raise HTTPException(status_code=502, detail="Failed to get models")

@app.post("/v1/chat/completions")
async def chat_completions_v1(request: Request):
    """OpenAI-compatible chat completions endpoint"""
    return await chat_proxy(request)

# --- Memory Management Endpoints ---
@app.get("/memory/stats")
async def memory_stats_endpoint():
    """Direct endpoint for memory statistics"""
    try:
        result = mcp_get_memory_stats()
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Memory stats endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Memory stats failed: {e}")

@app.post("/memory/context")
async def memory_context_endpoint(request: Request):
    """Direct endpoint for memory context retrieval"""
    try:
        request_body = await request.json()
        query = request_body.get("query", "")
        include_long_term = request_body.get("include_long_term", True)
        result = mcp_get_context(query, include_long_term)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Memory context endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Memory context failed: {e}")

# --- Proxy Endpoints & Health ---
@app.get("/api/tags")
async def tags_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if DEBUG_VERBOSE: logger.debug(f"Proxying /api/tags to {OLLAMA_API_BASE}/api/tags")
            response = await client.get(f"{OLLAMA_API_BASE}/api/tags") 
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logger.error(f"Tags proxy error: {e}", exc_info=DEBUG_VERBOSE)
            raise HTTPException(status_code=502, detail="Failed to get model tags from Ollama")

@app.get("/api/ps")
async def ps_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if DEBUG_VERBOSE: logger.debug(f"Proxying /api/ps to {OLLAMA_API_BASE}/api/ps")
            response = await client.get(f"{OLLAMA_API_BASE}/api/ps") 
            response.raise_for_status()
            return JSONResponse(content=response.json() if response.content else {"models": []})
        except Exception as e:
            logger.error(f"Process status proxy error: {e}", exc_info=DEBUG_VERBOSE)
            return JSONResponse(content={"models": []}) 

@app.get("/api/version")
async def version_proxy():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if DEBUG_VERBOSE: logger.debug(f"Proxying /api/version to {OLLAMA_API_BASE}/api/version")
            response = await client.get(f"{OLLAMA_API_BASE}/api/version") 
            response.raise_for_status()
            return JSONResponse(content=response.json())
        except Exception as e:
            logger.error(f"Version proxy error: {e}", exc_info=DEBUG_VERBOSE)
            return JSONResponse(content={"version": "unknown"})

@app.get("/health")
async def health():
    ollama_healthy = False
    ollama_target_for_health = OLLAMA_API_BASE 
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(ollama_target_for_health) 
            ollama_healthy = response.status_code == 200
    except Exception: pass
    
    # Check memory system health
    memory_healthy = False
    try:
        memory_stats = mcp_get_memory_stats()
        memory_healthy = memory_stats.get("status") == "success"
    except Exception: pass
    
    return {
        "status": "healthy" if (ollama_healthy and memory_healthy) else "degraded", 
        "timestamp": time.time(), 
        "default_model": DEFAULT_MODEL, 
        "ollama_status": "healthy" if ollama_healthy else "unreachable",
        "memory_status": "healthy" if memory_healthy else "unavailable",
        "rag_keywords_count": len(RAG_KEYWORDS), 
        "memory_keywords_count": len(MEMORY_KEYWORDS),
        "debug_verbose": DEBUG_VERBOSE
    }

if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8013"))  # Different port from original
    reload_enabled = os.getenv("MCP_RELOAD", "False").lower() == "true"
    uvicorn_log_level = logging.getLevelName(LOG_LEVEL).lower()
    logger.info(f"🚀 Starting Advanced MCP Server with Memory on http://0.0.0.0:{port}")
    uvicorn.run("__main__:app", host="0.0.0.0", port=port, log_level=uvicorn_log_level, reload=reload_enabled)