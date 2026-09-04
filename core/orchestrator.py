#!/usr/bin/env python3
"""
Orchestrator v2 - Simple Tool Dispatcher for Gemma4
=====================================================

This version removes the ReAct agent and lets Gemma4 handle reasoning natively.
The orchestrator simply:
1. Lets Gemma4 think with /think or /no_think
2. Parses any tool requests from Gemma4's output
3. Executes requested tools
4. Returns results to Gemma4
"""

from typing import Dict, Any, List, Optional
import logging
import asyncio
import json
import re
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from config import (
    MEMORY_KEYWORDS, RAG_KEYWORDS, WEB_SEARCH_KEYWORDS,
    GITHUB_KEYWORDS, DEV_WORKFLOW_KEYWORDS, PACKAGE_SEARCH_KEYWORDS, BUILD_COMMAND_KEYWORDS,
    REPO_ANALYSIS_KEYWORDS, AUTO_LINTER_KEYWORDS, SANDBOX_KEYWORDS,
    CALCULATION_KEYWORDS, OLLAMA_API_BASE, DEFAULT_MODEL
)

logger = logging.getLogger(__name__)

def get_model_temperature(model_name: str) -> float:
    """Get appropriate temperature for model type"""
    if "qwen" in model_name.lower() or "r1" in model_name.lower():
        return 0.7  # Higher temperature for thinking models
    else:
        return 0.1  # Lower temperature for standard models

def strip_thoughts_from_content(content_to_process: str) -> str:
    """Strip <think></think> blocks from Gemma4 output"""
    final_speakable_content = ""
    while True:
        start_think_idx = content_to_process.find('<think>')
        end_think_idx = content_to_process.find('</think>')
        if start_think_idx != -1 and end_think_idx != -1 and start_think_idx < end_think_idx:
            final_speakable_content += content_to_process[:start_think_idx]
            content_to_process = content_to_process[end_think_idx + len('</think>'):] 
        elif start_think_idx != -1 and end_think_idx == -1 and len(content_to_process) > start_think_idx + 7:
            final_speakable_content += content_to_process[:start_think_idx]
            break
        else:
            final_speakable_content += content_to_process
            break
    return final_speakable_content.strip()

def is_title_generation_request(user_message: str) -> bool:
    """Check if the request is for title generation"""
    user_message_lower = user_message.lower()
    title_patterns = [
        "generate a title", "create a title", "title for", "suggest a title",
        "what should i title", "name this", "title this"
    ]
    return any(pattern in user_message_lower for pattern in title_patterns)

def should_use_no_think(user_message: str) -> bool:
    """Simple pattern matching to determine if /no_think should be used"""
    NO_THINK_PATTERNS = [
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", 
        "yes", "no", "bye", "goodbye", "good morning", "good afternoon",
        "nice", "cool", "awesome", "perfect", "sure", "exactly", "right",
        "got it", "makes sense", "agreed", "correct"
    ]
    
    message_lower = user_message.lower().strip()
    
    # Check exact matches or very short messages
    if message_lower in NO_THINK_PATTERNS or len(message_lower) <= 3:
        logger.info(f"Using /no_think for simple message: '{user_message}'")
        return True
    
    logger.info(f"Using default thinking for complex message: '{user_message}'")
    return False

def is_simple_greeting_or_response(user_message: str) -> bool:
    """Fallback simple check - only for very obvious cases"""
    user_message_lower = user_message.lower().strip()
    
    # Only very short single-word responses
    if len(user_message_lower) <= 2:
        return True
    
    # Only exact matches for most common responses
    simple_exact = ['hi', 'hey', 'hello', 'ok', 'yes', 'no', 'bye', 'thanks']
    return user_message_lower in simple_exact

