# 📖 User Guide: Git/GitHub Integration

## 🚀 **Getting Started**

### **Prerequisites**
1. **Git installed**: `sudo apt install git`
2. **Server running**: `python advanced_mcp_server.py`
3. **Continue IDE configured**: Uses port 8013

### **Optional GitHub Setup**
```bash
export GITHUB_TOKEN="your_github_token_here"
```

## 🔧 **Available Tools & Usage**

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
4. **"Search npm for testing library"** - Find new dependencies
5. **"Run tests"** - Execute build commands
6. **"Commit changes with message 'Add tests'"** - Save work
7. **"Search GitHub for similar projects"** - Research

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

### **Memory Integration**
- Remembers your Git workflow patterns
- Tracks project context across sessions
- Learns your preferred commands and responses

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

### **Helper Commands**
| Trigger Words | Tool | Action |
|---------------|------|---------|
| "search packages", "find library" | PackageSearch | Search package registries |
| "build project", "run tests" | BuildCommand | Execute build commands |

---

**💡 Tip**: You can combine operations in natural language. For example: "Check git status and then commit changes with message 'Fix bug'"

**🚀 The system automatically detects your intent and activates the appropriate tools - just speak naturally about what you want to do!**