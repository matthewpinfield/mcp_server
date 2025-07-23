Of course. This is an excellent question that gets to the heart of turning a plan into a concrete, organized codebase. Let's map the **MCP Engineering Plan** and the **12 modular tools** onto the recommended file structure.

Here is a clear breakdown of where each component lives and how they interact within the new, organized structure.

---

### New File Structure (Reference)

First, let's re-establish the target file structure we're mapping to:

```
mcp_server_project/
├── rag 
│   └── dual_endpoint_server.py  # The Rag Server Code and Docs DB's the brains
├── main.py                      # FastAPI app startup
├── config.py                    # All configurations, keyword lists
├── api/
│   └── chat.py                  # The /api/chat endpoint
├── core/
│   ├── orchestrator.py          # The "brain" - request routing & tool execution loop
│   ├── workflows.py             # The sequential WorkflowEngine (if needed)
│   └── memory_integration.py    # Functions for prompt enhancement
├── tools/
│   ├── __init__.py              # Makes 'tools' a package
│   ├── base.py                  # The new `AsyncTool` base class
│   ├── git.py                   # GitTool (Unified)
│   ├── github.py                # GitHubTool (Unified)
│   ├── code_analysis.py         # CodeAnalysisTool, RepoStructureTool, PackageSearchTool etc.
│   ├── development.py           # BuildCommandTool, 
│   ├── sandbox.py               # SandboxExecuteTool
│   ├── web.py                   # WebSearchTool
│   └── knowledge.py             # MemoryManagementTool
└── utils/
    ├── __init__.py
    ├── subprocess_helper.py
    └── file_system_helper.py
```

---

### Mapping the MCP Engineering Plan to the File Structure

This shows where the "Core Orchestrator" logic from your plan will reside.

| Engineering Plan Component        | Location in New Structure                             | Description                                                                                                                                                                                          |
| --------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. Request Ingestion & Security** | `main.py` & `api/chat.py`                             | `main.py` starts the server. `api/chat.py` defines the FastAPI endpoint, receives the HTTP request, and performs initial validation (e.g., checking for an empty `messages` list).                  |
| **2. Context Assembly**           | `core/orchestrator.py` & `core/memory_integration.py` | This is a core responsibility of the Orchestrator. The main `route_request` function in `core/orchestrator.py` will call helper functions. The `build_master_prompt_with_memory` function from your original script will live in `core/memory_integration.py` and be called from the orchestrator. The proactive RAG call logic also lives in the orchestrator. |
| **3. The Tool Execution Loop**    | `core/orchestrator.py`                                | This is the absolute central logic of `core/orchestrator.py`. It will contain the `while` loop that sends prompts to the LLM, parses for tool calls, dispatches to the correct tool class, and formats the observation. |
| **4. Response Finalization**      | `api/chat.py`                                         | The orchestrator will return a Python `AsyncGenerator`. The `api/chat.py` endpoint will wrap this generator in a `StreamingResponse` to handle the HTTP streaming mechanics.                 |
| **5. Memory & State Update**      | `core/orchestrator.py`                                | After the tool execution loop finishes and the final answer is generated, the orchestrator in `core/orchestrator.py` will be responsible for calling the `mcp_save_interaction` function.       |

### Mapping the 12 Core Tools to the File Structure

This shows where each of your defined tools will be implemented as Python classes. Each class will inherit from the new `AsyncTool` base class defined in `tools/base.py`.

