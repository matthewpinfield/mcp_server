# Continue VS Code Extension Integration Guide

## Issues with Original Configuration

The original `config.yaml` had several problems:

1. **Wrong file format**: Continue uses JSON (`config.json`), not YAML
2. **Incorrect approach**: Used `externalApi` instead of `models` with `apiBase`
3. **Wrong port**: Used 8012 (original server) instead of 8013 (advanced server with memory)
4. **Complex schema**: Tried to define OpenAPI schema instead of using simple model configuration

## Correct Configuration

### File Location
Place the configuration file at:
- **Windows**: `%USERPROFILE%\.continue\config.json`
- **macOS**: `~/.continue/config.json` 
- **Linux**: `~/.continue/config.json`

Or use VS Code Command Palette: `Ctrl+Shift+P` → "Continue: Open config.json"

### Complete Configuration

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
    },
    {
      "title": "Original MCP Server", 
      "provider": "openai",
      "model": "qwen3:8b",
      "apiKey": "dummy-key", 
      "apiBase": "http://localhost:8012/v1",
      "roles": ["chat"]
    },
    {
      "title": "Direct Ollama (Fallback)",
      "provider": "ollama",
      "model": "qwen3:8b",
      "roles": ["autocomplete"]
    }
  ],
  "systemMessage": "Your system message here...",
  "contextProviders": [
    {"name": "code", "params": {}},
    {"name": "docs", "params": {}},
    {"name": "diff", "params": {}},
    {"name": "terminal", "params": {}},
    {"name": "problems", "params": {}},
    {"name": "folder", "params": {}},
    {"name": "codebase", "params": {}}
  ]
}
```

## Key Configuration Differences

| Aspect | Original (Incorrect) | Corrected |
|--------|---------------------|-----------|
| **File Format** | YAML | JSON |
| **Model Definition** | `externalApi` + custom schema | `models` with `apiBase` |
| **Provider** | `ollama` with external API | `openai` with custom `apiBase` |
| **Port** | 8012 (original server) | 8013 (advanced server) |
| **API Key** | Not specified | `"dummy-key"` (required field) |

## How It Works

1. **Continue** sends chat requests to `http://localhost:8013/v1/chat/completions`
2. **Advanced MCP Server** receives the request on port 8013
3. **Orchestrator Logic** analyzes the message content:
   - Memory keywords → Activates memory tools
   - Flutter/Dart keywords → Activates RAG tools
   - Simple conversation → Direct Ollama path
4. **Layer 1 Tagging** extracts context-aware tags
5. **Memory System** automatically saves interactions with intelligent tags
6. **Response** streams back to Continue with full memory context

## Features Available in Continue

### Memory System Integration
- **Persistent context** across VS Code sessions
- **Intelligent tagging** of coding conversations
- **Long-term recall** of previous solutions
- **User preference learning**

### Advanced Orchestration
- **Smart tool selection** based on conversation content
- **Context-aware responses** using session history
- **Automatic memory storage** of coding sessions

### RAG Integration
- **Flutter/Dart documentation** queries
- **Code-specific help** with real documentation
- **Error explanation** from knowledge base

## Testing the Integration

1. **Install Continue extension** in VS Code
2. **Copy the configuration** to `~/.continue/config.json`
3. **Restart VS Code**
4. **Open a project** and start chatting
5. **Test memory features**:
   - Ask: "Remember that I prefer detailed explanations"
   - Later ask: "What do you remember about my preferences?"
6. **Test Flutter integration**:
   - Ask: "How do I create a Flutter widget?"
   - Should activate RAG tools automatically

## Multiple Server Support

The configuration supports both servers:
- **Port 8013**: Advanced server with memory (primary)
- **Port 8012**: Original server (backup)
- **Direct Ollama**: Fallback for autocomplete

This gives you flexibility to switch between different AI personalities and capabilities within Continue.

## Troubleshooting

### Common Issues

1. **Connection refused**: Ensure servers are running on correct ports
2. **No memory**: Check that port 8013 is configured (not 8012)
3. **No tool activation**: Verify keywords trigger orchestrator logic
4. **JSON syntax errors**: Validate JSON format

### Verification Commands

```bash
# Check servers are running
curl http://localhost:8013/health
curl http://localhost:8012/health

# Test memory endpoint
curl -X POST http://localhost:8013/memory/stats

# Test chat endpoint
curl -X POST http://localhost:8013/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"Hello"}]}'
```

## Benefits Over Open WebUI

- **Integrated development environment** - AI assistance directly in your editor
- **Code context awareness** - Automatic inclusion of current file/project context
- **Instant access** - No need to switch between tools
- **Memory persistence** - Coding sessions remembered across projects
- **Intelligent routing** - Automatic selection of appropriate tools based on coding context