def should_use_tools(user_message: str) -> bool:
    """Determine if ANY tools should be available"""
    # Skip tools for title generation requests
    if is_title_generation_request(user_message):
        return False
    
    # Skip tools for simple greetings
    if is_simple_greeting_or_response(user_message):
        return False
    
    user_message_lower = user_message.lower()
    
    # Check for any tool-related keywords
    all_keywords = (
        MEMORY_KEYWORDS + RAG_KEYWORDS + WEB_SEARCH_KEYWORDS +
        GITHUB_KEYWORDS + DEV_WORKFLOW_KEYWORDS +
        PACKAGE_SEARCH_KEYWORDS + BUILD_COMMAND_KEYWORDS +
        REPO_ANALYSIS_KEYWORDS + AUTO_LINTER_KEYWORDS + SANDBOX_KEYWORDS +
        CALCULATION_KEYWORDS
    )
    
    return any(keyword in user_message_lower for keyword in all_keywords)

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

def analyze_tool_needs(user_message: str) -> Dict[str, bool]:
    """Intelligent tool analysis using improved pattern matching"""
    user_message_lower = user_message.lower()
    
    # Start with no tools
    tools = {
        "memory": False,
        "rag": False,
        "web_search": False,
        "github": False,
        "dev_workflow": False,
        "repo_analysis": False,
        "auto_linter": False,
        "sandbox": False
    }

    # Web search: temporal indicators or current information needs
    temporal_patterns = ["weather", "current", "latest", "recent", "today", "now", "new", "2024", "2025"]
    info_patterns = ["what's happening", "news", "status of", "is down", "traffic", "stock market"]
    if any(pattern in user_message_lower for pattern in temporal_patterns + info_patterns):
        tools["web_search"] = True
    
    # RAG: Flutter/Dart specific questions (not meta-conversations)
    flutter_patterns = ["flutter", "dart", "widget", "stateful", "stateless", "build context", "scaffold"]
    is_meta_conversation = any(word in user_message_lower for word in ["logs", "system", "agent", "tool", "orchestrator"])
    if any(pattern in user_message_lower for pattern in flutter_patterns) and not is_meta_conversation:
        tools["rag"] = True
    
    # GitHub: repository operations
    github_patterns = ["github", "repository", "repo", "pull request", "issue", "release"]
    if any(pattern in user_message_lower for pattern in github_patterns):
        tools["github"] = True
    
    # Sandbox: code execution, calculations
    execution_patterns = ["calculate", "run this", "execute", "test this", "what's the result", "```"]
    if any(pattern in user_message_lower for pattern in execution_patterns):
        tools["sandbox"] = True
    
    # Memory: always enable for context unless very simple
    if not is_simple_greeting_or_response(user_message):
        tools["memory"] = True
    
    return tools

def get_tool_recommendations(user_message: str) -> Dict[str, bool]:
    """Get recommendations for which tool categories to activate"""
    if is_title_generation_request(user_message):
        return {
            "memory": False,
            "rag": False,
            "web_search": False,
            "github": False,
            "dev_workflow": False,
            "repo_analysis": False,
            "auto_linter": False,
            "sandbox": False
        }
    
    if is_simple_greeting_or_response(user_message):
        return {
            "memory": False,
            "rag": False,
            "web_search": False,
            "github": False,
            "dev_workflow": False,
            "repo_analysis": False,
            "auto_linter": False,
            "sandbox": False
        }
    
    # Use intelligent pattern analysis
    return analyze_tool_needs(user_message)

def get_workflow_recommendations(user_message: str) -> Dict[str, bool]:
    """Get recommendations for which workflows to activate"""
    return {
        "naming_conventions": False,
        "refactor": False,
        "test": False
    }

def parse_tool_calls(qwen_response: str) -> List[Dict[str, Any]]:
    """Parse tool calls from Gemma4's natural language response"""
    # For now, return empty list - Gemma4 should handle most things directly
    # This can be enhanced later to parse natural language tool requests
    return []

