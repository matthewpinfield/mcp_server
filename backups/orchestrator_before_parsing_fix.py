#!/usr/bin/env python3
"""
Orchestrator module for intelligent tool routing and request analysis
Contains the should_use_* functions and primary routing logic
"""

import asyncio
import logging
from typing import Any, Dict, List

from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult
from langchain_ollama import ChatOllama

from config import (  # MVP Optimization imports
    AUTO_LINTER_KEYWORDS,
    BUILD_COMMAND_KEYWORDS,
    CALCULATION_KEYWORDS,
    DEFAULT_MODEL,
    DEV_WORKFLOW_KEYWORDS,
    ENABLE_DYNAMIC_SCALING,
    GIT_KEYWORDS,
    GITHUB_KEYWORDS,
    MEMORY_KEYWORDS,
    OLLAMA_API_BASE,
    PACKAGE_SEARCH_KEYWORDS,
    RAG_KEYWORDS,
    RAG_RESULTS_COMPLEX,
    RAG_RESULTS_RESEARCH,
    RAG_RESULTS_SIMPLE,
    REPO_ANALYSIS_KEYWORDS,
    SANDBOX_KEYWORDS,
    WEB_SEARCH_COMPLEX_QUERIES,
    WEB_SEARCH_KEYWORDS,
    WEB_SEARCH_RESEARCH_QUERIES,
    WEB_SEARCH_SIMPLE_QUERIES,
)

logger = logging.getLogger(__name__)


def get_model_temperature(model_name: str) -> float:
    """Get appropriate temperature for model type"""
    if "qwen" in model_name.lower() or "r1" in model_name.lower():
        return 0.7  # Higher temperature for thinking models
    else:
        return 0.1  # Lower temperature for standard models


def strip_thoughts_from_content(content_to_process: str) -> str:
    """Strip <think></think> blocks from Qwen3 output to prevent ReAct parsing errors"""
    final_speakable_content = ""
    while True:
        start_think_idx = content_to_process.find("<think>")
        end_think_idx = content_to_process.find("</think>")
        if (
            start_think_idx != -1
            and end_think_idx != -1
            and start_think_idx < end_think_idx
        ):
            final_speakable_content += content_to_process[:start_think_idx]
            content_to_process = content_to_process[end_think_idx + len("</think>") :]
        elif (
            start_think_idx != -1
            and end_think_idx == -1
            and len(content_to_process) > start_think_idx + 7
        ):
            final_speakable_content += content_to_process[:start_think_idx]
            break
        else:
            final_speakable_content += content_to_process
            break
    return final_speakable_content.strip()


def is_title_generation_request(user_message: str) -> bool:
    """Check if the request is for title generation (should skip most tools)"""
    user_message_lower = user_message.lower()
    title_patterns = [
        "generate a title",
        "create a title",
        "title for",
        "suggest a title",
        "what should i title",
        "name this",
        "title this",
    ]
    return any(pattern in user_message_lower for pattern in title_patterns)


