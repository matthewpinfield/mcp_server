#!/usr/bin/env python3
"""
Orchestrator module for intelligent tool routing and request analysis
Contains the should_use_* functions and primary routing logic
"""

from typing import Dict, Any, List
from config import (
    MEMORY_KEYWORDS, RAG_KEYWORDS, WEB_SEARCH_KEYWORDS, GIT_KEYWORDS,
    GITHUB_KEYWORDS, DEV_WORKFLOW_KEYWORDS, PACKAGE_SEARCH_KEYWORDS, BUILD_COMMAND_KEYWORDS,
    REPO_ANALYSIS_KEYWORDS, AUTO_LINTER_KEYWORDS, SANDBOX_KEYWORDS,
    CALCULATION_KEYWORDS
)

def is_title_generation_request(user_message: str) -> bool:
    """Check if the request is for title generation (should skip most tools)"""
    user_message_lower = user_message.lower()
    title_patterns = [
        "generate a title", "create a title", "title for", "suggest a title",
        "what should i title", "name this", "title this"
    ]
    return any(pattern in user_message_lower for pattern in title_patterns)

def is_simple_greeting_or_response(user_message: str) -> bool:
    """Check if the message is a simple greeting or response that doesn't need tools"""
    user_message_lower = user_message.lower().strip()
    
    # Very short messages
    if len(user_message_lower) <= 3:
        return True
    
    # Common greetings and responses
    simple_patterns = [
        'hi', 'hello', 'hey', 'ok', 'yes', 'no', 'bye', 'thanks', 'thank you',
        'good morning', 'good afternoon', 'good evening', 'how are you',
        'fine', 'good', 'great', 'nice', 'cool', 'awesome', 'perfect'
    ]
    
    return user_message_lower in simple_patterns

def should_use_memory_tools(user_message: str) -> bool:
    """Determine if memory tools should be made available to the agent"""
    # Skip memory tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    
    # ALWAYS enable memory tools for identity - Continue ReAct agent needs them
    
    # For a memory-enabled assistant, always check memory for context
    # unless it's a very simple/short message that clearly doesn't need it
    user_message_lower = user_message.lower().strip()
    
    # Always use memory for longer conversations or explicit memory keywords
    if any(keyword in user_message_lower for keyword in MEMORY_KEYWORDS):
        return True
    
    # Enable memory for most normal conversations (default behavior)
    return True

def should_use_rag_tools(user_message: str) -> bool:
    """Determine if RAG tools should be made available to the agent"""
    # Skip RAG tools for title generation requests  
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in RAG_KEYWORDS)

def should_use_web_search(user_message: str) -> bool:
    """Determine if web search tools should be made available to the agent"""
    # Skip web search for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    
    # Check for explicit web search keywords
    if any(keyword in user_message_lower for keyword in WEB_SEARCH_KEYWORDS):
        return True
    
    # Check for temporal indicators (recent/current information)
    temporal_indicators = ["latest", "recent", "current", "new", "today", "this year", "2024", "2025"]
    if any(indicator in user_message_lower for indicator in temporal_indicators):
        return True
    
    # Check for information-seeking patterns
    info_patterns = ["what's happening", "what's new", "tell me about", "news about", "find information"]
    if any(pattern in user_message_lower for pattern in info_patterns):
        return True
    
    return False

def should_use_git_tools(user_message: str) -> bool:
    """Determine if Git tools should be made available to the agent"""
    # Skip Git tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in GIT_KEYWORDS)

def should_use_github_tools(user_message: str) -> bool:
    """Determine if GitHub API tools should be made available to the agent"""
    # Skip GitHub tools for title generation requests  
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in GITHUB_KEYWORDS)

def should_use_dev_workflow_tools(user_message: str) -> bool:
    """Determine if development workflow tools should be made available to the agent"""
    # Skip dev tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    # Check dev workflow, package search and build command keywords
    return any(keyword in user_message_lower for keyword in DEV_WORKFLOW_KEYWORDS + PACKAGE_SEARCH_KEYWORDS + BUILD_COMMAND_KEYWORDS)

def should_use_repo_analysis_tools(user_message: str) -> bool:
    """Determine if repository analysis tools should be made available to the agent"""
    # Skip repo analysis tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in REPO_ANALYSIS_KEYWORDS)

def should_use_auto_linter_tools(user_message: str) -> bool:
    """Determine if auto-linter tools should be made available to the agent"""
    # Skip auto-linter tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    return any(keyword in user_message_lower for keyword in AUTO_LINTER_KEYWORDS)