async def execute_simple_request(messages: List[Dict], user_message: str, requested_model_name: str) -> str:
    """Execute a simple request directly with Gemma4 - no tools needed"""
    try:
        # Set up Gemma4 LLM
        llm = ChatOllama(
            model=requested_model_name,
            base_url=OLLAMA_API_BASE,
            temperature=get_model_temperature(requested_model_name)
        )
        
        # Get memory context for system message
        memory_context = ""
        try:
            from tools.knowledge import mcp_get_context
            memory_result = mcp_get_context(user_message, include_long_term=False)
            if memory_result.get("status") == "success":
                context = memory_result.get("context", {})
                profile = context.get("profile", {})
                rules = profile.get("rules", [])
                if rules:
                    memory_context = "IMPORTANT IDENTITY RULES:\n"
                    for rule in rules[:5]:  # Top 5 rules only for simple responses
                        rule_text = rule.get("rule", str(rule))
                        memory_context += f"- {rule_text}\n"
                    memory_context += "\nYou MUST follow these rules, especially regarding your identity and name.\n"
        except Exception as e:
            logger.error(f"Memory context retrieval error: {e}")
        
        # Convert messages to LangChain format
        lc_messages = []
        
        # Add system message with memory context if available
        if memory_context:
            lc_messages.append(SystemMessage(content=memory_context))
        
        # Add conversation history
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
        
        # Get response from Gemma4
        logger.info(f"Gemma4 direct request: '{user_message}'")
        response = await llm.ainvoke(lc_messages)
        raw_response = response.content.strip()
        
        # Log the raw response from Gemma4
        logger.info(f"\033[35mRAW AGENT OUTPUT:\n{raw_response}\033[0m")
        
        # Strip thinking blocks for final response
        final_response = strip_thoughts_from_content(raw_response)
        
        logger.info(f"Gemma4 completed. Response length: {len(final_response)}")
        
        # Save interaction to memory
        try:
            from tools.knowledge import mcp_save_interaction
            interaction_messages = messages + [{"role": "assistant", "content": final_response}]
            save_result = mcp_save_interaction(interaction_messages, {"type": "simple_conversation"})
            if save_result.get("status") == "success":
                logger.info(f"Interaction saved to memory: {save_result.get('interaction_id', 'unknown')}")
            else:
                logger.warning(f"Failed to save interaction: {save_result.get('error')}")
        except Exception as e:
            logger.error(f"Memory save error: {e}")
        
        return final_response
        
    except Exception as e:
        logger.error(f"Simple request execution error: {e}")
        raise e

SANDBOX_LANGUAGE_HINTS = {
    "python": "python", "py": "python",
    "javascript": "javascript", "js": "javascript",
    "typescript": "typescript", "ts": "typescript",
    "java": "java", "c++": "cpp", "cpp": "cpp", "c": "c",
    "go": "go", "golang": "go", "rust": "rust", "php": "php",
    "ruby": "ruby", "dart": "dart", "flutter": "flutter"
}

def extract_code_and_language(user_message: str) -> tuple:
    """Pull an executable code snippet and language hint out of a user message.

    Returns (code, language) or (None, None) if no code could be found.
    """
    fence_match = re.search(r"```(\w*)\s*\n?(.*?)```", user_message, re.DOTALL)
    if fence_match:
        code = fence_match.group(2).strip()
        language = SANDBOX_LANGUAGE_HINTS.get(fence_match.group(1).strip().lower())
    else:
        # Fallback: "run this code: <code>" style phrasing with no fences
        inline_match = re.search(r"code[^:]*:\s*(.+)$", user_message, re.IGNORECASE | re.DOTALL)
        code = inline_match.group(1).strip() if inline_match else None
        language = None

    if not code:
        return None, None

    if not language:
        lowered = user_message.lower()
        for hint, lang in SANDBOX_LANGUAGE_HINTS.items():
            if hint in lowered:
                language = lang
                break
        language = language or "python"

    return code, language

