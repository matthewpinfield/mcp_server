#!/usr/bin/env python3
"""
Simplified Orchestrator - All Tools with Memory Context
=======================================================
Single agent with all tools, uses existing memory tools for context.
"""

import logging
import re
import uuid
from typing import Dict, List, Optional, AsyncGenerator

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import LANGCHAIN_AGENT_TIMEOUT, DEFAULT_MODEL, get_cached_llm
from tools.rules import get_user_rules, process_rules_slash_command

# Import shared tool instances from all_tools.py
from tools.all_tools import SHARED_TOOLS

# Import memory system for context retrieval
from tools.memory import get_memory_system

logger = logging.getLogger(__name__)

# --- Autopilot toggle: controls whether the agent keeps working through a
# whole multi-step task unprompted, or stops after each step/batch to check
# in. On by default (matches the verified-working autonomous behavior).
# Persisted in Redis so it survives across requests and server restarts,
# same store used by the memory system.
_AUTOPILOT_REDIS_KEY = "settings:autopilot_enabled"


def is_autopilot_enabled() -> bool:
    try:
        from tools.memory import get_redis_connection

        value = get_redis_connection().get(_AUTOPILOT_REDIS_KEY)
        return value != "false"  # unset (None) or "true" both mean ON
    except Exception as e:
        logger.error(f"Failed to read autopilot setting: {e}")
        return True


def set_autopilot(enabled: bool) -> None:
    from tools.memory import get_redis_connection

    get_redis_connection().set(_AUTOPILOT_REDIS_KEY, "true" if enabled else "false")


# Words/phrases that indicate the model is narrating an action it intends to
# take, rather than reporting one it already took via a real tool call. If a
# turn ends with this kind of text and NO tool was actually invoked, the
# agent has stalled - it announced work and stopped, leaving the user
# waiting. This is a known failure mode of tool-calling models under long
# context: they sometimes describe the next step instead of emitting the
# structured tool call for it.
NARRATION_STALL_PATTERN = re.compile(
    r"\bI(?:'ll|'m| will| am)\s+(?:now\s+|first\s+|just\s+|also\s+)?"
    r"(?:going to\s+)?"
    r"(check(?:ing)?|read(?:ing)?|writ(?:e|ing)|creat(?:e|ing)|"
    r"execut(?:e|ing)|run(?:ning)?|call(?:ing)?|us(?:e|ing)|"
    r"try(?:ing)?|attempt(?:ing)?|proceed(?:ing)?|start(?:ing)?|"
    r"look(?:ing)?|verify(?:ing)?|explor(?:e|ing)|build(?:ing)?|"
    r"implement(?:ing)?|continue|now)\b"
    r"|\blet me now\b|<call:",
    re.IGNORECASE,
)


def _has_repetition_loop(text: str, min_repeats: int = 3) -> bool:
    """
    Detect a degenerate repetition loop: the model repeating essentially the
    same sentence/line verbatim several times in a row instead of acting.
    Checked periodically while streaming so a runaway loop can be cut off
    immediately instead of running to completion.
    """
    parts = [p.strip() for p in re.split(r"[\n.]+", text) if len(p.strip()) > 15]
    if len(parts) < min_repeats:
        return False
    last = parts[-1]
    return all(p == last for p in parts[-min_repeats:])


# Model name Continue is configured to use for its Edit/Apply roles (see
# ~/.continue/config.yaml). Requests with this model name bypass the tool
# agent entirely - Continue's Edit/Apply features need clean code output
# honoring THEIR OWN system prompt, not our chat-assistant one.
DIRECT_COMPLETION_MODEL = "gemma4-direct-edit"


