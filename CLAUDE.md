# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Rules
1. IMPORTANT!! THIS IS FIRST RULE: Don't assume anything
2. be polite and remember you are the assistant so dont swear.. ever..
3. you cannot use the sudo command so ask the user to run the command and repoert back 
4. Use clear, concise trains of thought
5. Use websearch to ensure to pass 100% true facts
6. Always use claude_todo.md to maintain a constant non memory reliant list. 
7. Adhere strictly to MVP principles
8. NO new files to be added to the exiting file structure unless approved, this exludes backups and test files
9. Do not alter a existing file, use a sandbox protocol and create and test from back ups not original files.  Create an .md that lists all changes made so we can always go back. 
10. The Project runs within a .venv
11. Take small steps when planning code changes    
12. The /superceeded folder has code from before the main code of 5000 lines was split into its current form,  it is a good source of good code.
13. a fix is never ready till its tested against its actual purpose, example does it actually search the internet, recall a memory.
14. confirming a file does not crash on startup is not the same as testing if the fix actually works.. see ## Proven Issue Resolution Methodology
15. DO NOT WAIT MORE THAN 10 SECONDS BETWEEN SERVER STARTUP AND TEST CODE EXECUTION. THIS IS TIME WASTING, ANNOYING AND POINTLESS
16. IMPORTANT DO NOT END CONVERSATIONS TELLING THE USER SOMETHING DOES NOT WORK OR IS BROKEN AS THIS IS 100% WRONG, END YOU CONVERSATIONS IF YOU FIND AN ERROR WITH A PROPOSED FIX ONCE YOU HAVE SEARCHED FOR ONLINE FOR THE DEFINETIVE ANSWER. 
17. you are a highly experienced coding agent you are the best at code generation and debugging, you adhere to best principles of coding and always adhere to mvp conduct.
18. use you internal websearch tool to always look for the most recent 2025 solution as this is newer than your training date. 
use you internal websearch tool to always look for the most recent 2025 solution as this is newer than your training date. use small incremental changes to code and test, do not change huge chuncks of code. ensure all existing functions name remain the same during refactoring. use your linter tools as you code to keep code clean.
19. use ALL linter tools as you code to keep code clean.
20. use claude_todo.md as a permanent todo list use this rather than the inline chat version. this ensure you do not forget across sessions.


## Program Structure IMPORTANT YOU NEED TO UNDERSTAND THIS BEFORE ATTEMPTING TO WRITE ANY CODE. 

mcp_server_project/
├── rag 
│   └── dual_endpoint_server.py  # The Rag Server Code and Docs DB's the brains
├── main.py                      # FastAPI app startup
├── config.py                    # All configurations, keyword lists
├── api/
│   └── chat.py                  # The /api/chat endpoint
├── core/
│   ├── orchestrator.py          # The "brain" - request routing & tool execution loop
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
    └── base_tool.py


## Development Commands

### 1. Start the RAG Server (required dependency)
```bash
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
python3 rag/dual_endpoint_server.py
```
### 2. Start the Main Server
```bash
# This starts the RAG service on port 8008 with dual endpoints for Flutter docs and code examples.### Start the MCP Server
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
python3 main.py
```
The server will start on port 8013 and perform dependency checks for Ollama and RAG services.


### Install Dependencies
```bash
pip install -r requirements.txt # the rag has its own requirements.txt
```

### Testing
No formal test framework is configured. Test functionality through the API endpoints.

### Linting/Code Quality
No automated linting is configured. Use all the tools we have installed within the codebase.

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

5. **Memory System** (Sliding window architecture via `tools/memory.py`)
   - **Redis**: Today's memories only (discrete turns, not accumulated conversations)
   - **LanceDB SSD**: Days 2-30 (with embeddings for semantic search)
   - **LanceDB NAS**: 30+ days (archival with embeddings)
   - **Rules System**: MongoDB via `tools/rules.py` (separate from memory)

   Daily batch transfer moves memories from Redis → LanceDB SSD → LanceDB NAS.
   Each conversation turn is stored as separate memory (no exponential growth).
   Agent gets automatic context from recent memories without searching. 

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

- **See config.py** 


### Memory & Context Management

- **Automatic Saving**: All conversations saved without user action
- **Identity Rules**: System retrieves user rules for consistent behavior
- **Slash Commands**: Quick access to memory operations (`/remember`, `/recall`, `/rule`)
- **Context Retrieval**: Relevant past context automatically included in agent prompts

### External Dependencies

- **Ollama**: Required LLM service with specified model availability
- **RAG Service**: Must be running on port 8008 for knowledge retrieval
- **Redis**: Today's discrete memories  
- **MongoDB**: User rules (separate system)
- **LanceDB**: Historical memories with embeddings (SSD + NAS)

### Integration Points

- **OpenAI-Compatible API**: `/v1/chat/completions` endpoint for standard clients
- **Continue IDE**: Primary integration target with streaming support
- **OpenWebUI**: Secondary integration with proper model listing Port 9000
- **Direct HTTP**: RESTful API for custom integrations

The system is designed for production deployment with proper error handling, logging, and graceful degradation when optional services are unavailable.

## Proven Issue Resolution Methodology

**How to Fix Complex Issues (Learned from Tool Fix Session):**

### 1. **Real Functional Testing vs Existence Testing**
- Never test if something "exists" - test if it actually **works**
- Use specific, verifiable test cases with expected answers:
 - If you can't verify the answer is correct, the test is useless

### 2. **One Thing At A Time (Critical Rule)**
- Fix **exactly one** specific issue
- Test that **one** fix immediately  
- Only move to next issue after current one is **completely working**
- Never try to "fix everything at once"

### 3. **Todo Lists for Micro-Management**
- Break overwhelming problems into tiny, manageable chunks
- Each todo item should be completable in one focused session
- Mark as completed **only when actually verified working**
- Example: "Fix Memory tool - key pattern mismatch" not "Fix memory system"

### 4. **Forced Verification at Each Step**
The pattern that works:
1. Identify **specific** issue (not vague problem)
2. Make **minimal** fix (change only what's needed)
3. Test **immediately** with real functionality test
4. Mark completed **only if actually working**

### 5. **Distinguish Between Types of Failures**
- **Existence failure**: "Class won't load" 
- **Functional failure**: "Tool runs but gives wrong answer"
- **Logic failure**: "Tool works but test expectations are wrong"
- **Architecture failure**: "Using wrong tool for the task"

### 6. **Key Success Factors**
- **Harsh feedback loops**: If something doesn't work, call it broken immediately
- **Specific examples**: Use real-world test cases with verifiable outcomes  
- **No assumption**: Just because code runs doesn't mean it works correctly
- **Immediate testing**: Test every change before moving on

**Remember**: The difference between despair and success is methodical, verified progress rather than assumed progress.
