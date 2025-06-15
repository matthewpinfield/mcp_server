# 🤖 Advanced MCP Server with RAG Integration & 3-Tier Memory

**The World's Most Sophisticated Development Assistant - Local, Private, Intelligent**

## 🚀 **What Is This?**

An advanced Model Context Protocol (MCP) server that transforms any LLM into a senior developer with:
- **23+ Specialized Tools** for development workflows
- **3-Tier Memory System** (Redis + MongoDB + ChromaDB) for persistent context
- **Dual RAG Knowledge Base** with 11,663+ curated code examples and documentation
- **19 Slash Commands** for instant tool access
- **Web Search Integration** for current information
- **Secure Code Sandbox** for verification and testing
- **Complete Git/GitHub Integration** for repository management

## 🏗️ **System Architecture**

### **Core Components**
```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   MCP Server        │    │   RAG Server        │    │   Memory System     │
│   (Port 8013)       │    │   (Port 8008)       │    │   (3-Tier)          │
├─────────────────────┤    ├─────────────────────┤    ├─────────────────────┤
│ • 23+ Tools         │────│ • Flutter Docs DB   │────│ • Redis (Working)   │
│ • 19 Slash Commands │    │ • Mixed Code DB     │    │ • MongoDB (Profile) │
│ • Intelligent Router│    │ • 11,663 Documents  │    │ • ChromaDB (Archive)│
│ • Memory Interface  │    │ • LanceDB Storage   │    │ • NAS Integration   │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

### **Database Architecture**
| Component | Technology | Purpose | Location |
|-----------|------------|---------|----------|
| **Working Memory** | Redis | Current conversation context | Local SSD |
| **Profile & Rules** | MongoDB | User preferences, permanent rules | Local SSD |
| **Long-term Archive** | ChromaDB | Conversation history, semantic search | NAS |
| **Flutter Docs** | LanceDB | Official Flutter/Dart documentation | Local SSD |
| **Code Knowledge** | LanceDB | Mixed programming language examples | Local SSD |

## 🛠️ **Available Tools**

### **🧠 Memory & Learning (4 tools)**
- **Memory Context**: Intelligent conversation history retrieval
- **Save Interactions**: Persistent conversation storage with smart tagging
- **Permanent Rules**: User preference and behavior rule management
- **Memory Stats**: System diagnostics and health monitoring

### **🔍 Web Search (1 tool)**
- **Current Information Search**: Google Custom Search with domain prioritization
- **Tier-based Sources**: Official docs → Educational → Community → News

### **🔒 Code Sandbox (3 tools)**
- **Python Execution**: Secure, isolated code execution with timeout protection
- **Debug Analysis**: Comprehensive debugging with performance metrics
- **Sandbox Stats**: Resource monitoring and security configuration

### **📚 RAG Documentation (1 tool)**
- **Flutter/Dart Knowledge**: 5,098 official documentation chunks
- **Mixed Programming**: 11,663 multi-language code examples and patterns

### **⚙️ Git Operations (5 tools)**
- **Status Checking**: Repository state and working directory analysis
- **Diff Viewing**: File changes with staging options
- **Commit Creation**: Smart commits with auto-add capabilities
- **Branch Management**: Create, switch, delete, and list branches
- **History Analysis**: Commit logs with formatting options

### **🐙 GitHub Integration (3 tools)**
- **Repository Search**: Find libraries and projects by language/topic
- **Issues & PRs**: Search and analyze repository issues
- **Release Information**: Version tracking and changelog access

### **🔧 Development Helpers (6 tools)**
- **Repository Explorer**: Project structure analysis with .gitignore support
- **Dependency Analysis**: Parse package.json, pubspec.yaml, requirements.txt
- **Code Metrics**: Language distribution, file statistics, project insights
- **Package Search**: npm, PyPI, pub.dev, crates.io, Maven Central
- **Build Commands**: Detect and execute project build systems
- **Auto Linter**: Multi-language code analysis and auto-fixing

## ⚡ **Slash Commands System**

**19 Built-in Commands** across 5 categories:

### **🧠 Memory (7 commands)**
- `/rule <text>` - Add preference/rule to memory
- `/remember <info>` - Save specific information
- `/recall <query>` - Retrieve stored information
- `/forget <query>` - Remove outdated information
- `/stats` - Show memory system statistics
- `/correct <text>` - Correct AI responses for learning
- `/fix <text>` - Fix AI responses (alias for /correct)

### **🔧 Development (3 commands)**
- `/build [command]` - Execute build operations
- `/package <ecosystem> <query>` - Search packages
- `/analyze [type]` - Repository analysis

### **🔀 Git (3 commands)**
- `/status` - Quick git status check
- `/commit <message>` - Create git commits
- `/branch [action] [name]` - Branch operations

### **🛠️ System (4 commands)**
- `/commands [category]` - List available commands
- `/help <command>` - Get command help
- `/add-command <name> <desc> <action>` - Create custom commands
- `/remove-command <name>` - Remove custom commands

### **📁 Project (2 commands)**
- `/context` - Show current session context
- `/project [name] [description]` - Set project information

## 🚀 **Quick Start**

### **1. Server Startup**

**RAG Server (Port 8008):**
```bash
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
DB_PATH=lancedb_data python3 rag/dual_endpoint_server.py
```

**MCP Server (Port 8013):**
```bash
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
python3 -m advanced_mcp_server
```

### **2. IDE Integration**

**Continue VS Code Extension** (`~/.continue/config.json`):
```json
{
  "models": [
    {
      "title": "Advanced MCP Server with Memory",
      "provider": "openai",
      "model": "qwen3:8b",
      "apiKey": "dummy-key",
      "apiBase": "http://localhost:8013/v1",
      "roles": ["chat", "edit", "apply"]
    }
  ]
}
```

### **3. First Usage**

```bash
# Set up your preferences
/rule I prefer detailed code explanations
/remember This project uses Firebase for authentication

