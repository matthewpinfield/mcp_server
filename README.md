# MCP Server - Local LLM Agent System

An intelligent Model Context Protocol (MCP) server that provides specialized tools and memory integration for local LLM deployment. Acts as middleware between chat clients and Ollama, with intelligent tool routing and sliding window memory architecture.

## Quick Start

#### **Combined RAG Server** (Port 8008) 
```bash
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
python3 rag/dual_endpoint_server.py
```

#### **Main MCP Server** (Port 8013)
```bash
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
python3 main.py
```

**Access Points:**
- MCP API: http://localhost:8013
- OpenWebUI: http://localhost:9000  
- RAG Search: http://localhost:8008

## Features

- **9 Tool Categories**: Memory, RAG, Web Search, Git, GitHub, Development, Code Analysis, Sandbox, System
- **Sliding Window Memory**: Redis (today) → LanceDB SSD (2-30 days) → LanceDB NAS (30+ days)
- **Dual RAG System**: Flutter docs + code examples with vector search
- **OpenAI Compatible**: `/v1/chat/completions` endpoint with streaming
- **LangChain Integration**: ReAct agent with automatic tool selection
- **Slash Commands**: `/remember`, `/recall`, `/rule`, `/list_rules`

## Documentation

- **[mcp_engineering_plan.md](mcp_engineering_plan.md)** - Complete technical specification
- **[User_Guide.md](User_Guide.md)** - Detailed usage instructions
- **[claude.md](claude.md)** - Development guidelines and methodology
- **[qwen3_thinking.md](qwen3_thinking.md)** - qwen3 unique thinking explained
- **[slash_commands_QR.md](slash_commands_QR.md)** additional user fucnctions

## Requirements

- Python 3.11+ with virtual environment
- Ollama with qwen3:30b-a3b model
- Required: Redis, MongoDB for rules, LanceDB for memory storage