| Modular Tool                    | Location in New Structure       | Original Class(es) from your script                                                                                                                                                             | Notes                                                                                                                                                         |
| ------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. GitTool (Unified)**        | `tools/git.py`                  | `LangchainGitStatusTool`, `LangchainGitDiffTool`, `LangchainGitCommitTool`, `LangchainGitBranchTool`, `LangchainGitLogTool`                                                                            | These 5 classes will be moved into this single file. You can keep them separate or unify them into one `GitTool` with different methods if you prefer.          |
| **2. CodeAnalysisTool**         | `tools/code_analysis.py`        | `LangchainAutoLinterTool`                                                                                                                                                                       | This tool is for language-specific analysis. It makes sense to group it with other static code analysis tools.                                              |
| **3. RepoStructureTool**        | `tools/code_analysis.py`        | `LangchainRepoExploreTool`                                                                                                                                                                      | Since this analyzes the structure of a repository, it fits perfectly alongside the other code analysis tools.                                               |
| **4. DependencyAnalysisTool**   | `tools/code_analysis.py`        | `LangchainDependencyAnalysisTool`                                                                                                                                                               | Also a form of static code analysis, so it belongs in the same file.                                                                                          |
| **5. CodeMetricsTool**          | `tools/code_analysis.py`        | `LangchainCodeMetricsTool`                                                                                                                                                                      | This is the fourth tool related to static analysis of the codebase. Grouping them keeps related functionality together.                                      |
| **6. BuildCommandTool**         | `tools/development.py`          | `LangchainBuildCommandTool`                                                                                                                                                                     | This tool is more about *executing* development tasks rather than analyzing code. It fits well in a file for general development workflow helpers.            |
| **7. SandboxExecuteTool**       | `tools/sandbox.py`              | `LangchainSandboxExecuteTool`, `LangchainSandboxDebugTool`, `LangchainSandboxStatsTool`                                                                                                         | All sandbox-related tools will go into this dedicated file, referencing the external `mcp_sandbox` module.                                                    |
| **8. WebSearchTool**            | `tools/web.py`                  | `LangchainWebSearchTool`                                                                                                                                                                        | This tool is for external web interaction and should have its own file.                                                                                       |
| **9. PackageSearchTool**        | `tools/development.py`          | `LangchainPackageSearchTool`                                                                                                                                                                    | Similar to the `BuildCommandTool`, this is a development workflow utility, making `tools/development.py` the right home for it.                               |
| **10. GitHubTool (Unified)**    | `tools/github.py`               | `LangchainGitHubRepoSearchTool`, `LangchainGitHubIssuesTool`, `LangchainGitHubReleasesTool`                                                                                                     | All tools that interact with the GitHub API belong in this file.                                                                                              |
| **11. RAGQueryTool**            | `tools/knowledge.py`            | `LangchainFlutterDocTool`                                                                                                                                                                       | This tool is about retrieving knowledge. It makes sense to group it with the Memory tool, as both deal with knowledge and context retrieval.                  |
| **12. MemoryManagementTool**    | `tools/knowledge.py`            | `LangchainMemoryContextTool`, `LangchainMemorySaveTool`, `LangchainMemoryRuleTool`, `LangchainMemoryStatsTool`                                                                                    | These tools provide the agent's interface to the memory system. They belong together, referencing the external `mcp_memory` module for their implementation. |

By organizing your code this way, you create a system that is not only clean and easy to navigate but also directly reflects the logical components outlined in your engineering plan. The "Core Orchestrator" logic is centralized in the `core/` directory, while all the "Core Toolset" capabilities are neatly organized by function within the `tools/` directory.

---

# DEFINITIVE SYSTEM SPECIFICATION

**This section contains the complete technical specification of how the MCP Server actually works. Read this to eliminate all assumptions.**

## SYSTEM ARCHITECTURE OVERVIEW

### DEPLOYMENT TOPOLOGY
```
Port 8013: MCP Server (FastAPI) - Main API endpoint
Port 8008: RAG Server (Flask) - Knowledge retrieval service  
Port 9000: OpenWebUI - Web interface for LLM interaction
Port 11434: Ollama - Local LLM service (qwen3:30b-a3b at 0.7 temperature)
```

### REQUEST FLOW ARCHITECTURE
```
Client Request → FastAPI (api/chat.py) → Orchestrator Analysis → Tool Selection → LangChain Agent → Ollama LLM → Streaming Response
                                      ↓
                               Memory System (3-tier) + RAG System (dual endpoint)
```

## CORE COMPONENTS SPECIFICATION

### 1. REQUEST INGESTION (api/chat.py)
**Function**: OpenAI-compatible `/v1/chat/completions` endpoint
**Input Format**: OpenAI ChatCompletions API format
**Authentication**: None (local deployment)
**Validation**: Message array validation, model parameter handling
**Response**: Server-Sent Events (SSE) streaming in OpenAI format

**Key Functions**:
- `chat_completions()` - Main endpoint handler
- Processes streaming parameter 
- Routes to orchestrator based on message analysis
- Handles both direct Ollama calls and agent-based responses

### 2. REQUEST ORCHESTRATION (core/orchestrator.py)
**Function**: Central intelligence for request routing and tool execution

**Core Analysis Functions**:
- `analyze_tool_needs(user_message)` → Dict - Determines which tool categories are needed
- `should_use_tools(message)` → Boolean - Decides agent vs direct Ollama
- `get_tool_recommendations(message)` → Dict - Returns tool activation map
- `execute_agent_request()` - Runs LangChain ReAct agent with selected tools