# Check system status
/stats

# Start development workflow
/status
/analyze structure
/build test
```

## 🎯 **Intelligent Tool Activation**

The system automatically selects appropriate tools based on keywords:

- **Memory**: "remember", "recall", "previous", "before"
- **Web Search**: "search web", "latest", "current", "2024"
- **Code Execution**: "run code", "execute", "what does this do"
- **Git Operations**: "git status", "commit", "branch", "push"
- **Repository Analysis**: "explore", "analyze", "structure", "dependencies"

## 🔐 **Security Features**

### **Code Sandbox Security**
- ✅ **Safe imports**: math, datetime, json, numpy, pandas
- ❌ **Blocked**: subprocess, os.system, eval, open, input
- **Resource limits**: 30s timeout, 128MB memory, 10KB output

### **Web Search Security**
- **Domain prioritization**: Official docs → Educational → Community
- **Rate limiting**: Respects API limits and `robots.txt`
- **Content validation**: Filters low-quality sources

### **Memory System Security**
- **Local storage**: All sensitive data stays on your machine
- **NAS connectivity checks**: Automatic monitoring and fallbacks
- **Encrypted connections**: Secure database communications

## 📊 **System Performance**

### **Current Capabilities**
- **Tool Count**: 23+ specialized development tools
- **Knowledge Base**: 11,663+ curated documents
- **Response Time**: <2s for most operations
- **Memory Capacity**: Unlimited with NAS storage
- **Concurrent Users**: Single-user optimized

### **Resource Requirements**
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 10GB for knowledge bases
- **CPU**: Multi-core recommended for concurrent tool execution
- **Network**: Required for web search and GitHub integration

## 🔧 **Configuration**

### **Environment Variables**
```bash
# Optional GitHub integration
export GITHUB_TOKEN="your_github_token"

