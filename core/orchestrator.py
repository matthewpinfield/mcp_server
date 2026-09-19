#!/usr/bin/env python3
"""
Simplified Orchestrator - All Tools with Memory Context
=======================================================
Single agent with all tools, uses existing memory tools for context.
"""

import logging
import uuid
from typing import Dict, List, Optional, AsyncGenerator

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import LANGCHAIN_AGENT_TIMEOUT, DEFAULT_MODEL, get_cached_llm
from tools.rules import get_user_rules, process_rules_slash_command

# Import shared tool instances from all_tools.py
from tools.all_tools import SHARED_TOOLS

# Import memory system for context retrieval
from tools.memory import get_memory_system

logger = logging.getLogger(__name__)


async def orchestrate_request(
    messages: List[Dict],
    user_message: str,
    requested_model_name: str,
    conversation_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Simplified orchestrator using existing tools for everything.
    """
    # Generate conversation ID if needed
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    # Handle slash commands
    if user_message.strip().startswith("/"):
        parts = user_message.strip().split(" ", 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # Route rules commands to rules.py
        if command in ["/rule", "/list_rules", "/delete_rule", "/change_rule"]:
            yield process_rules_slash_command(command, args)
            return

        # Unknown command
        yield f"Unknown command '{command}'. Use tools instead of slash commands."
        return

    # Load user rules (cached)
    try:
        user_rules = get_user_rules()
    except Exception as e:
        logger.error(f"Failed to load user rules: {e}")
        user_rules = ""

    # Use shared tool instances to avoid repeated instantiation
    tools = SHARED_TOOLS

    # Debug: Log available tools
    logger.info(f"Agent has {len(tools)} tools: {[t.name for t in tools]}")

    # Simple system prompt with conditional memory context
    system_prompt = f"""
Tool names: {', '.join(tool.name for tool in tools)}
### IMPORTANT: memory entries are supplied by the system not the user, example "**[chat_......]**" is from the system.
 
Use your last memory as context to ensure you have the most relevant information.

YOUR TRAINING DATA IT IS FROM 2023 and is considered of lower quality than the tools and memory context.

Memory workflow: Use search_memory with a query to find relevant conversations (returns IDs with summaries). If you need full conversation details, use get_full_memory with the specific memory ID.

User Rules:
{user_rules}

"""

    # Build clean chat history from messages (excluding the last one which is current user input)
    chat_history = []
    if messages and len(messages) > 1:
        for msg in messages[:-1]:
            role = "human" if msg.get("role") == "user" else "assistant"
            content = msg.get("content", "")
            
            # Extract content cleanly (sometimes IDEs send complex dicts for multi-modal)
            if isinstance(content, list):
                text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                content = " ".join(text_parts)
            elif not isinstance(content, str):
                content = str(content)
                
            if content.strip():
                chat_history.append((role, content.strip()))

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    # Get cached LLM instance - always use DEFAULT_MODEL for consistency
    llm = get_cached_llm(DEFAULT_MODEL)
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_execution_time=LANGCHAIN_AGENT_TIMEOUT,
        max_iterations=15,
        early_stopping_method="force",
    )

    # Execute with streaming
    full_response = ""
    error_occurred = False
    
    try:
        async for event in agent_executor.astream_events(
            {"input": user_message, "chat_history": chat_history}, 
            version="v2"
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                # Only stream content if this is NOT a tool call
                if chunk.content and not getattr(chunk, "tool_calls", None):
                    full_response += chunk.content
                    yield chunk.content
    except Exception as e:
        logger.error(f"Agent execution stream error: {e}")
        error_message = f"An error occurred during execution: {e}"
        full_response += error_message
        yield error_message
        error_occurred = True

    if not full_response and not error_occurred:
        full_response = "No response generated"
        yield full_response

    # Save memory (after full response has streamed out)
    try:
        memory_system = get_memory_system()
        memory_system.save_memory(user_message, full_response)
    except Exception as e:
        logger.error(f"Memory save failed: {e}")