async def execute_complex_request(messages: List[Dict], user_message: str, requested_model_name: str, tool_recommendations: Dict[str, bool]) -> str:
    """Execute a complex request with tools available"""
    try:
        # Import all tool classes
        from tools import (
            LangchainMemoryContextTool,
            LangchainMemorySaveTool,
            LangchainMemoryRuleTool,
            LangchainMemoryStatsTool,
            LangchainMemoryCorrectionTool,
            MultiLanguageSandboxTool,
            SandboxStatsTool,
            LangchainWebSearchTool,
            LangchainFlutterDocTool,
            LangchainCodeSearchTool
        )

        # Get file access tools function
        def get_file_access_tools():
            from tools import (
                LangchainAutoLinterTool,
                LangchainRepoExploreTool,
                LangchainDependencyAnalysisTool,
                LangchainCodeMetricsTool,
                LangchainPackageSearchTool,
                LangchainBuildCommandTool,
                LangchainDateTimeTool,
                LangchainGitHubRepoSearchTool,
                LangchainGitHubIssuesTool,
                LangchainGitHubReleasesTool
            )
            return {
                "auto_linter": LangchainAutoLinterTool,
                "repo_explore": LangchainRepoExploreTool,
                "dependency_analysis": LangchainDependencyAnalysisTool,
                "code_metrics": LangchainCodeMetricsTool,
                "package_search": LangchainPackageSearchTool,
                "build_command": LangchainBuildCommandTool,
                "datetime": LangchainDateTimeTool,
                "github_repo_search": LangchainGitHubRepoSearchTool,
                "github_issues": LangchainGitHubIssuesTool,
                "github_releases": LangchainGitHubReleasesTool
            }

        # Build context from tools BEFORE Gemma4 call
        context_info = ""
        
        # Get memory context first
        if tool_recommendations.get("memory"):
            try:
                memory_tool = LangchainMemoryContextTool()
                memory_result = memory_tool._run(user_message)
                if memory_result and "No relevant context" not in memory_result:
                    context_info += f"\n--- MEMORY CONTEXT ---\n{memory_result}\n"
                    logger.info(f"\033[34mMemory tool result: {memory_result[:200]}...\033[0m")
                else:
                    logger.info("\033[34mMemory tool: No relevant context found\033[0m")
            except Exception as e:
                logger.error(f"Memory context error: {e}")
        
        # Get RAG context
        if tool_recommendations.get("rag"):
            try:
                # Try Flutter docs first
                flutter_tool = LangchainFlutterDocTool()
                flutter_result = flutter_tool._run(user_message)
                if flutter_result and "No relevant documentation" not in flutter_result:
                    context_info += f"\n--- FLUTTER DOCUMENTATION ---\n{flutter_result}\n"
                    logger.info(f"\033[33mFlutter docs result: {flutter_result[:200]}...\033[0m")
                else:
                    logger.info("\033[33mFlutter docs: No relevant documentation found\033[0m")
                
                # Try code search
                code_tool = LangchainCodeSearchTool()
                code_result = code_tool._run(user_message)
                if code_result and "No relevant code" not in code_result:
                    context_info += f"\n--- CODE EXAMPLES ---\n{code_result}\n"
                    logger.info(f"\033[33mCode search result: {code_result[:200]}...\033[0m")
                else:
                    logger.info("\033[33mCode search: No relevant code found\033[0m")
            except Exception as e:
                logger.error(f"RAG context error: {e}")
        
        # Get web search context
        if tool_recommendations.get("web_search"):
            try:
                web_tool = LangchainWebSearchTool()
                web_result = web_tool._run(user_message)
                if web_result and "No search results" not in web_result:
                    context_info += f"\n--- WEB SEARCH RESULTS ---\n{web_result}\n"
                    logger.info(f"\033[32mWeb search result: {web_result[:200]}...\033[0m")
                else:
                    logger.info("\033[32mWeb search: No search results found\033[0m")
            except Exception as e:
                logger.error(f"Web search error: {e}")

        # Get sandbox execution result
        if tool_recommendations.get("sandbox"):
            try:
                code, language = extract_code_and_language(user_message)
                if code:
                    sandbox_tool = MultiLanguageSandboxTool()
                    sandbox_result = sandbox_tool._run(json.dumps({"code": code, "language": language}))
                    context_info += f"\n--- SANDBOX EXECUTION RESULT (ACTUAL, VERIFIED OUTPUT) ---\n{sandbox_result}\n"
                    logger.info(f"\033[36mSandbox result: {sandbox_result[:200]}...\033[0m")
                else:
                    logger.info("\033[36mSandbox: No executable code found in message\033[0m")
            except Exception as e:
                logger.error(f"Sandbox execution error: {e}")

        # Set up Gemma4 LLM with enhanced context
        llm = ChatOllama(
            model=requested_model_name,
            base_url=OLLAMA_API_BASE,
            temperature=get_model_temperature(requested_model_name)
        )
        
        # Get memory rules for system message
        memory_context = ""
        try:
            from tools.knowledge import mcp_get_context
            memory_result = mcp_get_context(user_message, include_long_term=False)
            if memory_result.get("status") == "success":
                context = memory_result.get("context", {})
                profile = context.get("profile", {})
                rules = profile.get("rules", [])
                if rules:
                    memory_context = "IMPORTANT IDENTITY RULES:\n"
                    for rule in rules[:10]:  # Top 10 rules
                        rule_text = rule.get("rule", str(rule))
                        memory_context += f"- {rule_text}\n"
                    memory_context += "\nYou MUST follow these rules, especially regarding your identity and name.\n"
        except Exception as e:
            logger.error(f"Memory rules retrieval error: {e}")
        
        # Convert messages to LangChain format
        lc_messages = []
        
        # Add system message with memory rules and tool context
        system_content = ""
        if memory_context:
            system_content += memory_context + "\n"
        if context_info:
            system_content += f"REFERENCE INFORMATION:\n{context_info}\n"
            system_content += "Use this reference information to provide accurate, detailed responses.\n"
            if "SANDBOX EXECUTION RESULT" in context_info:
                system_content += "The sandbox result above is real, verified program output. Report it exactly as given - do not recompute or guess the output yourself.\n"
        
        if system_content:
            lc_messages.append(SystemMessage(content=system_content))
        
        # Add conversation history
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
        
        # Get response from Gemma4 with enhanced context
        logger.info(f"Gemma4 complex request with context: '{user_message}'")
        response = await llm.ainvoke(lc_messages)
        raw_response = response.content.strip()
        
        # Log the raw response from Gemma4
        logger.info(f"\033[35mRAW AGENT OUTPUT:\n{raw_response}\033[0m")
        
        # Strip thinking blocks for final response
        final_response = strip_thoughts_from_content(raw_response)
        
        logger.info(f"Gemma4 completed complex request. Response length: {len(final_response)}")
        
        # Save interaction to memory
        try:
            from tools.knowledge import mcp_save_interaction
            interaction_messages = messages + [{"role": "assistant", "content": final_response}]
            save_result = mcp_save_interaction(interaction_messages, {"type": "complex_conversation"})
            if save_result.get("status") == "success":
                logger.info(f"Interaction saved to memory: {save_result.get('interaction_id', 'unknown')}")
            else:
                logger.warning(f"Failed to save interaction: {save_result.get('error')}")
        except Exception as e:
            logger.error(f"Memory save error: {e}")
        
        return final_response
        
    except Exception as e:
        logger.error(f"Complex request execution error: {e}")
        raise e

async def execute_agent_request(messages: List[Dict], user_message: str, requested_model_name: str, tool_recommendations: Dict[str, bool]) -> str:
    """Main entry point - decides between simple and complex execution"""
    
    # Check if tools are needed
    needs_tools = any(tool_recommendations.values())
    
    if needs_tools:
        logger.info(f"Executing complex request with tools")
        return await execute_complex_request(messages, user_message, requested_model_name, tool_recommendations)
    else:
        logger.info(f"Executing simple request without tools")
        return await execute_simple_request(messages, user_message, requested_model_name)