async def analyze_complexity(user_message: str) -> bool:
    """Use LLM to intelligently determine if query requires deep thinking"""
    try:
        # Initialize lightweight LLM for complexity analysis
        complexity_llm = ChatOllama(
            model=DEFAULT_MODEL,
            base_url=OLLAMA_API_BASE,
            temperature=get_model_temperature(DEFAULT_MODEL),
        )

        # Craft analysis prompt
        analysis_prompt = f"""Analyze this user message and determine if it requires deep reasoning, complex problem-solving, or multi-step thinking.

User message: "{user_message}"

Examples of NO deep thinking (simple responses):
- "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "yes", "no", "bye"
- "good morning", "good afternoon", "good evening", "how are you", "fine", "great"
- "what time is it?", "what's the date?", "what day is it?"
- "nice", "cool", "awesome", "perfect", "sure", "exactly", "right"
- "I understand", "got it", "makes sense", "agreed", "correct"
- "please", "sorry", "excuse me", "pardon", "welcome"
- Simple acknowledgments and basic social interactions

Examples of YES deep thinking (complex analysis):
- "how does state management work?", "explain dependency injection"
- "debug this error", "why is my code not working?", "fix this bug"
- "create a function that...", "write code to...", "implement this feature"
- "refactor this code", "optimize this algorithm", "improve performance"
- "what's the difference between X and Y?", "compare these approaches"
- "how to implement...", "best practices for...", "recommended approach"
- "explain how this works", "walk me through this", "break this down"
- "analyze this code", "review my implementation", "check for issues"
- "design a system", "architect a solution", "plan this project"
- "troubleshoot this problem", "investigate this issue", "diagnose the error"
- "what are the pros and cons", "evaluate these options", "which is better"
- "how do I solve...", "help me figure out...", "guide me through..."
- Technical programming questions, coding problems, debugging, explanations
- Multi-step tasks, analysis, problem-solving, learning concepts

Respond with only: YES or NO"""

        # Get LLM analysis
        response = await complexity_llm.ainvoke([HumanMessage(content=analysis_prompt)])
        raw_response = response.content.strip()

        # Extract final answer after thinking blocks
        if "</think>" in raw_response:
            # Get content after the last </think> tag
            analysis = raw_response.split("</think>")[-1].strip().upper()
        else:
            analysis = raw_response.upper()

        # Return whether complex thinking is needed
        needs_thinking = "YES" in analysis
        logger.info(
            f"🧠 Complexity analysis for '{user_message}': {'COMPLEX' if needs_thinking else 'SIMPLE'}"
        )
        return needs_thinking

    except Exception as e:
        logger.error(f"Complexity analysis error: {e}, defaulting to thinking mode")
        # Fallback: if analysis fails, use thinking mode for safety
        return True


def is_simple_greeting_or_response(user_message: str) -> bool:
    """Fallback simple check - only for very obvious cases"""
    user_message_lower = user_message.lower().strip()

    # Only very short single-word responses
    if len(user_message_lower) <= 2:
        return True

    # Only exact matches for most common responses
    simple_exact = ["hi", "hey", "ok", "yes", "no", "bye", "thanks"]
    return user_message_lower in simple_exact


async def determine_query_complexity_with_llm(user_message: str) -> str:
    """Use LLM intelligence to determine appropriate data scaling level"""
    if not ENABLE_DYNAMIC_SCALING:
        return "standard"

    # Quick check for obvious simple cases
    if is_simple_greeting_or_response(user_message):
        return "simple"

    try:
        # Use LLM to intelligently assess data needs
        complexity_llm = ChatOllama(
            model=DEFAULT_MODEL,
            base_url=OLLAMA_API_BASE,
            temperature=get_model_temperature(DEFAULT_MODEL),
        )

        analysis_prompt = f"""Analyze this query and determine how much context/data would be helpful:

Query: "{user_message}"

Choose the appropriate data level:
- SIMPLE: Basic greeting, yes/no, minimal data needed
- STANDARD: Normal questions, moderate context helpful  
- COMPLEX: Technical problems, debugging, implementation - needs substantial context
- RESEARCH: Architecture, design patterns, comprehensive explanations - needs maximum context

Respond with only one word: SIMPLE, STANDARD, COMPLEX, or RESEARCH"""

        response = await complexity_llm.ainvoke([HumanMessage(content=analysis_prompt)])
        raw_response = response.content.strip()

        # Extract final answer (handle both case variations)
        if "</think>" in raw_response.lower():
            # Find the last thinking block end (case insensitive)
            import re

            thinking_pattern = r"</think>"
            matches = list(re.finditer(thinking_pattern, raw_response, re.IGNORECASE))
            if matches:
                last_match = matches[-1]
                analysis = raw_response[last_match.end() :].strip().upper()
            else:
                analysis = raw_response.upper()
        else:
            analysis = raw_response.upper()

        # Map response to our complexity levels
        if "SIMPLE" in analysis:
            return "simple"
        elif "COMPLEX" in analysis:
            return "complex"
        elif "RESEARCH" in analysis:
            return "research"
        else:
            return "standard"

    except Exception as e:
        logger.warning(f"LLM complexity analysis failed: {e}, using standard")
        return "standard"


