# MCP Server

A Model Context Protocol (MCP) server that sits between chat clients and a local [Ollama](https://ollama.com) LLM, adding tool use, retrieval-augmented generation, and persistent memory on top of a plain chat model.

It exposes an OpenAI-compatible chat API, so it works as a drop-in backend for tools like [Continue](https://continue.dev) or [OpenWebUI](https://github.com/open-webui/open-webui), while transparently deciding when a request needs a tool (git, GitHub, web search, code execution, documentation lookup, etc.) versus a direct model response.

## How it works

1. **Request comes in** via `/api/chat` or the OpenAI-compatible `/v1/chat/completions`.
2. **Orchestrator** (`core/orchestrator.py`) analyzes the message and decides which tools, if any, are relevant.
3. **Tool execution loop** runs a ReAct-style agent when tools are needed, or streams a direct response from Ollama when they aren't.
4. **Memory system** automatically saves the interaction and retrieves relevant past context for future requests.
5. **Response** streams back in OpenAI-compatible format.

```
Client → api/chat.py → core/orchestrator.py → [tools/*.py]  → Ollama
                                            → tools/knowledge.py (memory + RAG)
```

## Features

- **OpenAI-compatible API** — works with `/api/chat`, `/v1/chat/completions`, `/v1/completions`, `/v1/models`
- **RAG integration** — dual-endpoint retrieval service for documentation and code examples (`rag/dual_endpoint_server.py`), backed by LanceDB
- **Three-tier memory** — Redis (session/recent), MongoDB (rules/preferences), ChromaDB (semantic long-term memory), with graceful degradation if any tier is unavailable
- **Tool categories** — git, GitHub, code analysis, dependency/package search, sandboxed code execution, web search, and knowledge/memory tools
- **Slash commands** — quick actions like `/remember`, `/recall`, `/rule`, `/status`, `/commit` (see `Slash_Commands_Guide.md`)

## Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com) running locally with a chat model and an embedding model pulled (defaults: `gemma4:26b` and `nomic-embed-text`)
- Optional, for full functionality (the server degrades gracefully without them):
  - Redis (Tier 1 memory)
  - MongoDB (Tier 2 memory)
  - ChromaDB (Tier 3 memory)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

Start the RAG service first (the main server checks for it on startup, but runs without it if it's not available):

```bash
cd rag/
python dual_endpoint_server.py   # http://localhost:8008
```

Then start the main server:

```bash
python main.py                   # http://localhost:8013
```

## Usage

```bash
curl -s -X POST http://localhost:8013/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4:26b",
    "messages": [{"role": "user", "content": "What does StatefulWidget do in Flutter?"}],
    "stream": false
  }'
```

## Configuration

All configuration lives in `config.py` and reads from environment variables, e.g.:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_API_BASE` | `http://localhost:11434` | Ollama server URL |
| `RAG_SERVER_ENDPOINT` | `http://localhost:8008/search/docs` | RAG documentation search endpoint |
| `DEFAULT_MODEL` | `gemma4:26b` | Default Ollama chat model |
| `MCP_SERVER_PORT` | `8013` | Port the main server listens on |
| `MAX_WORKERS` | `3` | Thread pool size for tool execution |
| `GOOGLE_API_KEY` / `GOOGLE_SEARCH_ENGINE_ID` | — | Enables the web search tool |
| `GITHUB_TOKEN` | — | Enables GitHub API tools |
| `MCP_API_KEY` | — | If set, all `/api/chat` and `/v1/*` requests must include a matching `X-API-Key` header. Unset by default (open, local-only use) |

### Security notes

- The server binds to `0.0.0.0` by default and has no built-in rate limiting. If you expose it beyond localhost, set `MCP_API_KEY` first.
- The sandbox tool executes code in isolated Docker containers (`--network=none`, memory/CPU limits) — verified to actually block outbound network access, not just claim to.
- Code-analysis and file-reading tools can read files anywhere you point them (by design, so they can analyze any project you're working on), but refuse to touch known-sensitive system locations (`/etc`, `/root`, `~/.ssh`, `~/.aws`, etc.).

## Project structure

```
main.py                 # FastAPI app entry point, startup/dependency checks
config.py               # Centralized configuration
api/chat.py             # /api/chat and OpenAI-compatible endpoints
core/orchestrator.py    # Request routing and the tool execution loop
core/memory_integration.py
tools/                  # git, github, code_analysis, development, sandbox, web, knowledge
rag/                    # Standalone RAG service (Flutter docs + code examples)
utils/                  # Shared helpers
superceeded/            # Earlier implementations, kept for reference
```

## Documentation

- `mcp_engineering_plan.md` — architecture and design rationale
- `Slash_Commands_Guide.md` / `Slash_Commands_Quick_Reference.md` — slash command reference
- `User_Guide.md` — end-user usage guide
