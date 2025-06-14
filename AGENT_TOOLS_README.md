# 🤖 Agent Tools Reference Guide

## Overview

This document provides comprehensive information about all available tools in the Advanced MCP Server system. It serves as both a reference for developers and a specification for the AI agent on how to effectively use each tool.

## 🧠 Memory System Tools

### 1. **Memory Context Retrieval**
- **Tool Name**: `get_memory_context`
- **Purpose**: Retrieve conversation context from 3-tier memory system
- **When to Use**: 
  - User asks about previous conversations
  - Need to recall user preferences or rules
  - Context is needed for personalized responses
- **Input**: Query string (optional), include_long_term flag
- **Output**: Formatted context with user profile, rules, and semantic memories

**Best Practices**:
- Use at the start of conversations to get user context
- Query specific topics when user references "before" or "previously"
- Always include long-term memory unless specifically about current session

### 2. **Save Interactions**
- **Tool Name**: `save_interaction_to_memory`
- **Purpose**: Save conversation messages for future recall
- **When to Use**:
  - Important conversations that should be remembered
  - User explicitly asks to remember something
  - After solving complex problems
- **Input**: List of message objects with role/content
- **Output**: Confirmation with interaction ID and storage locations

**Best Practices**:
- Save complete conversations, not fragments
- Include context messages for clarity
- Use tags for better categorization

### 3. **Add Permanent Rules**
- **Tool Name**: `add_permanent_rule`
- **Purpose**: Store user preferences and behavioral rules
- **When to Use**:
  - User expresses preferences ("I prefer detailed explanations")
  - Behavior requests ("Always ask before running destructive commands")
  - Coding style preferences
- **Input**: Rule text and category
- **Output**: Confirmation with rule ID

**Best Practices**:
- Use clear, actionable rule text
- Categorize appropriately (preference, coding_style, communication)
- Don't duplicate existing rules

### 4. **Memory Statistics**
- **Tool Name**: `get_memory_stats`
- **Purpose**: Diagnostic information about memory system
- **When to Use**: Troubleshooting or user requests system status
- **Input**: None
- **Output**: Status of Redis, MongoDB, ChromaDB with counts

## 🔍 Web Search Tools

### 1. **Web Search**
- **Tool Name**: `search_web`
- **Purpose**: Find current information from the internet
- **When to Use**:
  - Questions about recent events or current information
  - Latest versions, news, or updates
  - Information beyond training data cutoff
  - User explicitly requests web search
- **Input**: Search query, max_results (default 5)
- **Output**: Prioritized search results with domain trust indicators

**Best Practices**:
- Use specific, targeted queries
- Include relevant keywords and context
- Prefer for time-sensitive information
- Don't use for basic programming concepts covered in documentation

**Domain Priority**:
- 🏛️ **Tier 1**: Official docs (flutter.dev, python.org, etc.)
- 👥 **Tier 2**: Community sites (stackoverflow.com, github.com)
- 📰 **Tier 3**: News sites (techcrunch.com, theverge.com)

## 🔒 Code Sandbox Tools

### 1. **Execute Python Code**
- **Tool Name**: `execute_python_sandbox`
- **Purpose**: Run Python code in secure, isolated environment
- **When to Use**:
  - User asks "what does this code do?"
  - Testing code snippets for correctness
  - Performing calculations or data analysis
  - Verifying algorithm implementations
  - **CRITICAL**: Before presenting complex code as final answer
- **Input**: Valid Python code string
- **Output**: Execution status, stdout, stderr, timing, warnings

**Best Practices**:
- **Always verify complex code before presenting it**
- Use for any non-trivial code examples
- Perfect for mathematical calculations
- Test edge cases and error conditions

**Security Features**:
- ✅ Safe imports: math, datetime, json, numpy, pandas
- ❌ Blocked: subprocess, os.system, eval, open, input
- Resource limits: 30s timeout, 128MB memory, 10KB output

### 2. **Debug Python Code**
- **Tool Name**: `debug_python_sandbox`
- **Purpose**: Detailed debugging with performance analysis
- **When to Use**:
  - Code fails and need detailed error analysis
  - Performance optimization questions
  - Comparing actual vs expected output
  - Complex debugging scenarios
