# Claude Memory - Project Knowledge Base

This file contains persistent knowledge that Claude should remember about this project and general development practices.

## Naming Conventions by Language

### Python
- **Variables, functions, methods** → `snake_case`
- **Classes** → `PascalCase` 
- **Constants** → `SCREAMING_SNAKE_CASE`
- **Files, modules** → `snake_case`
- **Packages** → `snake_case`

### Dart/Flutter
- **Variables, functions, methods** → `camelCase`
- **Classes, types, enums** → `PascalCase`
- **Constants** → `lowerCamelCase` (NOT SCREAMING_SNAKE_CASE)
- **Files, directories** → `snake_case`
- **Package names** → `snake_case`

### JavaScript/TypeScript
- **Variables, functions** → `camelCase`
- **Classes, interfaces** → `PascalCase`
- **Constants** → `SCREAMING_SNAKE_CASE` or `camelCase`
- **Files** → `camelCase` or `kebab-case`

### General CSS/HTML
- **CSS classes, IDs** → `kebab-case`
- **HTML attributes** → `kebab-case`

## Project-Specific Guidelines

### MCP Server Development
- Use Python snake_case conventions
- Tool names should be descriptive: `LangchainAutoLinterTool`
- Function names should be clear: `should_use_code_analysis_workflow`

### Code Analysis Workflow
- Sequential execution is preferred over parallel tool chaos
- Always follow the 6-step analysis process:
  1. Static Analysis
  2. Code Understanding  
  3. Architecture Review
  4. Performance Analysis
  5. Enhancement Suggestions
  6. Final Report

### When User Says "Use Correct Naming Conventions"
- Apply the language-specific conventions listed above
- If language is unclear, ask for clarification
- Default to the most common convention for the detected language
- Explain why specific conventions are being used

## Development Preferences
- **Refactor existing files** rather than creating new ones
- **Sequential workflows** over parallel tool execution
- **Comprehensive error handling** with graceful fallbacks
- **Detailed logging** for debugging and monitoring