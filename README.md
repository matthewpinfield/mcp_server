# MCP Server - Local LLM Agent System

An intelligent Model Context Protocol (MCP) server that provides specialized tools and memory integration for local LLM deployment. Acts as middleware between chat clients (e.g. Continue IDE) and Ollama, with intelligent tool routing and sliding-window memory architecture.

## Quick Start

#### RAG Server (Port 8008)
```bash
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
python3 rag/dual_endpoint_server.py
```

#### Main MCP Server (Port 8013)
```bash
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
python3 main.py
```

**Access Points:**
- MCP API: http://localhost:8013
- OpenWebUI: http://localhost:9000
- RAG Search: http://localhost:8008

### Prerequisites
1. **Ollama** running with `gemma4:26b` (main agent + memory summarization) and `nomic-embed-text:latest` (embeddings)
2. **Both servers running**: MCP (8013) + RAG (8008)
3. **Redis** (today's memories) and **MongoDB** (user rules) reachable
4. **Continue IDE configured** to use port 8013 for chat, and the separate `gemma4-direct-edit` model entry for Edit/Apply (see `.continue/models/new-model.yaml`)
5. **Git installed**: `sudo apt install git` (required for the git/GitHub tools)

### Optional GitHub Setup
Set a personal access token in `.env` for higher API rate limits on the GitHub tools:
```bash
GITHUB_TOKEN="ghp_your_token_here"
```

## Features

- **Tool categories**: Memory, RAG (Flutter docs + code examples), Web Search (DuckDuckGo), Git, GitHub, Development helpers, Code Analysis, Sandbox execution, System file access
- **Sliding Window Memory**: Redis (today) -> LanceDB SSD (2-30 days) -> LanceDB NAS (30+ days), with a separate MongoDB-backed Rules system for permanent user preferences
- **OpenAI-compatible API**: `/v1/chat/completions` and `/api/chat`, with streaming
- **LangChain tool-calling agent**: automatic tool selection based on the request, single shared `gemma4:26b` model instance
- **Cursor-style code delivery**: the agent proposes code as a chat block for you to Apply (real inline diff in Continue), rather than silently overwriting files
- **Slash commands**: `/rule`, `/list_rules`, `/delete_rule`, `/change_rule` (rules/preferences management - routed directly, no LLM call)

## Usage Guide

### Memory & Rules
**Triggers**: "remember that...", "add rule", "set preference"
```
Example: "Remember that I prefer concise code explanations"
Action: Stored as a permanent rule via the rules system (MongoDB)
```
Every conversation turn is also automatically saved to the sliding-window memory system without any explicit command - ask about something from an earlier session and the agent will search its memory for it.

### Git Operations
| Trigger phrases | What it does |
|---|---|
| "git status", "check status" | Show modified/staged files, branch info |
| "git diff", "show diff" | Show file changes (staged or unstaged) |
| "git commit", "commit changes" | Create a commit |
| "git branch", "switch branch" | List, create, checkout, or delete branches |
| "git log", "commit history" | Show commit history |

### GitHub Integration
| Trigger phrases | What it does |
|---|---|
| "search github", "find repository" | Search repositories by language/popularity/activity |
| "github issues", "find issues" | List open/closed issues and PRs for a repo |
| "github releases", "latest version" | Get release tags, notes, and download links |

### Repository Analysis
| Trigger phrases | What it does |
|---|---|
| "explore repository", "file tree" | Directory tree, project type detection, file stats (respects `.gitignore`) |
| "analyze dependencies", "check packages" | Reads `package.json`, `pubspec.yaml`, `requirements.txt`, `Cargo.toml`, etc. |
| "code metrics", "project statistics" | Lines of code, language distribution, file sizes |

### Web Search
**Triggers**: "search web", "latest", "current", "recent", "what's new"
```
Example: "Search for the latest stable Python version"
Backend: DuckDuckGo Lite scraping (no API key or cost)
```

### Code Sandbox
| Trigger phrases | What it does |
|---|---|
| "run code", "execute", "test code" | Executes in an isolated Docker sandbox (network-restricted, memory/CPU limited, max 120s timeout) |
| "debug", "verify", "check output" | Runs the code and reports stdout/stderr/timing |
| "calculate", "compute", "solve" | Uses the sandbox for exact calculations |

Note: the sandbox's filesystem (it mounts submitted code at `/code` inside the container) is completely separate from your real filesystem. `read_system_file`, `explore_repository`, and `write_file` operate directly on the real machine and can access any absolute path.

### Development Helpers
| Trigger phrases | What it does |
|---|---|
| "search packages", "find library" | Searches npm, PyPI, pub.dev, crates.io, Maven Central |
| "build project", "run tests" | Detects and runs build/test/lint commands (npm, Flutter, Python, Rust, Maven, Gradle, Make, CMake) |

## How Code Changes Reach Your Editor

There are two entry points, both diff-first (matching how Cursor works - never a silent overwrite):
1. **Chat + Apply**: ask in the Continue side panel; the agent replies with a code block; click **Apply** to get a real inline diff to accept/reject. This uses a separate lightweight completion path (`gemma4-direct-edit` model) that honors Continue's own prompt with no tool-calling overhead.
2. **Inline Edit** (Cmd/Ctrl+I): select code in the editor and describe the change directly - same lightweight path, shown as an inline diff.

The agent's own `write_file` tool is reserved for explicitly-confirmed brand-new file creation, not for editing existing files.

## Usage Patterns

**Typical development workflow:**
1. "What's the git status?"
2. "Explore this repository structure"
3. "Analyze dependencies"
4. "Search web for latest best practices"
5. "Run this code to test the function"
6. "Run tests"
7. "Commit changes with message 'Add tests'"

**Project analysis workflow:**
1. "Analyze the structure of this repository"
2. "Show me code metrics"
3. "Analyze dependencies"
4. "Detect build commands"

## Smart Features

### Automatic Tool Selection
The agent detects intent from your message and picks the right tool - no need to name it explicitly.

### Sliding Window Memory System
- **Redis**: today's discrete conversation turns, automatic context injection
- **LanceDB SSD**: days 2-30, semantic search via `nomic-embed-text` embeddings
- **LanceDB NAS**: 30+ days, archival storage with embeddings
- **Rules System**: MongoDB, permanent user preferences (separate from memory)
- Background summarization (`summary_worker.py`) uses the same `gemma4:26b` instance as the main agent, with thinking disabled, to avoid triggering a VRAM model swap

### Context Status
Check the current model/context configuration:
```bash
curl http://localhost:8013/api/context-status
```

## Troubleshooting

**Git command not found**
- Install Git: `sudo apt install git`, restart the server afterward

**GitHub rate limits**
- Set `GITHUB_TOKEN` in `.env` for higher API rate limits

**Repository not detected**
- Ensure you're in a proper project directory with recognizable project files (`package.json`, `pubspec.yaml`, etc.)

**Build commands not found**
- Ensure the relevant build tools are installed (npm, flutter, etc.)

**Agent feels slow / inconsistent**
- Check `ollama ps` and `nvidia-smi` for VRAM pressure - if a second model gets loaded alongside `gemma4:26b`, Ollama will evict/reload between them on every switch, costing several seconds per turn. Keep everything on `gemma4:26b` unless you've confirmed a second model's VRAM footprint fits comfortably alongside it with headroom to spare.

---

**Tip**: You can combine operations in natural language, e.g. "Check git status and then commit changes with message 'Fix bug'" - the system detects intent and activates the appropriate tools automatically.
