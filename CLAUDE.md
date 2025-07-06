# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Rules
IMPORTANT!! THIS IS FIRST RULE: Don't assume anything
Use clear, concise trains of thought
Use websearch to ensure to pass 100% true facts
Always use todo lists to break down tasks into smaller bites
Adhere strictly to MVP adadapt files dont create new
NO new files to be added to the exiting file structure 
The Project runs within a .venv
Take small steps when planning code changes
Create duplicate to keep files from further damage
Create test files to check the fix before suggesting its a permanent fix.     
/superceeded has code from before the main code of 5000 lines was split into its current form. it is a good source of good code.


## Development Commands

### Start the MCP Server
```bash
python main.py
```
The server will start on port 8013 and perform dependency checks for Ollama and RAG services.

### Start the RAG Server (required dependency)
```bash
cd rag/
python dual_endpoint_server.py
```
This starts the RAG service on port 8008 with dual endpoints for Flutter docs and code examples.

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Testing
No formal test framework is configured. Test functionality through the API endpoints.

### Linting/Code Quality
No automated linting is configured. Follow Python best practices and existing code style.

## Architecture Overview

This is an **MCP (Model Context Protocol) Server** that provides an intelligent agent system with specialized tools for development workflows. It acts as a middleware layer between chat clients and Ollama LLM, with intelligent tool routing and memory integration.

### Core Components

1. **FastAPI Server** (`main.py`)
   - Main entry point with health checks and dependency validation
   - Validates Ollama service and model availability on startup
   - Manages ThreadPoolExecutor for tool operations

2. **Chat API** (`api/chat.py`)
   - Primary `/api/chat` endpoint handling OpenAI-compatible requests
   - Intelligent routing between direct Ollama and agent-based responses
   - Streaming response support with proper OpenAI format
   - Slash command processing for quick actions

3. **Orchestrator** (`core/orchestrator.py`)
   - Request analysis and tool recommendation engine
   - Contains `should_use_*` functions for each tool category
   - Agent execution with ReAct pattern using LangChain
   - Automatic memory saving for all interactions

4. **RAG System** (`rag/dual_endpoint_server.py`)
   - Dual-endpoint design: `/search/docs` for Flutter documentation, `/search/code` for code examples
   - LanceDB vector storage with ~17k documents total
   - Ollama embeddings integration for semantic search

5. **Memory System** (3-tier architecture via `tools/knowledge.py`)
   - **Tier 1**: Redis (session context, recent interactions)
   - **Tier 2**: MongoDB (rules, preferences, long-term patterns)  
   - **Tier 3**: ChromaDB (semantic memory, conversation history)

### Tool Categories

The system intelligently activates tool categories based on message analysis:

- **Memory Tools**: Context retrieval, rule management, interaction saving
- **RAG Tools**: Flutter documentation and code example search
- **Web Search**: Google search for current information
- **Git Tools**: Status, diff, commit, branch operations
- **GitHub Tools**: Repository search, issues, releases
- **Development Tools**: Package search, build commands, date/time
- **Code Analysis**: Linting, repository exploration, metrics
- **Sandbox Tools**: Multi-language code execution

### Configuration

Primary configuration in `config.py` with environment variable support:

- `OLLAMA_API_BASE`: Ollama server URL (default: http://localhost:11434)
- `RAG_SERVER_ENDPOINT`: RAG service URL (default: http://localhost:8008/search/docs)  
- `DEFAULT_MODEL`: Default Ollama model (default: qwen3:30b-a3b)
- `MAX_WORKERS`: Thread pool size (default: 3)

YAML configuration in `mcp_config.yaml` for centralized settings.

### Request Flow

1. **Request Analysis**: Orchestrator analyzes user message for tool requirements
2. **Tool Selection**: Based on keywords and patterns, activates relevant tool categories
3. **Execution Path**:
   - **Direct**: No tools needed → Direct Ollama streaming
   - **Agent**: Tools needed → ReAct agent with selected tools
4. **Memory Integration**: All interactions automatically saved to 3-tier memory system
5. **Response**: Streaming response in OpenAI-compatible format

### Memory & Context Management

- **Automatic Saving**: All conversations saved without user action
- **Identity Rules**: System retrieves user preferences/rules for consistent behavior
- **Slash Commands**: Quick access to memory operations (`/remember`, `/recall`, `/rule`)
- **Context Retrieval**: Relevant past context automatically included in agent prompts

### External Dependencies

- **Ollama**: Required LLM service with specified model availability
- **RAG Service**: Must be running on port 8008 for knowledge retrieval
- **Redis**: Optional Tier 1 memory (degrades gracefully)
- **MongoDB**: Optional Tier 2 memory (degrades gracefully)  
- **ChromaDB**: Optional Tier 3 memory (degrades gracefully)

### Integration Points

- **OpenAI-Compatible API**: `/v1/chat/completions` endpoint for standard clients
- **Continue IDE**: Primary integration target with streaming support
- **OpenWebUI**: Secondary integration with proper model listing
- **Direct HTTP**: RESTful API for custom integrations

The system is designed for production deployment with proper error handling, logging, and graceful degradation when optional services are unavailable.