# Google Custom Search (for web search)
export GOOGLE_API_KEY="your_google_api_key"
export GOOGLE_SEARCH_ENGINE_ID="your_search_engine_id"
```

### **Database Paths**
- **Redis**: `localhost:6379` (local)
- **MongoDB**: `localhost:27017` (local)
- **ChromaDB**: `/mnt/my_nas_mcp_share/archives/` (NAS)
- **LanceDB**: `./lancedb_data/` (local)

## 🤝 **Integration Examples**

### **Daily Development Workflow**
```bash
# Morning setup
/project MyApp "Flutter e-commerce application"
/rule Always use async/await for API calls

# Development cycle
What's the git status?
How do I implement state management in Flutter?
Run this code: print([x*2 for x in range(5)])
Search web for latest Flutter version 2024
Commit changes with message "Add user authentication"

# End of day
/recall today's work
/stats
```

### **Problem Solving Workflow**
```bash
# Research phase
Search GitHub for Flutter authentication libraries
Show me the repository structure
Analyze dependencies in this project

# Implementation phase  
How do I create a secure login form in Flutter?
Run this authentication code
Debug this error: [paste error]

# Completion phase
/remember Authentication uses Firebase Auth with custom claims
Commit changes with message "Implement secure authentication"
```

## 🚀 **Advanced Features**

### **3-Tier Memory System**
- **Intelligent Context**: Automatically retrieves relevant conversation history
- **Persistent Learning**: Remembers your coding preferences across sessions
- **Semantic Search**: Finds related discussions from months ago
- **Smart Tagging**: Automatically categorizes conversations by topic

### **Dual RAG Knowledge Base**
- **Authority Weighting**: Prioritizes official documentation over blog posts
- **Metadata Filtering**: Surgically targets relevant knowledge by language/framework
- **Real-time Updates**: Latest documentation and best practices
- **Quality Curation**: Only high-authority sources included

### **Custom Command System**
```bash
# Create project-specific commands
/add-command /deploy "Deploy to production" deploy_prod
/add-command /test-e2e "Run end-to-end tests" run_e2e_tests

# Commands persist across sessions
/commands custom
```

## 🔍 **Troubleshooting**

### **Common Issues**

**Port conflicts:**
```bash
# Check what's using port 8013
sudo lsof -i :8013
# Kill process if needed
sudo kill -9 <PID>
```

**Memory system errors:**
```bash
# Check database connections
/stats
# Restart databases if needed
sudo systemctl restart redis mongodb
```

**RAG server not responding:**
```bash
# Check RAG server status
curl http://localhost:8008/health
# Restart if needed
DB_PATH=lancedb_data python3 rag/dual_endpoint_server.py
```

### **Health Checks**
```bash
# Verify all systems
curl http://localhost:8013/health  # MCP Server
curl http://localhost:8008/health  # RAG Server
/stats                            # Memory System
```

## 📈 **Performance Optimization**

### **Speed Optimizations**
- **Direct tool access** via slash commands (bypasses orchestrator)
- **Intelligent caching** in Redis for frequent queries
- **Lazy loading** of tools and knowledge bases
- **Connection pooling** for database operations

### **Quality Optimizations**
- **Authority-weighted retrieval** for accurate information
- **Correction learning** system for continuous improvement
- **Smart context assembly** for relevant, focused responses
- **Proactive code verification** before presenting solutions

---

## 💡 **Philosophy**

This system embodies the principle of **"Context-First AI"** - every response is grounded in facts from curated knowledge bases, your personal preferences, and relevant conversation history. It's designed to be:

- **Intelligent**: Automatically selects the right tools for each task
- **Personal**: Learns and adapts to your coding style and preferences  
- **Accurate**: Grounds all responses in authoritative sources
- **Private**: All data stays on your local infrastructure
- **Extensible**: Easy to add new tools and customize behavior

**🎯 Goal**: Transform any LLM into a senior developer with persistent memory, vast knowledge, and tool mastery - all running locally under your complete control.