**Tool Selection Logic**:
```python
{
    'memory': True/False,     # Context retrieval, rule management
    'rag': True/False,        # Flutter documentation search
    'web_search': True/False, # Google search for current info
    'git': True/False,        # Git operations
    'github': True/False,     # GitHub API operations
    'dev_workflow': True/False, # Build commands, package search
    'repo_analysis': True/False, # Code analysis, metrics
    'auto_linter': True/False,   # Code linting
    'sandbox': True/False        # Code execution
}
```

**Agent Integration**: Uses LangGraph `create_react_agent` with automatic tool binding

### 3. TOOL SYSTEM (tools/ directory)

#### Tool Categories (9 Total):
1. **Memory Tools** (`tools/knowledge.py`)
   - `LangchainMemoryContextTool` - Retrieves conversation context
   - `LangchainMemorySaveTool` - Saves interactions to memory
   - `LangchainMemoryRuleTool` - Manages user rules/preferences
   - `LangchainMemoryStatsTool` - Memory system diagnostics

2. **RAG Tools** (`tools/knowledge.py`) 
   - `LangchainFlutterDocTool` - Flutter documentation search
   - `LangchainCodeSearchTool` - Code example search

3. **Web Search** (`tools/web.py`)
   - `LangchainWebSearchTool` - Google search with domain prioritization

4. **Git Tools** (`tools/git.py`)
   - `LangchainGitStatusTool`, `LangchainGitDiffTool`, `LangchainGitCommitTool`, `LangchainGitBranchTool`, `LangchainGitLogTool`

5. **GitHub Tools** (`tools/github.py`) 
   - `LangchainGitHubIssuesTool` - Repository issue management
   - `LangchainGitHubReleasesTool` - Release information

6. **Development Tools** (`tools/development.py`)
   - `LangchainBuildCommandTool`, `LangchainPackageSearchTool`, `LangchainDateTimeTool`, `LangchainSystemFileReaderTool`

7. **Code Analysis** (`tools/code_analysis.py`)
   - `LangchainAutoLinterTool`, `LangchainRepoExploreTool`, `LangchainDependencyAnalysisTool`, `LangchainCodeMetricsTool`

8. **Sandbox Tools** (`tools/sandbox.py`)
   - `MultiLanguageSandboxTool` - Docker-based code execution
   - `SandboxStatsTool` - Execution environment stats

9. **System Tools** (`tools/development.py`)
   - File system operations, system information

#### Tool Base Class (`tools/base.py`)
All tools inherit from `AsyncTool` base class with standardized interface:
- `name`: Tool identifier
- `description`: LLM-readable tool purpose  
- `args_schema`: Pydantic schema for parameters
- `_run()`: Core execution method

## DATA STORAGE SPECIFICATION

### 3-TIER MEMORY ARCHITECTURE

#### Tier 1: Redis (Fast/Recent)
**Purpose**: Session context, recent interactions (14-day TTL)
**Location**: Local Redis instance
**Key Pattern**: `interaction:{interaction_id}`
**Data Format**:
```json
{
  "text": "formatted conversation text",
  "metadata": {"timestamp": "ISO8601", "user_id": "default", "interaction_id": "unique_id"},
  "messages": [{"role": "user/assistant", "content": "message"}],
  "timestamp": "ISO8601"
}
```

#### Tier 2: MongoDB (Persistent Rules)
**Purpose**: User rules, preferences, corrections
**Location**: Local MongoDB instance
**Collections**:
- `profiles` - User preferences and rules
- `correction_logs` - AI correction tracking

**Profile Schema**:
```json
{
  "user_id": "default",
  "rules": [{"rule": "text", "category": "preference", "added_at": "datetime", "id": "hash"}],
  "preferences": {}
}
```

#### Tier 3: ChromaDB (Semantic Memory)
**Purpose**: Long-term semantic search of conversations
**Location**: Local ChromaDB instance (`/mnt/caseSSD/mcp_server_project/chroma_data/`)
**Migration**: Redis → ChromaDB after 14 days
**Query**: Vector similarity search for conversation context

### RAG SYSTEM DATA

#### LanceDB Vector Storage
**Location**: `/mnt/caseSSD/mcp_server_project/lancedb_data/`
**Databases**:
1. `flutter_dart_knowledge.lance` - Flutter/Dart documentation (~8.5k documents)
2. `expert_py_flutter_dart_final.lance` - Code examples (~8.5k documents)

#### RAG Server (rag/dual_endpoint_server.py)
**Port**: 8008
**Endpoints**:
- `/search/docs` - Documentation search
- `/search/code` - Code example search  
**Embedding Model**: Ollama embeddings via local API
**Response Format**: JSON with documents, relevance scores, metadata

## CONFIGURATION SPECIFICATION