async def direct_completion(messages: List[Dict]) -> AsyncGenerator[str, None]:
    """
    Lightweight passthrough for Continue's Edit/Apply roles: no tools, no
    memory, no system-prompt override. Honors whatever system/user messages
    Continue sends exactly as given, and streams raw model output back
    untouched so Continue can apply it as a clean inline diff.
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    lc_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
            )
        elif not isinstance(content, str):
            content = str(content)

        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))

    llm = get_cached_llm(DEFAULT_MODEL)
    async for chunk in llm.astream(lc_messages):
        if chunk.content:
            yield chunk.content


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

        # Autopilot toggle: controls whether the agent runs a whole
        # multi-step task unprompted, or stops after each step to check in.
        if command == "/autopilot":
            arg = args.strip().lower()
            if arg == "on":
                set_autopilot(True)
                yield "Autopilot is now **ON**. I'll keep working through a multi-step task (e.g. building a new project) without stopping to check in, until it's done or I hit a real blocker."
            elif arg == "off":
                set_autopilot(False)
                yield "Autopilot is now **OFF**. I'll pause and check in with you between steps/batches on multi-step tasks."
            else:
                state = "ON" if is_autopilot_enabled() else "OFF"
                yield f"Autopilot is currently **{state}**. Use `/autopilot on` or `/autopilot off` to change it."
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

    autopilot_on = is_autopilot_enabled()
    if autopilot_on:
        autopilot_prompt = """### IMPORTANT: autopilot is ON for multi-step tasks (e.g. building a new project from scratch):
