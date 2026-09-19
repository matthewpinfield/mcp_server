#!/usr/bin/env python3
"""
Configuration module for Advanced MCP Server
Centralized configuration management for all environment variables and settings
"""

import logging
import os

# --- Environment Variables Configuration ---
RAG_SERVER_ENDPOINT = "http://localhost:8008/search/docs"
RAG_CODE_ENDPOINT = "http://localhost:8008/search/code"
OLLAMA_API_BASE = "http://localhost:11434"
OLLAMA_OPENAI_BASE = "http://localhost:11434/v1"
DEFAULT_MODEL = "gemma4:26b"
temperature = 0.8  # Higher temperature for thinking models

MAX_WORKERS = 3
REQUEST_TIMEOUT = 180
LANGCHAIN_AGENT_TIMEOUT = 900  # raised from 240s to allow long autonomous multi-file build turns
DIRECT_OLLAMA_TIMEOUT = 180


# Server configuration
MCP_SERVER_HOST = "0.0.0.0"
MCP_SERVER_PORT = 8013
DEBUG_VERBOSE = False

# Logging configuration
LOG_LEVEL = logging.DEBUG if DEBUG_VERBOSE else logging.INFO

# API Keys
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# --- RAG Keywords Configuration ---
DEFAULT_RAG_KEYWORDS = "flutter,dart,widget,state management,navigation,routing,buildrunner,firebase,api,documentation,code example,debug,error,fix,how to,what is,explain"
RAG_KEYWORDS_STR = DEFAULT_RAG_KEYWORDS
RAG_KEYWORDS = [
    keyword.strip().lower()
    for keyword in RAG_KEYWORDS_STR.split(",")
    if keyword.strip()
]

# --- Tool Activation Keywords ---

# Memory-specific configuration
MEMORY_KEYWORDS = [
    "remember",
    "recall",
    "forget",
    "save this",
    "memory",
    "context",
    "history",
    "previous",
    "earlier",
    "before",
    "add rule",
    "permanent rule",
    "prefer",
    "rule",
    "permanent",
    "store",
]
PROGRAMMING_LANGUAGES = [
    "python",
    "dart",
    "flutter",
    "javascript",
    "typescript",
    "java",
    "c++",
    "c#",
    "rust",
    "go",
    "php",
    "ruby",
]
PROGRAMMING_DOMAINS = [
    "api",
    "backend",
    "frontend",
    "mobile",
    "web",
    "database",
    "devops",
    "machine learning",
    "ai",
]

# Web search configuration
WEB_SEARCH_KEYWORDS = [
    "search",
    "look up",
    "find information",
    "what's new",
    "latest",
    "recent",
    "news",
    "current",
    "today",
    "2024",
    "2025",
    "google",
    "web search",
    "online",
]

# Dynamic Web Search Configuration (MVP Optimization)
WEB_SEARCH_MAX_RESULTS = 5  # Legacy default - kept for compatibility
WEB_SEARCH_SIMPLE_QUERIES = 3  # Simple questions
WEB_SEARCH_COMPLEX_QUERIES = 8  # Technical/debugging queries
WEB_SEARCH_RESEARCH_QUERIES = 12  # Deep research queries
WEB_SEARCH_TIMEOUT_OPTIMIZED = 45  # Reduced from 60s
WEB_CONTENT_LENGTH_ENHANCED = 1200  # Increased from 800 chars

# Git/GitHub configuration
GIT_KEYWORDS = [
    "git",
    "commit",
    "push",
    "pull",
    "branch",
    "merge",
    "checkout",
    "status",
    "diff",
    "log",
    "clone",
    "repository",
    "repo",
]
GITHUB_KEYWORDS = [
    "github push",
    "github pull",
    "create pr",
    "create pull request",
    "open pr",
    "github merge",
    "github issue",
    "create issue",
    "github release",
    "publish release",
    "github workflow",
    "github actions",
]
DEV_WORKFLOW_KEYWORDS = [
    "build",
    "test",
    "lint",
    "format",
    "deploy",
    "ci",
    "cd",
    "pipeline",
    "package",
    "dependency",
    "date",
    "time",
    "today",
    "day",
    "what day",
    "current date",
    "current time",
    "datetime",
    "calendar",
]

# Repository analysis configuration
REPO_ANALYSIS_KEYWORDS = [
    "explore",
    "analyze",
    "structure",
    "dependencies",
    "metrics",
    "code analysis",
    "project analysis",
    "file tree",
    "repository structure",
]