- **Input**: Python code, optional expected output
- **Output**: Comprehensive debug report with timing and validation

**Best Practices**:
- Use when simple execution isn't enough
- Provide expected output for comparison when available
- Great for teaching and explaining code behavior

### 3. **Sandbox Statistics**
- **Tool Name**: `get_sandbox_stats`
- **Purpose**: System health and configuration info
- **When to Use**: Troubleshooting sandbox issues
- **Input**: None
- **Output**: Sandbox availability, limits, security settings

## 📚 RAG Documentation Tools

### 1. **Flutter/Dart Documentation**
- **Tool Name**: `flutter_dart_documentation_search`
- **Purpose**: Search comprehensive Flutter/Dart knowledge base
- **When to Use**:
  - Flutter/Dart specific questions
  - Widget usage and examples
  - Best practices and patterns
  - API documentation lookup
- **Input**: Search query
- **Output**: Relevant documentation with examples and context

**Best Practices**:
- Use for Flutter/Dart specific questions
- Include context about what you're trying to build
- Prefer over web search for established Flutter concepts

## ⚙️ Git Operations Tools

### 1. **Git Status**
- **Tool Name**: `git_status`
- **Purpose**: Check repository status and working directory changes
- **When to Use**: User asks about current git state
- **Input**: None
- **Output**: Modified files, staged changes, branch info

### 2. **Git Diff**
- **Tool Name**: `git_diff`
- **Purpose**: Show file differences and changes
- **When to Use**: User wants to see what changed
- **Input**: Optional file path, staged flag
- **Output**: Detailed diff output

### 3. **Git Commit**
- **Tool Name**: `git_commit`
- **Purpose**: Create commits with messages
- **When to Use**: User wants to save changes
- **Input**: Commit message, add_all flag
- **Output**: Commit success/failure status

### 4. **Git Branch Operations**
- **Tool Name**: `git_branch`
- **Purpose**: Branch management (list, create, checkout, delete)
- **When to Use**: Branch-related operations
- **Input**: Action, branch name
- **Output**: Branch operation results

### 5. **Git Log**
- **Tool Name**: `git_log`
- **Purpose**: View commit history
- **When to Use**: User wants to see past commits
- **Input**: Count limit, oneline flag
- **Output**: Formatted commit history

## 🐙 GitHub Tools

### 1. **Repository Search**
- **Tool Name**: `github_repo_search`
- **Purpose**: Search GitHub repositories
- **When to Use**: Finding libraries, examples, or projects
- **Input**: Search query, language filter, sort options
- **Output**: Repository results with stats

### 2. **Repository Issues**
- **Tool Name**: `github_repo_issues`
- **Purpose**: Search issues and pull requests
- **When to Use**: Finding known problems or solutions
- **Input**: Repository name, state filter
- **Output**: Issues/PRs with details

### 3. **Repository Releases**
- **Tool Name**: `github_repo_releases`
- **Purpose**: Get release information
- **When to Use**: Checking versions and changelogs
- **Input**: Repository name
- **Output**: Release versions and notes

## 🔧 Development Helper Tools

### 1. **Repository Explorer**
- **Tool Name**: `explore_repository`
- **Purpose**: Analyze project structure and files
- **When to Use**: Understanding unfamiliar projects
- **Input**: Path, depth limit
- **Output**: Directory tree with file types and stats

### 2. **Dependency Analysis**
- **Tool Name**: `analyze_dependencies`
- **Purpose**: Parse and analyze project dependencies
- **When to Use**: Understanding project dependencies
- **Input**: None (auto-detects)
- **Output**: Dependency tree and analysis

### 3. **Code Metrics**
- **Tool Name**: `code_metrics`
- **Purpose**: Calculate code statistics and metrics
- **When to Use**: Project analysis and insights
- **Input**: None
- **Output**: Lines of code, language distribution, file stats

### 4. **Package Search**
- **Tool Name**: `search_packages`
- **Purpose**: Search package registries (npm, PyPI, pub.dev, etc.)
- **When to Use**: Finding libraries and packages
- **Input**: Ecosystem, query
- **Output**: Package search results