def get_dynamic_limits(complexity_level: str) -> Dict[str, int]:
    """Get dynamic limits based on query complexity"""
    if not ENABLE_DYNAMIC_SCALING:
        return {
            "rag_results": 5,
            "web_results": 5,
            "tier1_interactions": 5,
            "tier3_semantic": 5,
        }

    limits = {
        "simple": {
            "rag_results": RAG_RESULTS_SIMPLE,
            "web_results": WEB_SEARCH_SIMPLE_QUERIES,
            "tier1_interactions": 3,
            "tier3_semantic": 3,
        },
        "standard": {
            "rag_results": 5,  # Original default
            "web_results": 5,  # Original default
            "tier1_interactions": 5,
            "tier3_semantic": 5,
        },
        "complex": {
            "rag_results": RAG_RESULTS_COMPLEX,
            "web_results": WEB_SEARCH_COMPLEX_QUERIES,
            "tier1_interactions": 8,
            "tier3_semantic": 8,
        },
        "research": {
            "rag_results": RAG_RESULTS_RESEARCH,
            "web_results": WEB_SEARCH_RESEARCH_QUERIES,
            "tier1_interactions": 8,
            "tier3_semantic": 8,
        },
    }

    return limits.get(complexity_level, limits["standard"])


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
    """Determine if web search tools should be made available to the agent using LLM-based intent analysis"""
    # Skip web search for title generation requests
    if is_title_generation_request(user_message):
        return False

    # For now, enable web search for ALL information requests
    # The LLM agent will decide whether to actually use it
    return True


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
    return any(
        keyword in user_message_lower
        for keyword in DEV_WORKFLOW_KEYWORDS
        + PACKAGE_SEARCH_KEYWORDS
        + BUILD_COMMAND_KEYWORDS
    )


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
    verification_patterns = [
        "does this work",
        "test this",
        "verify",
        "what happens",
        "output",
        "result",
    ]
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
        "naming convention",
        "correct naming",
        "use correct naming",
        "proper naming",
        "rename",
        "naming standards",
        "naming style",
        "camelcase",
        "snake_case",
        "pascalcase",
        "kebab-case",
    ]

    return any(keyword in user_message_lower for keyword in naming_keywords)


def should_use_refactor_workflow(user_message: str) -> bool:
    """Determine if the request requires refactor workflow"""
    if is_title_generation_request(user_message):
        return False

    user_message_lower = user_message.lower()

    refactor_keywords = [
        "refactor",
        "refactoring",
        "clean up",
        "improve code",
        "code improvement",
        "restructure",
        "reorganize",
        "optimize code",
        "clean code",
    ]

    # Check for code presence (code blocks or file extensions)
    has_code = "```" in user_message or any(
        ext in user_message_lower
        for ext in [".py", ".dart", ".js", ".java", ".cpp", ".c", ".go", ".rs"]
    )

    # SAFETY: Must NOT be a test request (those are dangerous)
    # Exclude test keywords that appear in filenames/paths
    test_action_keywords = [
        "run this",
        "execute this",
        "try this",
        "test this code",
        "can you run",
    ]
    is_test_request = any(
        keyword in user_message_lower for keyword in test_action_keywords
    )

    # Check for refactor analysis request
    has_refactor_request = any(
        keyword in user_message_lower for keyword in refactor_keywords
    )

    return has_code and has_refactor_request and not is_test_request


def should_use_test_workflow(user_message: str) -> bool:
    """Determine if the request requires test workflow (DANGEROUS - executes code)"""
    if is_title_generation_request(user_message):
        return False

    user_message_lower = user_message.lower()

    # DANGER: Test action phrases can modify/execute code
    test_keywords = [
        "run this",
        "execute this",
        "try this",
        "test this code",
        "does this work",
        "will this work",
        "can you run",
        "validate this",
        "verify this works",
        "check if this works",
    ]

    # Check for code presence
    has_code = "```" in user_message or any(
        ext in user_message_lower
        for ext in [".py", ".dart", ".js", ".java", ".cpp", ".c", ".go", ".rs"]
    )

    # SAFETY: Must NOT be a refactor request (those are read-only)
    refactor_keywords = [
        "refactor",
        "refactoring",
        "clean up",
        "improve code",
        "code improvement",
        "restructure",
        "reorganize",
        "clean code",
        "suggestions",
        "suggest improvements",
    ]
    is_refactor_request = any(
        keyword in user_message_lower for keyword in refactor_keywords
    )

    # Check for test request patterns
    has_test_request = any(keyword in user_message_lower for keyword in test_keywords)

    return has_code and has_test_request and not is_refactor_request


