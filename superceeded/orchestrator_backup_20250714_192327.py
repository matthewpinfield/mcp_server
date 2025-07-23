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
from typing import Any, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_ollama import ChatOllama

# --- Tool Integration ---
# Import the correct, decorator-based tool from tools.web
from tools.web import search_web

# Dummy config for standalone execution
try:
    from config import DEFAULT_MODEL, OLLAMA_API_BASE
except ImportError:
    print("Warning: config.py not found. Using dummy values for testing.")
    OLLAMA_API_BASE = "http://localhost:11434"
    DEFAULT_MODEL = "qwen2:7b"


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


# --- Core Execution Logic ---


async def orchestrate_request(
    messages: List[Dict], user_message: str, requested_model_name: str
) -> str:
    """
    Manages an agentic loop where the LLM can decide to call tools.
    """
    # --- 1. Initialize ---
    # The LangChain Ollama integration with .bind_tools will handle the agent loop
    llm_with_tools = ChatOllama(
        model=requested_model_name,
        base_url=OLLAMA_API_BASE,
        temperature=0.1,  # Lower temperature for more predictable tool use
    ).bind_tools(
        [search_web]
    )  # Bind the imported tool to the LLM

    available_tools = {search_web.name: search_web}

    # --- 2. Construct the System Prompt ---
    system_prompt = (
        "You are a helpful assistant. You have access to tools. "
        "To use a tool, you MUST respond with a JSON object that conforms to the tool's schema. "
        "The user will not see your tool calls. After a tool is called and you get the result, "
        "formulate a final, natural language answer to the user based on the tool's output."
    )

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
            # FIX: Ensure the final content is always a string
            return str(final_response_message.content)

        # If no tool call was made, return the content directly
        # FIX: Ensure the final content is always a string
        return str(response.content)

    except Exception as e:
        logger.error(f"Orchestrator request failed: {e}", exc_info=True)
        return f"An error occurred during agent execution: {str(e)}"