### 5. **Build Commands**
- **Tool Name**: `detect_build_commands`
- **Purpose**: Detect and execute build system commands
- **When to Use**: Running project builds, tests, lints
- **Input**: Action type
- **Output**: Detected commands and execution results

### 6. **Auto Linter**
- **Tool Name**: `auto_linter`
- **Purpose**: Run code analysis and linting tools
- **When to Use**: Code quality checks
- **Input**: None (auto-detects)
- **Output**: Linting results and suggestions

## 🎯 Tool Selection Guidelines

### **Automatic Tool Activation**

The system automatically selects tools based on keyword detection and context analysis:

#### **Memory Tools** - Activated by:
- "remember", "recall", "previous", "before", "history"
- "/correct", "/fix", user preferences
- Context needed for personalized responses

#### **Web Search** - Activated by:
- "search web", "latest", "current", "recent", "what's new"
- Temporal indicators: "2024", "2025", "today"
- "find information", "tell me about"

#### **Sandbox Tools** - Activated by:
- "run code", "execute", "test code", "what does this do"
- "calculate", "compute", "solve", "debug", "verify"
- Code blocks in messages (```python)
- Mathematical expressions

#### **RAG Documentation** - Activated by:
- "flutter", "dart", "widget", "state management"
- API questions, "how to", documentation requests

#### **Git Tools** - Activated by:
- "git status", "commit", "branch", "push", "pull"
- Repository state questions

#### **GitHub Tools** - Activated by:
- "github search", "repository", "issues", "releases"
- Library and project discovery

#### **Development Tools** - Activated by:
- "explore", "analyze", "structure", "dependencies"
- "build", "test", "lint", "package search"

## 🚀 Advanced Usage Patterns

### **Proactive Code Verification**
**IMPORTANT RULE**: Before presenting any complex or non-trivial code snippet as a final answer, use the `execute_python_sandbox` tool to verify its correctness and capture its output.

Example workflow:
1. User asks for a solution
2. Generate code solution
3. Test code in sandbox
4. Present verified solution with actual output

### **Combining Tools Effectively**
- **Research → Implement → Verify**: Web search → Code generation → Sandbox testing
- **Analyze → Build → Commit**: Repo exploration → Build commands → Git commit
- **Learn → Remember**: Problem solving → Save to memory for future reference

### **Error Handling Best Practices**
- Always provide clear error messages
- Suggest alternatives when tools fail
- Use fallback methods (e.g., direct sandbox if subprocess fails)
- Explain what went wrong and why

### **Security Considerations**
- Validate all user inputs
- Use sandbox for any code execution
- Respect rate limits on external APIs
- Never expose sensitive information

## 📋 Tool Performance Tips

### **Optimization Guidelines**
1. **Batch operations** when possible
2. **Cache results** for repeated queries
3. **Use appropriate timeouts** for long operations
4. **Provide progress feedback** for slow operations
5. **Limit output size** to prevent overwhelming responses

### **Resource Management**
- Sandbox: 30s timeout, 128MB memory limit
- Web search: 5 results max by default
- Git operations: Standard timeouts with graceful degradation
- Memory queries: Automatic relevance scoring

## 🔍 Troubleshooting Guide

### **Common Issues and Solutions**

1. **Sandbox execution fails**
   - Check code syntax validation
   - Review blocked imports/patterns
   - Try direct execution method

2. **Web search returns no results**
   - Verify API key configuration
   - Check rate limits
   - Try different query terms

3. **Git operations fail**
   - Ensure Git is installed
   - Check repository state
   - Verify permissions

4. **Memory system errors**
   - Check Redis/MongoDB/ChromaDB connectivity
   - Verify storage paths
   - Review memory system logs

---

**💡 Remember**: The goal is to be an intelligent, proactive assistant that leverages these tools to provide accurate, verified, and helpful responses. Always prioritize user safety and code correctness over speed.

**🎯 Key Principle**: Use tools to enhance reasoning and provide verified solutions, not just to appear busy. Each tool call should add genuine value to the response.