# Development helpers configuration
PACKAGE_SEARCH_KEYWORDS = [
    "package",
    "library",
    "npm",
    "pip",
    "pub",
    "cargo",
    "maven",
    "search packages",
    "find library",
]
BUILD_COMMAND_KEYWORDS = [
    "build",
    "test",
    "lint",
    "format",
    "deploy",
    "ci",
    "cd",
    "pipeline",
    "run command",
    "execute",
]

# Auto-linter configuration
AUTO_LINTER_KEYWORDS = [
    "lint",
    "analyze code",
    "flutter analyze",
    "dart fix",
    "eslint",
    "prettier",
    "auto fix",
    "format code",
    "code quality",
    "style check",
]

# Sandbox configuration
SANDBOX_KEYWORDS = [
    "run code",
    "execute",
    "test code",
    "debug",
    "verify",
    "check output",
    "sandbox",
    "python",
    "calculate",
    "what does this code do",
    "run this",
    "execute this",
]
CALCULATION_KEYWORDS = [
    "calculate",
    "compute",
    "math",
    "mathematics",
    "solve",
    "equation",
    "formula",
    "sum",
    "average",
    "statistics",
]

# --- Dynamic RAG Configuration (MVP Optimization) ---
RAG_RESULTS_SIMPLE = 3  # Basic queries (greetings, simple questions)
RAG_RESULTS_STANDARD = 5  # Current default - maintained for compatibility
RAG_RESULTS_COMPLEX = 8  # Technical/debugging queries
RAG_RESULTS_RESEARCH = 15  # Deep research, architecture questions
RAG_CONTENT_LENGTH_ENHANCED = 1200  # Increased from 800 chars

# --- Enhanced Memory Configuration (MVP Optimization) ---
TIER1_INTERACTIONS_ENHANCED = 8  # Increased from 5
TIER2_RULES_ACTIVE_ENHANCED = 15  # Increased from 10
TIER3_SEMANTIC_ENHANCED = 8  # Increased from 5
MEMORY_CONTEXT_LENGTH_ENHANCED = 200  # Increased from 150 chars

# --- Safe Fallback Configuration ---
ENABLE_DYNAMIC_SCALING = True  # Set to False to revert to original limits
AGENT_RESPONSE_TIMEOUT_WARNING = 25  # Warn if response takes >25s
CONTEXT_SIZE_WARNING_THRESHOLD = 5000  # Warn if context >5k chars


# Memory Retrieval Settings
MEMORY_RETRIEVAL_LIMIT = 3  # Number of memories to retrieve
MEMORY_SUMMARY_MAX_TOKENS = 500  # Max tokens for summary
MEMORY_CONTEXT_MAX_TOKENS = 1000  # Max tokens for final context

# Database Base Path - All databases use direct file paths
DATABASE_BASE_PATH = "/mnt/caseSSD/mcp_server_data"

# Redis Configuration - Maintain existing variable names, point to data directory
REDIS_DATA_PATH = os.path.join(DATABASE_BASE_PATH, "redis_data")
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_TIMEOUT = 5

# MongoDB Configuration - Maintain existing variable names, use existing service with data path
MONGODB_DATA_PATH = os.path.join(DATABASE_BASE_PATH, "tier2_mongodb")
MONGODB_URI = "mongodb://localhost:27017/"
MONGODB_DATABASE = "mcp_memory"

# LanceDB Configuration
LANCEDB_TIER3_PATH = "/mnt/caseSSD/mcp_server_data/tier3_memory_db"
LANCEDB_NAS_PATH = "/mnt/my_nas_mcp_share/archives/lancedb_archive"

# Embedding Model
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text:latest"

# Memory System Constants
DEFAULT_USER = "default_user"

# 3-Step Memory Quality Targets
MEMORY_QUALITY_TARGET = 9.0  # Target quality score (out of 10)
MEMORY_FALLBACK_DISABLED = True  # FAIL FAST - no fallback to old system

