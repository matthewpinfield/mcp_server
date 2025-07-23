#!/usr/bin/env python3
"""
Orchestrator V9 - Final Corrected Version
=====================================================
This version fixes the Pylance errors by adding proper type checking before
accessing message attributes. It correctly uses the modern LangChain
agentic loop, which is why it is more concise and powerful than the
original manual implementation.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from config import DEFAULT_MODEL, LANGCHAIN_AGENT_TIMEOUT, OLLAMA_API_BASE

# Import all tool classes dynamically from all_tools.py
from tools.all_tools import *

# --- Tool Integration ---
# Import the correct, decorator-based tool from tools.web
from tools.web import search_web

logger = logging.getLogger(__name__)


def strip_thoughts_from_content(content_to_process: str) -> str:
    """Strip <think></think> blocks from Qwen3 output"""
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


# --- Function Wrappers for Class-Based Tools ---
@tool
def memory_context(query: str) -> str:
    """Retrieve relevant context from memory"""
    return LangchainMemoryContextTool()._run(query)


@tool
def memory_save(content: str) -> str:
    """Save information to memory"""
    return LangchainMemorySaveTool()._run(content)


@tool
def memory_rule(rule: str) -> str:
    """Add or manage memory rules"""
    return LangchainMemoryRuleTool()._run(rule)


@tool
def memory_stats() -> str:
    """Get memory system statistics"""
    return LangchainMemoryStatsTool()._run()


@tool
def memory_correction(correction: str) -> str:
    """Correct memory information"""
    return LangchainMemoryCorrectionTool()._run(correction)


@tool
def sandbox_execute(code: str, language: str = "python") -> str:
    """Execute code in secure sandbox"""
    return MultiLanguageSandboxTool()._run(
        f'{{"code": "{code}", "language": "{language}"}}'
    )


@tool
def sandbox_stats() -> str:
    """Get sandbox execution statistics"""
    return SandboxStatsTool()._run()


@tool
def git_status() -> str:
    """Get git repository status"""
    return LangchainGitStatusTool()._run("")


@tool
def git_diff() -> str:
    """Show git differences"""
    return LangchainGitDiffTool()._run("")


@tool
def git_commit(message: str) -> str:
    """Create git commit"""
    return LangchainGitCommitTool()._run(message)


@tool
def git_branch(action: str = "list") -> str:
    """Manage git branches"""
    return LangchainGitBranchTool()._run(action)


@tool
def git_log() -> str:
    """Show git commit history"""
    return LangchainGitLogTool()._run("")


@tool
def flutter_docs(query: str) -> str:
    """Search Flutter documentation"""
    return LangchainFlutterDocTool()._run(query)


@tool
def code_search(query: str) -> str:
    """Search code examples"""
    return LangchainCodeSearchTool()._run(query)


@tool
def auto_linter(path: str) -> str:
    """Run automatic code linting"""
    return LangchainAutoLinterTool()._run(path)


@tool
def repo_explore(path: str) -> str:
    """Explore repository structure"""
    return LangchainRepoExploreTool()._run(path)


@tool
def dependency_analysis(path: str) -> str:
    """Analyze project dependencies"""
    return LangchainDependencyAnalysisTool()._run(path)


@tool
def code_metrics(path: str) -> str:
    """Calculate code metrics"""
    return LangchainCodeMetricsTool()._run(path)


@tool
def build_command(command: str) -> str:
    """Execute build commands"""
    return LangchainBuildCommandTool()._run(command)


@tool
def package_search(package: str, ecosystem: str = "auto") -> str:
    """Search for packages"""
    return LangchainPackageSearchTool()._run(ecosystem, package)


@tool
def get_datetime() -> str:
    """Get current date and time"""
    return LangchainDateTimeTool()._run()


@tool
def github_repo_search(query: str) -> str:
    """Search GitHub repositories"""
    return LangchainGitHubRepoSearchTool()._run(query)


@tool
def github_issues(repo: str) -> str:
    """Get GitHub repository issues"""
    return LangchainGitHubIssuesTool()._run(repo)


@tool
def github_releases(repo: str) -> str:
    """Get GitHub repository releases"""
    return LangchainGitHubReleasesTool()._run(repo)


@tool
def read_system_file(
    file_path: str, encoding: str = "utf-8", max_lines: int = 400
) -> str:
    """Read any file from anywhere on the Ubuntu Linux system"""
    return LangchainSystemFileReaderTool()._run(file_path, encoding, max_lines)


# --- Core Execution Logic ---


async def orchestrate_request(
    messages: List[Dict], user_message: str, requested_model_name: str
) -> str:
    """
    Manages an agentic loop where the LLM can decide to call tools.
    """
    # --- 1. Initialize ---

    # Use function wrappers for class-based tools + decorator-based tools
    all_tools = [
        # Memory tools
        memory_context,
        memory_save,
        memory_rule,
        memory_stats,
        memory_correction,
        # Sandbox tools
        sandbox_execute,
        sandbox_stats,
        # Git tools
        git_status,
        git_diff,
        git_commit,
        git_branch,
        git_log,
        # Code analysis tools
        flutter_docs,
        code_search,
        auto_linter,
        repo_explore,
        dependency_analysis,
        code_metrics,
        # System file reader
        read_system_file,
        # Development tools
        build_command,
        package_search,
        get_datetime,
        # GitHub tools
        github_repo_search,
        github_issues,
        github_releases,
        # Web search tool (decorator-based)
        search_web,
    ]

    # The LangChain Ollama integration with .bind_tools will handle the agent loop
    llm_with_tools = ChatOllama(
        model=requested_model_name,
        base_url=OLLAMA_API_BASE,
    ).bind_tools(
        all_tools
    )  # Bind all 25 function-based tools to the LLM

    available_tools = {tool.name: tool for tool in all_tools}

    # --- 2. Get Memory Context using agent's tool system ---
    memory_context_text = ""
    try:
        # Use the tool wrapper to get memory context
        memory_result_raw = memory_context(user_message)

        # Parse the result (it comes back as a string from the tool)
        import json

        try:
            memory_result = json.loads(memory_result_raw)
        except:
            # If not JSON, treat as plain text
            memory_result = {
                "status": "success",
                "context": {"profile": {}, "short_term": []},
            }
            if memory_result_raw and "No relevant context" not in memory_result_raw:
                memory_context_text += f"MEMORY CONTEXT:\n{memory_result_raw}\n\n"

        if memory_result.get("status") == "success":
            context = memory_result.get("context", {})

            # Add rules from profile
            rules = context.get("profile", {}).get("rules", [])
            if rules:
                rule_lines = [f"- {rule.get('rule', str(rule))}" for rule in rules]
                rules_text = "\n".join(rule_lines)
                memory_context_text += (
                    "IMPORTANT IDENTITY RULES:\n"
                    f"{rules_text}\n"
                    "\nYou MUST follow these rules, especially regarding your identity and name.\n\n"
                )

            # Add recent conversation context
            short_term = context.get("short_term", [])
            if short_term:
                memory_context_text += "RECENT CONVERSATION CONTEXT:\n"
                # Use last 3 interactions to keep context manageable
                for item in short_term[-3:]:
                    messages = item.get("messages", [])
                    for msg in messages:
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if content:  # Include all content, truncate if needed
                            truncated_content = (
                                content[:200] if len(content) > 200 else content
                            )
                            memory_context_text += f"- {role}: {truncated_content}{'...' if len(content) > 200 else ''}\n"
                memory_context_text += "\n"

    except Exception as e:
        logger.error(f"Memory context retrieval error: {e}")

    # --- 3. Construct the System Prompt ---
    # Use 2025 best practices: Rules first, then capabilities, with strong enforcement
    system_prompt = (
        # Step 1: Safety scaffolding - force rule evaluation
        "CRITICAL: Before responding, you MUST evaluate if your response follows ALL rules below.\n"
        "If any rule would be violated, stop and revise your response.\n\n"
        # Step 2: Core rules from memory
        f"{memory_context_text}\n"
        # Step 3: Enforcement reminder
        "ENFORCEMENT: These rules are non-negotiable. Violating them is unacceptable.\n"
        "Check your response against EVERY rule before finalizing.\n\n"
        # Step 4: Capabilities (tool usage)
        "CAPABILITIES:\n"
        "You have access to tools for various tasks. Use them appropriately.\n"
        "Tools include: web search, memory management, code analysis, git operations, sandbox execution.\n\n"
        # Step 5: Final enforcement
        "FINAL CHECK: Does your response violate ANY rule above? If yes, revise it."
    )

    # DEBUG: Log the EXACT system prompt being sent to LLM
    logger.info(f"DEBUG: EXACT SYSTEM PROMPT SENT TO LLM:\n{system_prompt}")
    logger.info(f"DEBUG: System prompt length: {len(system_prompt)}")

    # --- 3. Prepare Initial Messages ---
    lc_messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
    for msg in messages:
        role, content = msg.get("role"), msg.get("content")
        if content:
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

    lc_messages.append(HumanMessage(content=user_message))

    # --- 4. Start the Agentic Loop ---
    try:
        logger.info("Invoking LLM with tools...")
        # The first response from the LLM might be an answer or a tool call
        response = llm_with_tools.invoke(lc_messages)

        # Get response content directly
        processed_content = str(response.content)

        # Log the processed response content for debugging
        logger.info(f"RAW AGENT OUTPUT:\n{response.content}")
        logger.info(
            f"LLM request completed. Response length: {len(str(response.content))}"
        )

        # FIX: Add a type check to safely access .tool_calls
        if isinstance(response, AIMessage) and response.tool_calls:
            logger.info(f"Agent requested tool(s): {response.tool_calls}")
            # Append the agent's request to the message history
            lc_messages.append(response)

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                if tool_name in available_tools:
                    logger.info(f"Executing tool: {tool_name} with args {tool_args}")
                    try:
                        tool_output = available_tools[tool_name].invoke(tool_args)
                        # Append the result of the tool call to the history
                        lc_messages.append(
                            ToolMessage(
                                content=str(tool_output), tool_call_id=tool_call["id"]
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}")
                        # Append an error message if the tool fails
                        lc_messages.append(
                            ToolMessage(
                                content=f"Error: {e}", tool_call_id=tool_call["id"]
                            )
                        )
                else:
                    logger.warning(f"Agent requested an unknown tool: '{tool_name}'")
                    lc_messages.append(
                        ToolMessage(
                            content=f"Error: Tool '{tool_name}' not found.",
                            tool_call_id=tool_call["id"],
                        )
                    )

            # Invoke the model again with the tool results in the context
            logger.info("Re-invoking LLM with tool result(s)...")
            final_response_message = llm_with_tools.invoke(lc_messages)

            # Get final response content directly
            final_processed_content = str(final_response_message.content)

            # Log the final response content (including thinking blocks) for debugging
            logger.info(f"FINAL AGENT OUTPUT:\n{final_processed_content}")
            # FIX: Ensure the final content is always a string and strip thinking blocks
            return strip_thoughts_from_content(final_processed_content)

        # If no tool call was made, return the content directly
        # FIX: Ensure the final content is always a string and strip thinking blocks
        return strip_thoughts_from_content(processed_content)

    except Exception as e:
        logger.error(f"Orchestrator request failed: {e}", exc_info=True)
        return f"An error occurred during agent execution: {str(e)}"
