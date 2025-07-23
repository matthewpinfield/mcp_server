#!/usr/bin/env python3
"""
Orchestrator V14 - Custom Prompt Template
=====================================================
This version resolves the KeyError by replacing the unreliable Hub prompt
with a manually constructed ChatPromptTemplate. This ensures a perfect
match between the variables provided by the AgentExecutor and the variables
expected by the prompt, creating a robust and transparent agent.
"""

# --- Standard Library Imports ---
import json
import logging
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# --- Third-Party Imports ---
import ollama
import pymongo
import redis
from langchain import hub
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

# FIX: Import classes for custom prompt construction
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

# --- Local Application Imports ---
from config import (
    DEFAULT_MODEL,
    MEMORY_FALLBACK_DISABLED,
    MEMORY_RETRIEVAL_LIMIT,
    MEMORY_SUMMARIZATION_MODEL,
    OLLAMA_API_BASE,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_TIMEOUT,
)
from tools.all_tools import *
from tools.web import search_web

# --- Logger Configuration ---
logger = logging.getLogger(__name__)

# --- Global Cache for User Rules ---
CACHED_USER_RULES: Optional[str] = None


def get_user_rules() -> str:
    """Loads user-defined rules from MongoDB, caching them after the first load."""
    global CACHED_USER_RULES
    if CACHED_USER_RULES is not None:
        return CACHED_USER_RULES
    try:
        from tools.knowledge import DEFAULT_USER, MONGODB_DATABASE, MONGODB_URI

        mongo_client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        mongo_db = mongo_client[MONGODB_DATABASE]
        profile = mongo_db.profiles.find_one({"user_id": DEFAULT_USER})
        if profile and profile.get("rules"):
            rules_list = [
                f"- [{rule.get('category', 'general')}] {rule.get('rule', '')}"
                for rule in profile["rules"]
            ]
            CACHED_USER_RULES = "\n".join(rules_list)
            logger.info(f"Cached {len(profile['rules'])} user rules from MongoDB.")
        else:
            CACHED_USER_RULES = ""
            logger.warning("No user rules found in MongoDB profile.")
    except Exception as e:
        logger.error(f"Failed to load user rules from MongoDB: {e}")
        CACHED_USER_RULES = ""
    return CACHED_USER_RULES


def is_simple_query(query: str) -> bool:
    """Fast-path optimization: Detect simple queries that don't need memory context."""
    query_lower = query.lower().strip()
    simple_patterns = [
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "what's up",
        "how are you",
    ]
    if query_lower in simple_patterns or len(query_lower) < 10:
        return True
    if re.match(r"^\d+\s*[\+\-\*\/]\s*\d+$", query_lower):
        return True
    if any(
        phrase in query_lower for phrase in ["what time", "current time", "time is it"]
    ):
        return True
    return False