# --- Slash Commands Configuration ---
DEFAULT_SLASH_COMMANDS = {
    # Memory Management
    "/rule": {
        "description": "Add a new rule or to memory",
        "usage": "/rule <rule_text>",
        "example": "/rule I prefer detailed code explanations",
        "category": "memory",
        "action": "save_rule",
    },
    "/recall": {
        "description": "Retrieve information from memory",
        "usage": "/recall <query>",
        "example": "/recall state management rules",
        "category": "memory",
        "action": "get_memory",
    },
    "/forget": {
        "description": "Remove information from memory",
        "usage": "/forget <query>",
        "example": "/forget old project rules",
        "category": "memory",
        "action": "delete_memory",
    },
    "/correct": {
        "description": "Correct the AI's last response for future learning",
        "usage": "/correct <correction_text>",
        "example": "/correct Actually, use async/await instead of .then()",
        "category": "memory",
        "action": "correct",
    },
    "/fix": {
        "description": "Fix the AI's last response (alias for /correct)",
        "usage": "/fix <correction_text>",
        "example": "/fix The correct syntax is setState(() => ...)",
        "category": "memory",
        "action": "fix",
    },
    "/list_rules": {
        "description": "List rules with optional search filter",
        "usage": "/list_rules [search_term]",
        "example": "/list_rules coding",
        "category": "memory",
        "action": "list_rules",
    },
    "/delete_rule": {
        "description": "Delete rule by ID",
        "usage": "/delete_rule <rule_id>",
        "example": "/delete_rule ab12cd34",
        "category": "memory",
        "action": "delete_rule",
    },
    "/change_rule": {
        "description": "Update rule by ID",
        "usage": "/change_rule <rule_id> <new_text>",
        "example": "/change_rule ab12cd34 I prefer Vue",
        "category": "memory",
        "action": "change_rule",
    },
    # Development Workflow
    "/build": {
        "description": "Quick build command detection and execution",
        "usage": "/build [command]",
        "example": "/build test",
        "category": "development",
        "action": "build_command",
    },
    "/package": {
        "description": "Quick package search",
        "usage": "/package <ecosystem> <query>",
        "example": "/package npm react-router",
        "category": "development",
        "action": "package_search",
    },
    "/analyze": {
        "description": "Quick repository analysis",
        "usage": "/analyze [type]",
        "example": "/analyze structure",
        "category": "development",
        "action": "repo_analysis",
    },
    # Git Operations
    "/status": {
        "description": "Quick git status check",
        "usage": "/status",
        "example": "/status",
        "category": "git",
        "action": "git_status",
    },
    "/commit": {
        "description": "Quick git commit",
        "usage": "/commit <message>",
        "example": "/commit Fix authentication bug",
        "category": "git",
        "action": "git_commit",
    },
    "/branch": {
        "description": "Git branch operations",
        "usage": "/branch [action] [name]",
        "example": "/branch create feature-auth",
        "category": "git",
        "action": "git_branch",
    },
    # System Commands
    "/commands": {
        "description": "List available slash commands",
        "usage": "/commands [category]",
        "example": "/commands memory",
        "category": "system",
        "action": "list_commands",
    },
    "/help": {
        "description": "Get help for a specific command",
        "usage": "/help <command>",
        "example": "/help /remember",
        "category": "system",
        "action": "command_help",
    },
    "/add-command": {
        "description": "Add a custom slash command",
        "usage": "/add-command <name> <description> <action>",
        "example": "/add-command /deploy 'Deploy to prod' deploy_prod",
        "category": "system",
        "action": "add_custom_command",
    },
    "/remove-command": {
        "description": "Remove a custom slash command",
        "usage": "/remove-command <name>",
        "example": "/remove-command /deploy",
        "category": "system",
        "action": "remove_custom_command",
    },
    "/memories": {
        "description": "Show all memories (rules, context, interactions)",
        "usage": "/memories [search_term]",
        "example": "/memories coding",
        "category": "memory",
        "action": "show_all_memories",
    },
    # Project Management
    "/context": {
        "description": "Show current session context",
        "usage": "/context",
        "example": "/context",
        "category": "project",
        "action": "show_context",
    },
    "/project": {
        "description": "Set current project information",
        "usage": "/project [name] [description]",
        "example": "/project MyApp 'Flutter e-commerce app'",
        "category": "project",
        "action": "set_project",
    },
}

# --- LLM Instance Caching ---
# Cached LLM instances to avoid repeated model loading per request
_llm_cache = {}


def get_cached_llm(model_name: str):
    """
    Get cached LLM instance or create new one if not exists.
    Implements singleton pattern to avoid loading same model multiple times.
    """
    if model_name not in _llm_cache:
        from langchain_ollama import ChatOllama

        logging.getLogger(__name__).info(
            f"Creating new LLM instance for model: {model_name}"
        )
        _llm_cache[model_name] = ChatOllama(
            model=model_name, base_url=OLLAMA_API_BASE, timeout=LANGCHAIN_AGENT_TIMEOUT
        )
    else:
        logging.getLogger(__name__).debug(
            f"Using cached LLM instance for model: {model_name}"
        )
    return _llm_cache[model_name]