If the user asks you to proceed until a task/project is complete, or to keep going without stopping to check in, treat that as standing confirmation to write ALL the new files in your plan, not just the first one. Do not announce a plan ("I will start with Batch 1...") and then end your turn - actually call write_file for every file in that batch, then immediately continue to the next batch and do the same, in the SAME turn, without pausing to ask permission again. Only stop early if you hit a real blocker: a tool error you cannot resolve, or a genuine decision only the user can make (e.g. which of two conflicting approaches to take). A batch boundary or having announced what you're about to do is NOT a reason to stop - stop only when the whole task is actually finished or you are genuinely blocked."""
    else:
        autopilot_prompt = """### IMPORTANT: autopilot is OFF for multi-step tasks:
On a multi-step task (e.g. building a new project from scratch), plan out the batches, complete ONE batch (calling write_file for the files in it), then stop and summarize what you did and what's next, letting the user confirm before you continue to the next batch. The user can turn autopilot on with `/autopilot on` if they want you to run through the whole plan unprompted instead."""

    # Simple system prompt with conditional memory context
    system_prompt = f"""
Tool names: {', '.join(tool.name for tool in tools)}
### IMPORTANT: memory entries are supplied by the system not the user, example "**[chat_......]**" is from the system.
 
Use your last memory as context to ensure you have the most relevant information.

YOUR TRAINING DATA IT IS FROM 2023 and is considered of lower quality than the tools and memory context.

Memory workflow: Use search_memory with a query to find relevant conversations (returns IDs with summaries). If you need full conversation details, use get_full_memory with the specific memory ID.

### IMPORTANT: filesystem access - two separate, unrelated filesystems exist:
1. read_system_file, explore_repository, write_file, and analyze_dependencies operate directly on THIS machine's real filesystem. They can access ANY absolute path the user gives you, anywhere on the system (e.g. /home/username/..., /mnt/..., /opt/...). Never claim these tools are restricted to a specific mounted folder.
2. execute_code is the ONLY sandboxed tool. It runs code inside a temporary, isolated Docker container with its own separate filesystem (which happens to mount the submitted code at /code). That /code path exists ONLY inside that one-off sandbox container and has NOTHING to do with the user's real files or with any other tool.
If a file read fails, the most likely cause is a wrong or relative path - ask the user for the exact absolute path, or use explore_repository to look around, rather than assuming you are "containerized" or restricted to /code.
If the user names a file or folder WITHOUT giving a full absolute path (e.g. "read project_brief.md" instead of "/home/user/project/project_brief.md"), ask them for the absolute path FIRST. Do not guess by trying read_system_file, explore_repository, execute_code, and git tools one after another - that wastes many slow tool calls. One clarifying question is faster than five guesses.

### IMPORTANT: how to deliver code changes (Cursor-style, diff-first workflow):
When the user asks you to write or change code in an EXISTING file, do NOT call write_file. Instead, reply with the code as a markdown code block in chat. The user will review it and click "Apply" in their editor (Continue IDE), which shows them a real inline diff to accept or reject before anything touches disk - this is the same model Cursor uses for Cmd+K and chat-apply. Calling write_file skips that review entirely and silently overwrites the file, which is what we are trying to avoid.
CRITICAL: Continue's "Apply" button can only work out which file a code block belongs to if you put the file path in the code fence's info string, right after the language, e.g. ```python src/main.py. This path MUST be RELATIVE to the project root, NOT the full absolute path (Continue has a known bug where giving it an absolute path causes it to wrongly double-prepend the project root, producing a broken path and "Could not resolve filepath" errors). Even though you use full absolute paths for your own tools (read_system_file, write_file, etc.), strip the project's root directory off before putting the path in the code fence - e.g. if the project root is /home/user/myproject and you edited /home/user/myproject/src/main.py, the fence must read ```python src/main.py, not the full absolute path.
Only use write_file when the user explicitly asks you to create/save a brand-new file directly (not edit an existing one) AND has clearly confirmed they want it written immediately without reviewing a diff first.

{autopilot_prompt}

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
        max_iterations=40,  # raised from 15 to give room for multi-batch autonomous builds
        early_stopping_method="force",
    )

    async def _run_agent_turn(agent_input: str, history):
        """Run one AgentExecutor turn, streaming content chunks and reporting
        whether any tool was actually invoked."""
        text = ""
        tool_called = False
        async for event in agent_executor.astream_events(
            {"input": agent_input, "chat_history": history},
            version="v2",
        ):
            kind = event["event"]
            if kind == "on_tool_start":
                tool_called = True
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content and not getattr(chunk, "tool_calls", None):
                    text += chunk.content
                    yield ("content", chunk.content)
                    # Only worth checking once a sentence/line boundary just
                    # completed - cheap early-out, avoids re-splitting on
                    # every tiny token chunk.
                    if any(c in chunk.content for c in ".\n") and _has_repetition_loop(text):
                        logger.info("Detected mid-stream repetition loop - aborting this generation early")
                        break
        yield ("done", (text, tool_called))

    # Execute with streaming, auto-nudging if the model stalls: either it
    # narrates an action without actually calling the tool for it (only
    # nudged when autopilot is on - with it off, pausing after a step is
    # intended), or it returns a genuinely empty response with no text and
    # no tool call (always nudged, regardless of autopilot - a blank
    # response is never a valid answer to anything).
    full_response = ""
    error_occurred = False
    max_nudges = 2

    try:
        current_input = user_message
        current_history = list(chat_history)
        stalled = False
        for attempt in range(max_nudges + 1):
            attempt_text = ""
            tool_called = False
            async for kind, payload in _run_agent_turn(current_input, current_history):
                if kind == "content":
                    full_response += payload
                    attempt_text += payload
                    yield payload
                else:
                    attempt_text, tool_called = payload

            if tool_called:
                if not attempt_text.strip():
                    # Tool(s) ran (real work happened - files written,
                    # commands run, etc.) but the agent produced no closing
                    # summary text. Don't re-invoke - retrying here risks
                    # duplicate side effects (re-writing the same file,
                    # re-running a git command). Just tell the user
                    # something happened instead of showing nothing.
                    logger.info("Tool call succeeded but produced no summary text - adding a fallback note")
                    note = "\n\n*(That action completed, though I didn't generate a closing summary.)*"
                    full_response += note
                    yield note
                break
            is_empty = not attempt_text.strip()
            is_narration_stall = bool(NARRATION_STALL_PATTERN.search(attempt_text))
            if not is_empty and not (autopilot_on and is_narration_stall):
                break
            if attempt == max_nudges:
                stalled = True
                break

            # Stalled: either a blank response, or it described an action
            # without actually calling the tool for it. Nudge it to actually
            # respond/act, in the same turn.
            logger.info(
                "Detected %s - nudging agent to actually respond/act",
                "an empty response" if is_empty else "narration without a tool call",
            )
            current_history = current_history + [
                ("human", current_input),
                ("assistant", attempt_text if attempt_text.strip() else "(no response)"),
            ]
            current_input = (
                "You gave an empty response - answer the request directly, or call "
                "the necessary tool now."
                if is_empty
                else "You just said you would do that, but you did not actually call the "
                "necessary tool. Call it now, immediately - do not explain again."
            )

        if stalled:
            note = "\n\n*(I wasn't able to give a real response to that after a couple of attempts - say \"continue\" and I'll try again.)*"
            full_response += note
            yield note
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