def calculate_cosine_similarity(
    embedding1: List[float], embedding2: List[float]
) -> float:
    """Calculate cosine similarity between two embeddings."""
    import math

    dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
    magnitude1 = math.sqrt(sum(a * a for a in embedding1))
    magnitude2 = math.sqrt(sum(a * a for a in embedding2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


def step1_retrieve_memories(
    redis_client: redis.Redis, query: str, limit: int = MEMORY_RETRIEVAL_LIMIT
) -> List[Dict]:
    """Retrieves relevant conversation chunks from Redis using vector similarity."""
    if is_simple_query(query):
        logger.info(f"Simple query detected, skipping memory retrieval: {query}")
        return []
    try:
        query_embedding = ollama.embeddings(model="nomic-embed-text", prompt=query)[
            "embedding"
        ]
        conversation_keys = redis_client.keys("conversation:*")
        if not conversation_keys:
            return []
        scored_memories = []
        for key in conversation_keys:
            conversation_data = redis_client.get(key)
            if not conversation_data:
                continue
            conversation = json.loads(conversation_data)
            stored_embedding = conversation.get("embedding")
            if stored_embedding:
                similarity = calculate_cosine_similarity(
                    query_embedding, stored_embedding
                )
                scored_memories.append(
                    {"conversation": conversation, "similarity": similarity}
                )
        scored_memories.sort(key=lambda x: x["similarity"], reverse=True)
        logger.info(
            f"Retrieved {len(scored_memories)} memories, returning top {limit}."
        )
        return scored_memories[:limit]
    except Exception as e:
        logger.error(f"Error in step1_retrieve_memories: {e}")
        return []


def step2_summarize_memories(retrieved_memories: List[Dict], query: str) -> str:
    """Summarizes retrieved memories using a dedicated LLM."""
    if not retrieved_memories:
        return ""
    try:
        memory_content = ""
        for i, memory in enumerate(retrieved_memories, 1):
            conversation = memory["conversation"]
            messages = conversation.get("messages", [])
            memory_content += f"\n--- Memory {i} ---\n"
            for msg in messages:
                content = msg.get("content", "")
                truncated_content = content[:300] if len(content) > 300 else content
                memory_content += f"{msg.get('role', 'unknown')}: {truncated_content}\n"
        summarization_prompt = f'Summarize the following conversation memories based on the user\'s query: "{query}".\n\n{memory_content}'
        response = ollama.chat(
            model=MEMORY_SUMMARIZATION_MODEL,
            messages=[{"role": "user", "content": summarization_prompt}],
        )
        summary = response["message"]["content"]
        logger.info(f"Generated summary of {len(summary)} chars.")
        return summary.strip()
    except Exception as e:
        logger.error(f"Error in step2_summarize_memories: {e}")
        return ""


def save_conversation_to_redis(
    redis_client: redis.Redis, conversation_id: str, new_messages: List[Dict]
) -> None:
    """Saves conversation turns to Redis and triggers background processing."""

    def generate_summary_and_embedding_background(key, data):
        try:
            full_text = data.get("text", "")
            if not full_text.strip():
                return
            summary_prompt = (
                f"Summarize this conversation in 1-2 sentences: {full_text}"
            )
            summary_response = ollama.chat(
                model=MEMORY_SUMMARIZATION_MODEL,
                messages=[{"role": "user", "content": summary_prompt}],
            )
            summary = summary_response["message"]["content"].strip()
            embedding = ollama.embeddings(model="nomic-embed-text", prompt=full_text)[
                "embedding"
            ]
            data.update(
                {
                    "summary": summary,
                    "embedding": embedding,
                    "summary_generated_at": datetime.now().isoformat(),
                }
            )
            redis_client.setex(key, 86400 * 14, json.dumps(data, default=str))
            logger.info(
                f"Background summary/embedding generated for {conversation_id}."
            )
        except Exception as e:
            logger.error(f"Background processing failed for {conversation_id}: {e}")

    try:
        timestamp = datetime.now()
        conversation_key = f"conversation:{conversation_id}"
        existing_data = redis_client.get(conversation_key)
        if existing_data:
            conversation_data = json.loads(existing_data)
            conversation_data["messages"].extend(new_messages)
            conversation_data["last_updated"] = timestamp.isoformat()
        else:
            conversation_data = {
                "conversation_id": conversation_id,
                "messages": new_messages,
                "created_at": timestamp.isoformat(),
                "last_updated": timestamp.isoformat(),
                "summary": "",
                "embedding": None,
            }
        full_text = " ".join(
            [msg.get("content", "") for msg in conversation_data["messages"]]
        )
        conversation_data["text"] = full_text
        redis_client.setex(
            conversation_key, 86400 * 14, json.dumps(conversation_data, default=str)
        )
        logger.info(f"Conversation saved to Redis: {conversation_id}")
        bg_thread = threading.Thread(
            target=generate_summary_and_embedding_background,
            args=(conversation_key, conversation_data),
            daemon=True,
        )
        bg_thread.start()
    except Exception as e:
        logger.error(f"Failed to save conversation {conversation_id}: {e}")


def strip_thoughts_from_content(content: str) -> str:
    """Strips <think>...</think> blocks from content for the final user-facing response."""
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


# === CONTINUATION OF orchestrator.py ===


class MemoryTools:
    """A class to encapsulate memory tools that require a Redis connection."""

    def __init__(self, redis_client: redis.Redis):
        """
        Initializes the MemoryTools with a Redis client dependency.

        Args:
            redis_client: An active redis.Redis client instance.
        """
        self.redis_client = redis_client

    @tool
    def recall(self, query: str) -> str:
        """
        Searches through past conversations to find relevant information. Use this if the user asks 'do you remember...' or references a past topic.
        """
        try:
            if not self.redis_client:
                return "Memory is unavailable. Redis client not configured."

            logger.info(f"Memory tool activated with query: {query}")
            retrieved_memories = step1_retrieve_memories(self.redis_client, query)
            if not retrieved_memories:
                return "No relevant memories were found for that topic."

            summary = step2_summarize_memories(retrieved_memories, query)
            return (
                summary
                if summary
                else "I found some memories but could not summarize them."
            )
        except Exception as e:
            logger.error(f"Failed to recall past conversations: {e}")
            return "An error occurred while accessing conversation memory."


# --- All Original Tool Wrappers Preserved ---


@tool
def memory_context(query: str) -> str:
    """Retrieve relevant context from memory"""
    return LangchainMemoryContextTool()._run(query)


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


# === CONTINUATION OF orchestrator.py ===


async def orchestrate_request(
    messages: List[Dict],
    user_message: str,
    requested_model_name: str,
    conversation_id: Optional[str] = None,
) -> str:
    """
    Manages an agentic loop using LangChain's modern Tool-Calling AgentExecutor.
    """
    # --- 1. Initialization ---
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())
    redis_client = None
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            socket_timeout=REDIS_TIMEOUT,
            socket_connect_timeout=REDIS_TIMEOUT,
            decode_responses=True,
        )
        redis_client.ping()
        logger.info("Redis connection established successfully.")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}. Memory tool will be disabled.")
        if MEMORY_FALLBACK_DISABLED:
            raise ConnectionError(
                f"FAIL FAST: Redis unavailable and fallback disabled: {e}"
            )

    # --- 2. Assemble All Tools ---
    all_tools = [
        memory_context,
        memory_rule,
        memory_stats,
        memory_correction,
        sandbox_execute,
        sandbox_stats,
        git_status,
        git_diff,
        git_commit,
        git_branch,
        git_log,
        flutter_docs,
        code_search,
        auto_linter,
        repo_explore,
        dependency_analysis,
        code_metrics,
        read_system_file,
        build_command,
        package_search,
        get_datetime,
        github_repo_search,
        github_issues,
        github_releases,
        search_web,
    ]
    if redis_client:
        memory_tool_instance = MemoryTools(redis_client=redis_client)
        all_tools.append(memory_tool_instance.recall)
    else:

        @tool
        def recall(query: str) -> str:
            """Searches through past conversations. Currently disabled as memory is unavailable."""
            return "Conversation memory is currently unavailable."

        all_tools.append(recall)

    # --- 3. Create the Agent and Executor with a Custom Prompt ---
    llm = ChatOllama(model=requested_model_name, base_url=OLLAMA_API_BASE)

    # This custom prompt is the definitive fix for the KeyError.
    # It explicitly defines the variables the AgentExecutor provides.
    # Your custom rules are now part of the core system prompt.
    system_rules = get_user_rules()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"You are a helpful assistant. You must follow these rules:\n{system_rules}",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, all_tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent, tools=all_tools, verbose=True, handle_parsing_errors=True
    )

    # --- 4. Prepare Chat History ---
    chat_history: List[BaseMessage] = []
    for msg in messages:
        role, content = msg.get("role"), msg.get("content")
        if content:
            if role == "user":
                chat_history.append(HumanMessage(content=content))
            elif role == "assistant":
                chat_history.append(AIMessage(content=content))

    # --- 5. Invoke the Agent and Handle the Response ---
    try:
        logger.info("Invoking agent executor with custom prompt...")
        # The invoke call is now simple and correct, as the AgentExecutor
        # will automatically handle the 'agent_scratchpad' variable.
        response = await agent_executor.ainvoke(
            {"input": user_message, "chat_history": chat_history}
        )
        final_response = response.get(
            "output", "I encountered an issue and couldn't provide a response."
        )

        final_response_clean = strip_thoughts_from_content(final_response)

        if redis_client:
            try:
                new_messages_to_save = [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": final_response_clean},
                ]
                save_conversation_to_redis(
                    redis_client, conversation_id, new_messages_to_save
                )
            except Exception as e:
                logger.error(f"Failed to save conversation {conversation_id}: {e}")

        return final_response_clean

    except Exception as e:
        logger.error(f"Agent Executor request failed: {e}", exc_info=True)
        return f"An error occurred during the agent's execution: {str(e)}"