def should_use_sandbox_tools(user_message: str) -> bool:
    """Determine if sandbox tools should be made available to the agent"""
    # Skip sandbox tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    user_message_lower = user_message.lower()
    
    # Check for explicit sandbox/execution keywords
    if any(keyword in user_message_lower for keyword in SANDBOX_KEYWORDS):
        return True
    
    # Check for calculation requests
    if any(keyword in user_message_lower for keyword in CALCULATION_KEYWORDS):
        return True
    
    # Check for code verification patterns
    verification_patterns = ["does this work", "test this", "verify", "what happens", "output", "result"]
    if any(pattern in user_message_lower for pattern in verification_patterns):
        return True
    
    # Check if message contains code blocks (likely needs testing)
    if "```" in user_message or "def " in user_message or "print(" in user_message:
        return True
    
    return False

def should_use_naming_conventions(user_message: str) -> bool:
    """Determine if the request is about applying naming conventions"""
    if is_title_generation_request(user_message):
        return False
    
    user_message_lower = user_message.lower()
    
    naming_keywords = [
        "naming convention", "correct naming", "use correct naming",
        "proper naming", "rename", "naming standards", "naming style",
        "camelcase", "snake_case", "pascalcase", "kebab-case"
    ]
    
    return any(keyword in user_message_lower for keyword in naming_keywords)

def should_use_refactor_workflow(user_message: str) -> bool:
    """Determine if the request requires refactor workflow"""
    if is_title_generation_request(user_message):
        return False
    
    user_message_lower = user_message.lower()
    
    refactor_keywords = [
        "refactor", "refactoring", "clean up", "improve code", "code improvement",
        "restructure", "reorganize", "optimize code", "clean code"
    ]
    
    # Check for code presence (code blocks or file extensions)
    has_code = ("```" in user_message or 
                any(ext in user_message_lower for ext in [".py", ".dart", ".js", ".java", ".cpp", ".c", ".go", ".rs"]))
    
    # SAFETY: Must NOT be a test request (those are dangerous)
    # Exclude test keywords that appear in filenames/paths
    test_action_keywords = ["run this", "execute this", "try this", "test this code", "can you run"]
    is_test_request = any(keyword in user_message_lower for keyword in test_action_keywords)
    
    # Check for refactor analysis request
    has_refactor_request = any(keyword in user_message_lower for keyword in refactor_keywords)
    
    return has_code and has_refactor_request and not is_test_request

def should_use_test_workflow(user_message: str) -> bool:
    """Determine if the request requires test workflow (DANGEROUS - executes code)"""
    if is_title_generation_request(user_message):
        return False
    
    user_message_lower = user_message.lower()
    
    # DANGER: Test action phrases can modify/execute code
    test_keywords = [
        "run this", "execute this", "try this", "test this code", 
        "does this work", "will this work", "can you run", "validate this",
        "verify this works", "check if this works"
    ]
    
    # Check for code presence
    has_code = ("```" in user_message or 
                any(ext in user_message_lower for ext in [".py", ".dart", ".js", ".java", ".cpp", ".c", ".go", ".rs"]))
    
    # SAFETY: Must NOT be a refactor request (those are read-only)
    refactor_keywords = [
        "refactor", "refactoring", "clean up", "improve code", "code improvement",
        "restructure", "reorganize", "clean code", "suggestions", "suggest improvements"
    ]
    is_refactor_request = any(keyword in user_message_lower for keyword in refactor_keywords)
    
    # Check for test request patterns
    has_test_request = any(keyword in user_message_lower for keyword in test_keywords)
    
    return has_code and has_test_request and not is_refactor_request



def get_tool_recommendations(user_message: str) -> Dict[str, bool]:
    """Get recommendations for which tool categories to activate"""
    return {
        "memory": should_use_memory_tools(user_message),
        "rag": should_use_rag_tools(user_message),
        "web_search": should_use_web_search(user_message),
        "git": should_use_git_tools(user_message),
        "github": should_use_github_tools(user_message),
        "dev_workflow": should_use_dev_workflow_tools(user_message),
        "repo_analysis": should_use_repo_analysis_tools(user_message),
        "auto_linter": should_use_auto_linter_tools(user_message),
        "sandbox": should_use_sandbox_tools(user_message)
    }

def get_workflow_recommendations(user_message: str) -> Dict[str, bool]:
    """Get recommendations for which workflows to activate"""
    return {
        "naming_conventions": should_use_naming_conventions(user_message),
        "refactor": should_use_refactor_workflow(user_message),
        "test": should_use_test_workflow(user_message)
    }