def get_tool_recommendations(user_message: str) -> Dict[str, bool]:
    """Get recommendations for which tool categories to activate - simplified for unified path"""
    # Always enable memory tools for consistent behavior
    recommendations = {
        "memory": True,  # Always available for context and learning
        "rag": should_use_rag_tools(user_message),
        "web_search": should_use_web_search(user_message),
        "git": should_use_git_tools(user_message),
        "github": should_use_github_tools(user_message),
        "dev_workflow": should_use_dev_workflow_tools(user_message),
        "repo_analysis": should_use_repo_analysis_tools(user_message),
        "auto_linter": should_use_auto_linter_tools(user_message),
        "sandbox": should_use_sandbox_tools(user_message),
    }

    # For title generation, only enable memory tools to minimize overhead
    if is_title_generation_request(user_message):
        return {key: False if key != "memory" else True for key in recommendations}

    # Note: We no longer use simple hardcoded checks here - let the agent decide tool usage dynamically

    return recommendations


def get_workflow_recommendations(user_message: str) -> Dict[str, bool]:
    """Get recommendations for which workflows to activate"""
    return {
        "naming_conventions": should_use_naming_conventions(user_message),
        "refactor": should_use_refactor_workflow(user_message),
        "test": should_use_test_workflow(user_message),
    }


