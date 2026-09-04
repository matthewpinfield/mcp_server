# 🚀 Slash Commands System - Complete Guide

## 📋 Overview

The Advanced MCP Server now includes a comprehensive slash command system that provides instant access to tools and features without going through the full orchestrator. Slash commands are processed immediately and can be stored in memory for persistence across sessions.

## ⚡ Key Features

- **20 Built-in Commands** across 5 categories
- **Custom Command Creation** - Add your own commands dynamically
- **Memory Integration** - Commands stored in memory persist across sessions  
- **Direct Tool Access** - Bypass orchestrator for instant responses
- **Help System** - Built-in documentation and usage examples
- **Category Filtering** - Organize commands by purpose

---

## 📚 Complete Command Library

### 🧠 **Memory Management**

#### `/rule <rule_text>`
**Purpose**: Add a new rule or preference to memory  
**Example**: `/rule I prefer detailed code explanations`  
**Use Case**: Set coding preferences, project guidelines, personal rules

#### `/list_rules [search_term]`
**Purpose**: List all rules with optional search filtering  
**Example**: `/list_rules coding`  
**Use Case**: Find existing rules, get rule IDs for updates/deletion

#### `/delete_rule <rule_id>`
**Purpose**: Delete a specific rule from memory by ID  
**Example**: `/delete_rule ab12cd34`  
**Use Case**: Remove outdated rules, clean up preferences

#### `/change_rule <rule_id> <new_rule_text>`
**Purpose**: Update a specific rule in memory by ID  
**Example**: `/change_rule ab12cd34 I prefer concise explanations`  
**Use Case**: Modify existing rules without losing history

#### `/remember <information>`
**Purpose**: Save specific information to memory  
**Example**: `/remember This project uses Redux for state management`  
**Use Case**: Store project details, important facts, context

#### `/recall <query>`
**Purpose**: Retrieve information from memory  
**Example**: `/recall state management preferences`  
**Use Case**: Find stored information, project details, rules

#### `/forget <query>`
**Purpose**: Remove information from memory  
**Example**: `/forget old project preferences`  
**Use Case**: Clean up outdated information

#### `/stats`
**Purpose**: Show memory and system statistics  
**Example**: `/stats`  
**Use Case**: Monitor memory usage, system performance

### 🔧 **Development Workflow**

#### `/build [command]`
**Purpose**: Quick build command detection and execution  
**Example**: `/build test`  
**Use Case**: Run project builds, tests, compilation

#### `/package <ecosystem> <query>`
**Purpose**: Quick package search  
**Example**: `/package npm react-router`  
**Use Case**: Find libraries, dependencies, packages

#### `/analyze [type]`
**Purpose**: Quick repository analysis  
**Example**: `/analyze structure`  
**Options**: structure, dependencies, metrics  
**Use Case**: Project insights, code analysis

### 🛠️ **System & Help**

#### `/commands [category]`
**Purpose**: List all available slash commands  
**Example**: `/commands memory`  
**Categories**: memory, development, system, project, custom  
**Use Case**: Discovery, reference

#### `/help <command>`
**Purpose**: Get help for a specific command  
**Example**: `/help /rule`  
**Use Case**: Learn command usage, syntax

#### `/add-command <name> <description> <action>`
**Purpose**: Add a new custom slash command  
**Example**: `/add-command /deploy 'Deploy to production' deploy_prod`  
**Use Case**: Extend functionality, custom workflows

#### `/remove-command <name>`
**Purpose**: Remove a custom slash command  
**Example**: `/remove-command /deploy`  
**Use Case**: Clean up custom commands

### 📁 **Project Management**

#### `/context`
**Purpose**: Get current session and project context  
**Example**: `/context`  
**Use Case**: Check session state, project info

#### `/project [name] [description]`
**Purpose**: Set or get current project information  
**Example**: `/project MyApp 'Flutter e-commerce app'`  
**Use Case**: Project identification, context setting

#### `/workspace [setting] [value]`
**Purpose**: Manage workspace settings and preferences  
**Example**: `/workspace theme dark`  
**Use Case**: Environment configuration

---

## 🎯 **Usage Examples**

### **Daily Development Workflow**
```bash
# Start work session
/project MyApp "Flutter e-commerce application"
/rule I prefer TypeScript over JavaScript
/workspace theme dark

# Check project status  
/analyze structure

# Find dependencies
/package npm react-navigation
/package pub provider

# Work and build
/build test

# End session context check
/context
/stats
```

