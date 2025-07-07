# Configuration Backup & Restore Instructions

## Backup Created: 2025-06-24

### Original Configuration Values (SAFE BASELINE)

**RAG System**:
- RAG results: 5 (max 20)
- Content length: 800 chars
- Response time: 0.02-0.05s

**Web Search**:
- Results: 3-5
- Timeout: 60s
- Content length: 800 chars

**Tier Memory**:
- Tier 1: 5 interactions, 150 chars
- Tier 2: 5-10 rules, 5 corrections
- Tier 3: 5 semantic matches

**Total Context**: ~11,650-13,250 chars

## Files Backed Up

1. `config_original.py` - Main configuration
2. `knowledge_original.py` - RAG and memory tools
3. `web_original.py` - Web search configuration  
4. `orchestrator_original.py` - Agent routing logic

## Restore Commands (if agent flooding occurs)

```bash
# Navigate to project root
cd /mnt/caseSSD/mcp_server_project

# Restore original files
cp backups/original_configs/config_original.py config.py
cp backups/original_configs/knowledge_original.py tools/knowledge.py
cp backups/original_configs/web_original.py tools/web.py
cp backups/original_configs/orchestrator_original.py core/orchestrator.py

# Restart services
pkill -f "python.*main.py"
pkill -f "python.*dual_endpoint_server.py"
python main.py &
cd rag && python dual_endpoint_server.py &
```

## Signs of Agent Flooding

- Response times >30 seconds
- Incomplete responses  
- Agent stops mid-response
- Context overflow errors
- Memory issues

**Immediate Action**: Run restore commands above to return to stable baseline.