async def execute_agent_request(
    messages: List[Dict],
    user_message: str,
    requested_model_name: str,
    tool_recommendations: Dict[str, bool],
) -> str:
    """Execute agent request with tools - moved from chat.py"""
    try:
        # Import all tool classes
        from tools import (
            LangchainCodeSearchTool,
            LangchainFlutterDocTool,
            LangchainGitBranchTool,
            LangchainGitCommitTool,
            LangchainGitDiffTool,
            LangchainGitLogTool,
            LangchainGitStatusTool,
            LangchainMemoryContextTool,
            LangchainMemoryCorrectionTool,
            LangchainMemoryRuleTool,
            LangchainMemorySaveTool,
            LangchainMemoryStatsTool,
            LangchainWebSearchTool,
            MultiLanguageSandboxTool,
            SandboxStatsTool,
        )

        # Get file access tools function
        def get_file_access_tools():
            from tools import (
                LangchainAutoLinterTool,
                LangchainBuildCommandTool,
                LangchainCodeMetricsTool,
                LangchainDateTimeTool,
                LangchainDependencyAnalysisTool,
                LangchainGitHubIssuesTool,
                LangchainGitHubReleasesTool,
                LangchainGitHubRepoSearchTool,
                LangchainPackageSearchTool,
                LangchainRepoExploreTool,
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
                "github_releases": LangchainGitHubReleasesTool,
            }

        # Set up base LLM with appropriate temperature for model type
        # Thinking models (like Qwen3) need higher temperature for diverse reasoning
        base_llm = ChatOllama(
            model=requested_model_name,
            base_url=OLLAMA_API_BASE,
            temperature=get_model_temperature(requested_model_name),
        )

        # Use base LLM directly
        llm = base_llm

        # Build tool list conditionally
        tools = []

        if tool_recommendations.get("memory"):
            tools.extend(
                [
                    LangchainMemoryContextTool(),
                    LangchainMemorySaveTool(),
                    LangchainMemoryRuleTool(),
                    LangchainMemoryStatsTool(),
                    LangchainMemoryCorrectionTool(),
                ]
            )
            logger.info("🧠 Added memory tools to agent")

        if tool_recommendations.get("rag"):
            tools.extend([LangchainFlutterDocTool(), LangchainCodeSearchTool()])
            logger.info("📚 Added RAG tools to agent")

        if tool_recommendations.get("web_search"):
            tools.append(LangchainWebSearchTool())
            logger.info("🔍 Added web search tool to agent")

        if tool_recommendations.get("git"):
            tools.extend(
                [
                    LangchainGitStatusTool(),
                    LangchainGitDiffTool(),
                    LangchainGitCommitTool(),
                    LangchainGitBranchTool(),
                    LangchainGitLogTool(),
                ]
            )
            logger.info("🔧 Added Git tools to agent")

        if tool_recommendations.get("github"):
            file_tools = get_file_access_tools()
            tools.extend(
                [
                    file_tools["github_repo_search"](),
                    file_tools["github_issues"](),
                    file_tools["github_releases"](),
                ]
            )
            logger.info("🐙 Added GitHub tools to agent")

        if tool_recommendations.get("repo_analysis"):
            file_tools = get_file_access_tools()
            tools.extend(
                [
                    file_tools["repo_explore"](),
                    file_tools["dependency_analysis"](),
                    file_tools["code_metrics"](),
                ]
            )
            logger.info("📊 Added repository analysis tools to agent")

        if tool_recommendations.get("dev_workflow"):
            file_tools = get_file_access_tools()
            tools.extend(
                [
                    file_tools["package_search"](),
                    file_tools["build_command"](),
                    file_tools["datetime"](),
                ]
            )
            logger.info("🔧 Added development workflow tools to agent")

        if tool_recommendations.get("auto_linter"):
            file_tools = get_file_access_tools()
            tools.append(file_tools["auto_linter"]())
            logger.info("🔍 Added auto-linter tool to agent")

        if tool_recommendations.get("sandbox"):
            tools.extend([MultiLanguageSandboxTool(), SandboxStatsTool()])
            logger.info("🔒 Added sandbox tools to agent")

        # Get base ReAct prompt
        base_prompt = hub.pull("hwchase17/react")

        # Get memory context for system message instead of prompt enhancement
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
            logger.error(f"Memory context retrieval error: {e}")

        # Create ReAct agent
        llm_with_system = llm

        # Create agent with tools using system-enhanced LLM
        agent = create_react_agent(llm_with_system, tools, base_prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors="Check messages and try to recover, or output the parsing error directly to the user.",
        )

        # Execute agent asynchronously
        lc_messages_history = []
        for msg in messages:
            if msg["role"] == "user":
                lc_messages_history.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages_history.append(AIMessage(content=msg["content"]))

        agent_input_data = {"input": user_message, "chat_history": lc_messages_history}

        # Execute agent completely FIRST
        logger.info(f"🤖 Invoking ReAct agent for query: '{user_message}'")
        result = await agent_executor.ainvoke(agent_input_data)
        agent_response = result.get("output", "[Agent did not return a final answer.]")

        # Only include tool execution details for sandbox tools (debugging needed)
        intermediate_steps = result.get("intermediate_steps", [])
        if intermediate_steps:
            for i, (action, observation) in enumerate(intermediate_steps):
                tool_name = getattr(action, "tool", "unknown_tool")
                # Only show details for sandbox tools that need debugging
                if tool_name in ["MultiLanguageSandboxTool", "SandboxStatsTool"]:
                    tool_input = getattr(action, "tool_input", "unknown_input")
                    tool_details = f"\n\n**Tool Execution Details:**\n"
                    tool_details += f"\n🔧 **{tool_name}** execution:\n"
                    tool_details += f"Input: {tool_input}\n"
                    tool_details += f"Full Output: {observation}\n"
                    agent_response += tool_details

        logger.info(f"🤖 Agent completed. Response length: {len(agent_response)}")

        # Save the interaction to memory automatically
        try:
            from tools.knowledge import mcp_save_interaction

            interaction_messages = messages + [
                {"role": "assistant", "content": agent_response}
            ]
            save_result = mcp_save_interaction(
                interaction_messages, {"type": "agent_conversation"}
            )
            if save_result.get("status") == "success":
                logger.info(
                    f"💾 Interaction automatically saved to memory: {save_result.get('interaction_id')}"
                )
            else:
                logger.warning(
                    f"Failed to auto-save interaction: {save_result.get('error')}"
                )
        except Exception as e:
            logger.error(f"Memory auto-save error: {e}")

        return agent_response

    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        raise e