### **Memory Management Workflow**
```bash
# Store project information and rules
/rule "Always use async/await for API calls"
/remember "This project uses Firebase for authentication"
/remember "Database schema updated on March 15th"

# List and manage rules
/list_rules async
/change_rule ab12cd34 "Always use async/await with error handling"
/delete_rule old_rule_id

# Later retrieve information
/recall "Firebase"
/recall "database schema"

# Check what's stored
/stats
```

### **Custom Command Creation**
```bash
# Add deployment command
/add-command /deploy "Deploy app to production" deploy_prod

# Add testing command  
/add-command /e2e "Run end-to-end tests" run_e2e_tests

# List all commands including custom
/commands

# Remove when no longer needed
/remove-command /e2e
```

---

## 🔧 **Technical Implementation**

### **Command Processing Flow**
1. **Detection**: Message starts with `/`
2. **Parsing**: Extract command, arguments, validation
3. **Routing**: Route to appropriate handler based on action
4. **Execution**: Direct tool access or memory operation
5. **Response**: Immediate formatted response

### **Memory Integration**
- **Custom Commands**: Stored as `custom_slash_commands` in memory
- **Project Info**: Stored as `current_project` key
- **Workspace Settings**: Stored as `workspace_settings` key
- **Persistence**: All custom commands survive server restarts

### **Error Handling**
- **Invalid Commands**: Suggests using `/commands`
- **Missing Arguments**: Shows proper usage syntax
- **Tool Failures**: Graceful error messages with context
- **Memory Errors**: Fallback to session-only storage

---

## 🚀 **Advanced Features**

### **Command Categories**
Commands are organized into logical categories for easy discovery:
- **memory**: Memory and rule management
- **development**: Build, package, analysis tools
- **system**: Help, command management
- **project**: Project and workspace management
- **custom**: User-created commands

### **Dynamic Extension**
The system supports runtime command addition:
```bash
# Add custom analysis command
/add-command /security "Run security audit" security_audit

# Add deployment pipeline command
/add-command /pipeline "Trigger CI/CD pipeline" trigger_pipeline
```

### **Memory-Driven Commands**
Commands automatically load from memory on server start:
- Custom commands persist across sessions
- Project context maintained
- Workspace settings remembered

---

## 💡 **Best Practices**

### **Command Naming**
- Use descriptive names: `/deploy-prod` vs `/dp`
- Follow existing patterns: `/analyze-security` vs `/sec`  
- Avoid conflicts with built-in commands

### **Memory Usage**
- Use `/rule` for coding preferences and guidelines
- Use `/remember` for project-specific information
- Use `/forget` to clean up outdated information
- Check `/stats` periodically to monitor memory usage

### **Project Workflow**
- Set project context early: `/project ProjectName Description`
- Configure workspace: `/workspace setting value`
- Use `/context` to check current state
- Leverage `/analyze` for project insights

### **Custom Commands**
- Document custom commands: `/add-command /mydoc "Generate documentation" doc_gen`
- Group related commands: `/deploy-dev`, `/deploy-prod`, `/deploy-staging`
- Clean up unused commands: `/remove-command /oldcommand`

---

## 🔍 **Troubleshooting**

### **Command Not Found**
```bash
❌ Unknown command '/typo'. Use /commands to see available commands.
```
**Solution**: Use `/commands` to see all available commands

### **Missing Arguments**
```bash
❌ Please provide a rule to save. Usage: /rule <rule_text>
```
**Solution**: Check command syntax with `/help <command>`

### **Memory Errors**
```bash
⚠️ Command added to session but failed to save to memory
```
**Solution**: Command works in session, check memory system status with `/stats`

### **Tool Failures**
```bash
❌ Git status error: Git command not found
```
**Solution**: Ensure required tools (git, npm, etc.) are installed

---

## 🎯 **Performance Benefits**

### **Speed Advantages**
- **Instant Response**: No orchestrator processing
- **Direct Tool Access**: Bypass keyword detection
- **Minimal Overhead**: Simple parsing and routing

### **Efficiency Gains**
- **Memory Caching**: Frequently used info readily available
- **Custom Workflows**: Personalized command shortcuts
- **Context Persistence**: Project info survives sessions

### **User Experience**
- **Predictable Interface**: Consistent command syntax
- **Self-Documenting**: Built-in help system
- **Extensible**: Add commands as needed

---

**🚀 The slash command system transforms your MCP server into a powerful, personalized development assistant with instant access to all tools and persistent memory integration!**