#!/usr/bin/env python3
"""
Simplified Orchestrator - All Tools with Memory Context
=======================================================
Single agent with all tools, uses existing memory tools for context.
"""

import logging
import uuid
from typing import Dict, List, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import LANGCHAIN_AGENT_TIMEOUT, OLLAMA_API_BASE, DEFAULT_MODEL
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
) -> str:
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
            return process_rules_slash_command(command, args)

        # Unknown command
        return f"Unknown command '{command}'. Use tools instead of slash commands."

    # Load user rules (cached)
    try:
        user_rules = get_user_rules()
    except Exception as e:
        logger.error(f"Failed to load user rules: {e}")
        user_rules = ""

    # Use shared tool instances to avoid repeated instantiation
    tools = SHARED_TOOLS

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

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    # Create LLM instance - always use DEFAULT_MODEL for consistency
    from langchain_ollama import ChatOllama

    llm = ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_API_BASE)
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

    # Execute
    response = await agent_executor.ainvoke({"input": user_message})
    final_response = response.get("output", "No response generated")

    # Save memory (wait for completion to ensure it happens)
    try:
        memory_system = get_memory_system()
        memory_system.save_memory(user_message, final_response)
    except Exception as e:
        logger.error(f"Memory save failed: {e}")

    return final_response