### Primary Config (config.py)
```python
OLLAMA_API_BASE = "http://localhost:11434"
RAG_SERVER_ENDPOINT = "http://localhost:8008/search/docs"
DEFAULT_MODEL = "qwen3:30b-a3b"
MAX_WORKERS = 3
DEFAULT_USER = "default"
```

### Model Configuration
- **qwen3:30b-a3b**: Primary LLM model
- **Temperature**: 1.0 for for thinking and 0.4 for coding
- **Thinking Mode**: qwen3 supports `<think></think>` blocks (stripped from output)

### Tool Selection Keywords (config.py)
Each tool category has associated keywords that trigger activation:
- Memory: "remember", "recall", "previous", "context"
- RAG: "flutter", "dart", "widget", "documentation"  
- Web: "search", "latest", "current", "news", "weather"
- Git: "git", "commit", "branch", "diff", "status"
- GitHub: "github", "repository", "issue", "release"
- Sandbox: "run", "execute", "code", "test", "python"

## INTEGRATION SPECIFICATIONS

### OpenAI API Compatibility
**Endpoint**: `/v1/chat/completions`
**Supported Parameters**:
- `messages`: Required message array
- `model`: Model selection (maps to Ollama models)
- `stream`: Boolean for streaming response
- `temperature`: Model temperature override

**Response Format**: OpenAI ChatCompletions format with proper SSE streaming

### LangChain Integration  
**Agent Type**: ReAct (Reasoning + Acting)
**Tool Binding**: Automatic via LangGraph `create_react_agent`
**Prompt Template**: Custom ReAct prompt with tool descriptions
**Memory Integration**: Conversation context injected into agent prompt

### External Service Dependencies
**Required**:
- Ollama service (port 11434) with qwen3:30b-a3b model
- RAG server (port 8008) - rag/dual_endpoint_server.py

**Optional** (graceful degradation):
- Redis (Tier 1 memory)
- MongoDB (Tier 2 memory)  
- ChromaDB (Tier 3 memory)
- Docker (sandbox execution)

## OPERATIONAL SPECIFICATIONS

### Startup Sequence
1. `main.py` initializes FastAPI app
2. Dependency validation (Ollama, RAG server)
3. ThreadPoolExecutor initialization (MAX_WORKERS=3)
4. Memory system initialization (3-tier)
5. Tool loading and validation
6. Server startup on port 8013

### Error Handling
- Graceful degradation for optional services
- Tool execution timeout handling
- Memory system fallbacks (Tier 1 → Tier 2 → Tier 3)
- Ollama connection retry logic

### Monitoring & Diagnostics
- Health check endpoint: `/health`
- Memory stats via `LangchainMemoryStatsTool`
- Tool execution logging
- Request/response tracing

### Performance Characteristics
- **Tool Selection**: < 100ms analysis time
- **Memory Retrieval**: Tier 1 (Redis) < 10ms, Tier 3 (ChromaDB) < 500ms
- **RAG Search**: < 2s for documentation queries
- **Streaming Response**: Real-time SSE delivery
- **Concurrent Requests**: ThreadPoolExecutor manages parallel tool execution

## SLASH COMMAND SYSTEM

### Command Processing (`tools/knowledge.py`)
**Function**: `process_slash_command(command, args, custom_commands)`

**Built-in Commands**:
- `/remember` - Save information to memory
- `/recall` - Retrieve memory context  
- `/rule` - Add permanent user rule
- `/list_rules` - Show current rules
- `/correct` - Add AI correction
- `/no_think` - Disable thinking mode

**Implementation**: Commands bypass normal tool selection and directly invoke memory functions

## DEPLOYMENT NOTES

### File System Layout
```
/mnt/caseSSD/mcp_server_project/
├── main.py (FastAPI server)
├── config.py (configuration) 
├── api/chat.py (HTTP endpoint)
├── core/orchestrator.py (request routing)
├── tools/ (9 tool modules)
├── rag/dual_endpoint_server.py (knowledge server)
├── lancedb_data/ (vector databases)
├── chroma_data/ (semantic memory)
└── .venv/ (Python virtual environment)
```

### External Integrations
- **Continue IDE**: Primary development environment integration
- **OpenWebUI**: Web interface (port 9000)
- **Direct HTTP**: RESTful API for custom clients

### Security Considerations
- Local deployment only (no external authentication)
- File system access limited to project directory
- Docker sandbox isolation for code execution  
- No external API key requirements (uses local Ollama)

---

**This specification is the definitive truth of how the MCP Server operates. All assumptions should be verified against this document.**