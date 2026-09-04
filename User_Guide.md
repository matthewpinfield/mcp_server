# 📖 User Guide: Advanced MCP Server with Memory System, Git/GitHub Integration & Code Sandbox

## 🚀 **Getting Started**

### **Server Startup Commands**

#### **Combined RAG Server** (Port 8008) 
```bash
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
python3 rag/dual_endpoint_server.py

#### **Main MCP Server** (Port 8013)
```bash
cd /mnt/caseSSD/mcp_server_project
source .venv/bin/activate
python3 main.py


### **Prerequisites**
1. **Git installed**: `sudo apt install git`
2. **Both servers running**: MCP (8013) + RAG (8008)
3. **Continue IDE configured**: Uses port 8013 for MCP tools

### **Optional GitHub Setup**
```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### **Memory & Learning**

#### **Correction Commands**
**Triggers**: "/correct", "/fix"
```
Example: "/correct 2+2=4, not 5"
Action: Stores correction in memory for future learning
```

#### **Profile Management**  
**Triggers**: "add rule", "set preference", "remember that"
```
Example: "Remember that I prefer concise code explanations"
Action: Stores permanent rules in user profile
```

### **Git Operations**

#### **Check Repository Status**
**Triggers**: "git status", "check status", "show changes"
```
Example: "What's the current git status?"
Response: Shows modified files, staged changes, branch info
```

#### **View Differences**
**Triggers**: "git diff", "show diff", "what changed"
```
Example: "Show me the git diff for main.py"
Options: Staged vs unstaged changes, specific files
```

#### **Create Commits**
**Triggers**: "git commit", "commit changes", "save changes"
```
Example: "Commit these changes with message 'Add new feature'"
Options: Auto-add all files before committing
```

#### **Branch Management**
**Triggers**: "git branch", "create branch", "switch branch"
```
Example: "Create a new branch called feature-login"
Actions: list, create, checkout, delete branches
```

#### **View History**
**Triggers**: "git log", "commit history", "show history"
```
Example: "Show the last 5 commits"
Options: Limit count, oneline vs detailed format
```

### **GitHub Integration**

#### **Search Repositories**
**Triggers**: "search github", "find repository", "github search"
```
Example: "Search GitHub for Flutter state management libraries"
Filters: Language, popularity, activity
```

#### **Repository Issues**
**Triggers**: "github issues", "find issues", "repository problems"  
```
Example: "Show open issues in flutter/flutter repository"
Options: Open/closed/all issues, includes PRs
```

#### **Release Information**
**Triggers**: "github releases", "latest version", "changelog"
```
Example: "Get latest releases for flutter/flutter"
Shows: Version tags, release notes, download links
```

### **Repository Analysis**

#### **Explore Structure**
**Triggers**: "explore repository", "analyze structure", "file tree"
```
Example: "Explore the structure of this project"
Shows: Directory tree, project type detection, file statistics
Features: Respects .gitignore, emoji file icons
```

#### **Dependency Analysis**  
**Triggers**: "analyze dependencies", "check packages", "dependency tree"
```
Example: "Analyze the dependencies in this Flutter project"
Supports: package.json, pubspec.yaml, requirements.txt, Cargo.toml
```

#### **Code Metrics**
**Triggers**: "code metrics", "analyze code", "project statistics"
```
Example: "Show me code metrics for this repository"  
Provides: Lines of code, language distribution, file sizes, insights
```

### **Web Search**

#### **Current Information Search**
**Triggers**: "search web", "latest", "current", "recent", "what's new"
```
Example: "Search for latest Flutter version 2024"
Features: Google Custom Search API, domain prioritization
Sources: Official docs, StackOverflow, GitHub, tech news
```

### **Code Sandbox & Execution**

#### **Execute Python Code**
**Triggers**: "run code", "execute", "test code", "what does this do"
```
Example: "Run this code: print([x*2 for x in range(5)])"
Features: Secure isolation, timeout protection, resource limits
Output: stdout, stderr, execution time, validation warnings
```

#### **Debug & Verify Code**
**Triggers**: "debug", "verify", "check output", "test this"
```
Example: "Debug this code and compare with expected output"
Features: Detailed analysis, performance metrics, output comparison
Security: Blocked dangerous imports, memory limits
```

#### **Code Calculations**
**Triggers**: "calculate", "compute", "solve", "math"
```
Example: "Calculate the average of these numbers: [1,2,3,4,5]"
Use case: Complex calculations, data analysis, formula verification
```

### **Development Helpers**

#### **Package Search**
**Triggers**: "search packages", "find library", "npm search"
```
Example: "Search npm for React state management"
Ecosystems: npm, PyPI, pub.dev, crates.io, Maven Central
```

#### **Build Commands**
**Triggers**: "build project", "run tests", "detect build system"
```
Example: "Detect build commands for this project"
Actions: detect, run, test, lint, format, clean
Supports: npm, Flutter, Python, Rust, Maven, Gradle, Make, CMake
```

## 🎯 **Usage Patterns**

### **Typical Development Workflow**
1. **"What's the git status?"** - Check current state
2. **"Explore this repository structure"** - Understand project
3. **"Analyze dependencies"** - Check packages  
4. **"Search web for latest Flutter best practices"** - Current info
5. **"Search npm for testing library"** - Find new dependencies
6. **"Run this code to test the function"** - Verify implementation
7. **"Run tests"** - Execute build commands
8. **"Commit changes with message 'Add tests'"** - Save work
9. **"Search GitHub for similar projects"** - Research

### **Code Development Workflow**
1. **"I need to implement this algorithm"** - Share code
2. **"Run this code to see if it works"** - Test execution
3. **"Debug this and show me what's wrong"** - Detailed analysis
4. **"Calculate the time complexity"** - Mathematical analysis
5. **"Search web for optimization techniques"** - Current research
6. **"Verify the corrected code works"** - Final validation

### **Project Analysis Workflow**
1. **"Analyze the structure of this repository"**
2. **"Show me code metrics"**  
3. **"Analyze dependencies"**
4. **"Detect build commands"**
5. **"Check git status"**

## 🔍 **Smart Features**

### **Automatic Tool Selection**
- System detects keywords and activates appropriate tools
- No need to specify which tool to use
- Intelligent context awareness

### **3-Tier Memory System**
- **Tier 1 (Redis)**: Current conversation context and working memory
- **Tier 2 (MongoDB)**: Permanent user profile, rules, and preferences  
- **Tier 3 (ChromaDB)**: Long-term conversation archive on NAS
- **Correction Learning**: Use `/correct <text>` to teach the AI from mistakes
- **Personalized Responses**: AI adapts to your preferences and rules automatically

### **Context Window Management & Auto-Compaction**
- **Dynamic Context Detection**: Automatically detects model context limits from Ollama
- **Real-time Monitoring**: Shows context usage percentage with every request
- **Smart Warnings**: Alerts when approaching 75% of context limit
- **Auto-Compaction**: Automatically triggers at 85% usage to prevent overflows
- **Conversation Artifacts**: Preserves key information during compaction for seamless agent handoff
- **Hardware Adaptation**: Automatically adjusts to different hardware setups (CPU vs GPU inference)

#### **Context Monitoring Features**
```
🔄 Chat Request: Model='qwen3:30b-a3b ', Msgs=45, Context: 32450/40960 (79.2%)
⚠️ Context usage at 87.3% - creating artifact and compacting  
📦 Compacted: 45 → 8 messages, 35720 → 8450 tokens
```

#### **Artifact Preservation**
When auto-compaction occurs, the system creates a conversation artifact containing:
- **Conversation Summary**: Overview of discussion with message counts
- **Key Decisions**: Recent progress and changes made
- **Current Context**: User's immediate request and intent
- **Mentioned Files**: File paths referenced in conversation
- **Topic Analysis**: Key technical topics discussed
- **Next Agent Briefing**: Handoff instructions for continued assistance

#### **Configuration Options**
Set environment variables to customize behavior:
```bash
export MAX_CONTEXT_TOKENS=100000     
export COMPACTION_THRESHOLD=0.85     # Auto-compact at 85% (0.0-1.0)
export WARNING_THRESHOLD=0.75        # Warning at 75% (0.0-1.0)  
export ARTIFACT_ENABLED=True         # Enable/disable auto-compaction
```

``

#### **Manual Context Check**
Check current context configuration:
```bash
curl http://localhost:8013/api/context-status
```

### **Error Handling**
- Graceful handling when Git not installed
- Clear error messages with suggestions
- Timeout protection for long-running commands

### **Security Features**
- Command validation prevents dangerous operations
- GitHub token optional but recommended for higher rate limits
- Safe command execution with proper error handling

## 🐛 **Troubleshooting**

### **Common Issues**

**Git command not found**
- Install Git: `sudo apt install git`
- Restart server after installation

**GitHub rate limits**
- Set GITHUB_TOKEN environment variable
- Token provides higher API rate limits

**Repository not detected**
- Ensure you're in a proper project directory
- Check that project files exist (package.json, pubspec.yaml, etc.)

**Build commands not found**
- Ensure build tools are installed (npm, flutter, etc.)
- Check that project configuration files exist

### **Getting Help**
- All tools provide descriptive error messages
- Check server logs for detailed debugging information
- Memory system tracks issues for pattern recognition

## 📋 **Quick Reference**

### **Git Commands**
| Trigger Words | Tool | Action |
|---------------|------|---------|
| "git status", "check status" | GitStatus | Show repository status |
| "git diff", "show diff" | GitDiff | Show file changes |
| "git commit", "commit changes" | GitCommit | Create commit |
| "git branch", "switch branch" | GitBranch | Branch management |
| "git log", "commit history" | GitLog | Show commit history |

### **GitHub Commands**
| Trigger Words | Tool | Action |
|---------------|------|---------|
| "search github", "find repository" | GitHubRepoSearch | Search repositories |
| "github issues", "find issues" | GitHubIssues | Search issues/PRs |
| "github releases", "latest version" | GitHubReleases | Get release info |

### **Analysis Commands**
| Trigger Words | Tool | Action |
|---------------|------|---------|
| "explore repository", "file tree" | RepoExplore | Analyze structure |
| "analyze dependencies", "check packages" | DependencyAnalysis | Check dependencies |
| "code metrics", "project statistics" | CodeMetrics | Calculate metrics |

### **Web Search Commands**
| Trigger Words | Tool | Action |
|---------------|------|---------|
| "search web", "latest", "current" | WebSearch | Google Custom Search |
| "what's new", "recent", "2024" | WebSearch | Current information lookup |

### **Sandbox Commands**
| Trigger Words | Tool | Action |
|---------------|------|---------|
| "run code", "execute", "test code" | SandboxExecute | Execute Python code securely |
| "debug", "verify", "check output" | SandboxDebug | Debug with detailed analysis |
| "calculate", "compute", "solve" | SandboxExecute | Mathematical calculations |

### **Helper Commands**
| Trigger Words | Tool | Action |
|---------------|------|---------|
| "search packages", "find library" | PackageSearch | Search package registries |
| "build project", "run tests" | BuildCommand | Execute build commands |

---

**💡 Tip**: You can combine operations in natural language. For example: "Check git status and then commit changes with message 'Fix bug'"

**🚀 The system automatically detects your intent and activates the appropriate tools - just speak naturally about what you want to do!**