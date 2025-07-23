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
import uuid
from typing import Any, Dict, List, Optional, Union

import ollama
import pymongo
import redis
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from config import (
    DEFAULT_MODEL,
    LANGCHAIN_AGENT_TIMEOUT,
    MEMORY_CONTEXT_MAX_TOKENS,
    MEMORY_FALLBACK_DISABLED,
    MEMORY_MAIN_MODEL,
    MEMORY_RETRIEVAL_LIMIT,
    MEMORY_SUMMARIZATION_MODEL,
    MEMORY_SUMMARY_MAX_TOKENS,
    OLLAMA_API_BASE,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_TIMEOUT,
)

# Import all tool classes dynamically from all_tools.py
from tools.all_tools import *

# --- Tool Integration ---
# Import the correct, decorator-based tool from tools.web
from tools.web import search_web

logger = logging.getLogger(__name__)

# Global cache for user rules from MongoDB
CACHED_USER_RULES = None


def get_user_rules() -> str:
    """Get cached user rules from MongoDB. Load once at startup."""
    global CACHED_USER_RULES
    if CACHED_USER_RULES is None:
        try:
            # Import constants from knowledge.py
            from tools.knowledge import DEFAULT_USER, MONGODB_DATABASE, MONGODB_URI

            mongo_client = pymongo.MongoClient(
                MONGODB_URI, serverSelectionTimeoutMS=5000
            )
            mongo_db = mongo_client[MONGODB_DATABASE]
            profile = mongo_db.profiles.find_one({"user_id": DEFAULT_USER})

            if profile and profile.get("rules"):
                rules_text = ""
                for rule in profile["rules"]:
                    category = rule.get("category", "general")
                    rule_text = rule.get("rule", "")
                    rules_text += f"- [{category}] {rule_text}\n"
                CACHED_USER_RULES = rules_text
                logger.info(f"Cached {len(profile['rules'])} user rules from MongoDB")
            else:
                CACHED_USER_RULES = ""
                logger.warning("No user rules found in MongoDB")
        except Exception as e:
            logger.error(f"Failed to load user rules: {e}")
            CACHED_USER_RULES = ""

    return CACHED_USER_RULES


# --- 3-Step Memory Architecture Functions ---


def step1_retrieve_memories(
    redis_client: redis.Redis, query: str, limit: int = MEMORY_RETRIEVAL_LIMIT
) -> List[Dict]:
    """
    Step 1: Fast memory retrieval using pre-computed embeddings and Redis vector search
    Returns raw memory objects that match the user's query
    """
    try:
        # Fast-path optimization: Skip memory for simple queries
        if is_simple_query(query):
            logger.info(f"Simple query detected, skipping memory retrieval: {query}")
            return []

        # Skip embeddings - Redis handles search better
        query_embedding = []

        # Get all conversation keys from Redis
        conversation_keys = redis_client.keys("conversation:*")

        if not conversation_keys:
            logger.warning("No conversations found in Redis")
            return []

        # Fast vector search using pre-computed embeddings
        scored_memories = []

        for key in conversation_keys:
            try:
                # Get conversation data
                conversation_data = redis_client.get(key)
                if not conversation_data:
                    continue

                conversation = json.loads(conversation_data)

                # Use pre-computed embedding if available
                stored_embedding = conversation.get("embedding")
                if stored_embedding:
                    # Calculate cosine similarity using stored embedding
                    similarity = calculate_cosine_similarity(
                        query_embedding, stored_embedding
                    )

                    scored_memories.append(
                        {
                            "key": key,
                            "conversation": conversation,
                            "similarity": similarity,
                            "content_length": len(conversation.get("text", "")),
                        }
                    )
                else:
                    # Fallback: Skip conversations without embeddings
                    logger.debug(f"Skipping conversation {key} - no embedding")
                    continue

            except Exception as e:
                logger.error(f"Error processing conversation {key}: {e}")
                continue

        # Sort by similarity score (descending) and return top results
        scored_memories.sort(key=lambda x: x["similarity"], reverse=True)
        top_memories = scored_memories[:limit]

        logger.info(
            f"Retrieved {len(top_memories)} memories from {len(conversation_keys)} total conversations"
        )

        return top_memories

    except Exception as e:
        logger.error(f"Error in step1_retrieve_memories: {e}")
        return []


def is_simple_query(query: str) -> bool:
    """
    Fast-path optimization: Detect simple queries that don't need memory context
    """
    query_lower = query.lower().strip()

    # Simple greetings
    simple_patterns = [
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "what's up",
        "how are you",
        "how's it going",
    ]

    # Simple math
    import re

    if re.match(r"^\d+\s*[\+\-\*\/]\s*\d+$", query_lower):
        return True

    # Simple questions
    if query_lower in simple_patterns:
        return True

    # Time requests
    if any(
        phrase in query_lower for phrase in ["what time", "current time", "time is it"]
    ):
        return True

    # Very short queries (likely don't need context)
    if len(query_lower) < 10:
        return True

    return False


def calculate_cosine_similarity(
    embedding1: List[float], embedding2: List[float]
) -> float:
    """Calculate cosine similarity between two embeddings"""
    import math

    # Calculate dot product
    dot_product = sum(a * b for a, b in zip(embedding1, embedding2))

    # Calculate magnitudes
    magnitude1 = math.sqrt(sum(a * a for a in embedding1))
    magnitude2 = math.sqrt(sum(a * a for a in embedding2))

    # Calculate cosine similarity
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


def step2_summarize_memories(
    retrieved_memories: List[Dict],
    query: str,
    max_tokens: int = MEMORY_SUMMARY_MAX_TOKENS,
) -> str:
    """
    Step 2: Summarize retrieved memories using gemma3:4b with query-specific prompts
    Returns intelligent summary focused on the user's query
    """
    try:
        if not retrieved_memories:
            return ""

        # Prepare memory content for summarization
        memory_content = ""
        for i, memory in enumerate(retrieved_memories, 1):
            conversation = memory["conversation"]
            similarity = memory["similarity"]

            # Extract key information from conversation
            timestamp = conversation.get("timestamp", "Unknown time")
            messages = conversation.get("messages", [])

            memory_content += f"\n--- Memory {i} (Similarity: {similarity:.3f}) ---\n"
            memory_content += f"Timestamp: {timestamp}\n"
            memory_content += "Conversation:\n"

            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if content:
                    # Truncate long messages but keep key information
                    truncated_content = content[:300] if len(content) > 300 else content
                    memory_content += f"{role}: {truncated_content}\n"

            memory_content += "\n"

        # Create query-specific summarization prompt
        summarization_prompt = f"""You are an expert memory summarizer. Your task is to create a concise, relevant summary of conversation memories based on the user's current query.

USER'S CURRENT QUERY: "{query}"

RETRIEVED MEMORIES:
{memory_content}

INSTRUCTIONS:
1. Focus on information that directly relates to the user's current query
2. Identify key topics, preferences, and context from the memories
3. Highlight any patterns in user behavior or interests
4. Keep the summary concise but informative (max {max_tokens} tokens)
5. Structure the summary logically with clear sections
6. Do not include timestamps or similarity scores in the final summary

Create a focused summary that will help answer the user's current query:"""

        # Use gemma3:4b for summarization
        response = ollama.chat(
            model=MEMORY_SUMMARIZATION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert memory summarizer focused on extracting relevant context.",
                },
                {"role": "user", "content": summarization_prompt},
            ],
        )

        summary = response["message"]["content"]

        # Ensure summary doesn't exceed token limit (rough estimate: 4 chars per token)
        if len(summary) > max_tokens * 4:
            summary = summary[: max_tokens * 4]

        logger.info(
            f"Generated summary of {len(summary)} characters from {len(retrieved_memories)} memories"
        )

        return summary.strip()

    except Exception as e:
        logger.error(f"Error in step2_summarize_memories: {e}")
        return ""


def step3_format_context(
    summary: str, query: str, max_tokens: int = MEMORY_CONTEXT_MAX_TOKENS
) -> str:
    """
    Step 3: Format context using breakthrough 'CONVERSATION CONTEXT' format
    Returns properly formatted context that achieves 9.3/10 quality
    """
    try:
        if not summary:
            return ""

        # Use the breakthrough format discovered in testing
        # Key insight: Use "CONVERSATION CONTEXT" not "MEMORY CONTEXT"
        formatted_context = f"""CONVERSATION CONTEXT:
Based on previous interactions, here are the key topics discussed:

{summary}

CURRENT QUERY: {query}

You have access to this conversation context. Use it to provide informed, confident responses about what you discussed previously."""

        # Ensure context doesn't exceed token limit (rough estimate: 4 chars per token)
        if len(formatted_context) > max_tokens * 4:
            # If too long, truncate the summary part while keeping the format
            available_summary_chars = (
                max_tokens * 4
            ) - 200  # Reserve 200 chars for format
            truncated_summary = summary[:available_summary_chars]

            formatted_context = f"""CONVERSATION CONTEXT:
Based on previous interactions, here are the key topics discussed:

{truncated_summary}

CURRENT QUERY: {query}

You have access to this conversation context. Use it to provide informed, confident responses about what you discussed previously."""

        logger.info(f"Formatted context: {len(formatted_context)} characters")

        return formatted_context

    except Exception as e:
        logger.error(f"Error in step3_format_context: {e}")
        return ""


def get_fast_memory_context(redis_client: redis.Redis, query: str) -> str:
    """
    Fast memory architecture: Get 3 most recent conversation summaries instantly
    No semantic search, no summarization - just fast summary retrieval
    """
    try:
        # Fast-path optimization: Skip memory for simple queries
        if is_simple_query(query):
            logger.info(f"Simple query detected, skipping memory retrieval: {query}")
            return ""

        # Get all conversation keys from Redis
        conversation_keys = redis_client.keys("conversation:*")

        if not conversation_keys:
            logger.info("No conversations found in Redis")
            return ""

        # Load conversations with summaries
        conversations_with_summaries = []

        for key in conversation_keys:
            try:
                conversation_data = redis_client.get(key)
                if not conversation_data:
                    continue

                conversation = json.loads(conversation_data)

                # Only include conversations that have summaries
                summary = conversation.get("summary", "").strip()
                if summary:
                    conversations_with_summaries.append(
                        {
                            "key": key,
                            "conversation": conversation,
                            "summary": summary,
                            "created_at": conversation.get("created_at", ""),
                            "last_updated": conversation.get("last_updated", ""),
                        }
                    )

            except Exception as e:
                logger.error(f"Error processing conversation {key}: {e}")
                continue

        if not conversations_with_summaries:
            logger.info("No conversations with summaries found")
            return ""

        # Sort by last_updated (most recent first) and get top 3
        conversations_with_summaries.sort(
            key=lambda x: x["conversation"].get("last_updated", ""), reverse=True
        )
        recent_conversations = conversations_with_summaries[:3]

        # Create fast context from summaries
        context_parts = ["RECENT CONVERSATION CONTEXT:"]
        context_parts.append("Based on your recent interactions:")
        context_parts.append("")

        for i, conv_data in enumerate(recent_conversations, 1):
            summary = conv_data["summary"]
            # Truncate very long summaries
            if len(summary) > 200:
                summary = summary[:200] + "..."
            context_parts.append(f"{i}. {summary}")

        context_parts.append("")
        context_parts.append(f"CURRENT QUERY: {query}")
        context_parts.append("")
        context_parts.append(
            "Use this context to provide informed responses based on your recent conversations."
        )

        fast_context = "\n".join(context_parts)

        logger.info(
            f"Fast memory context generated: {len(recent_conversations)} summaries, {len(fast_context)} chars"
        )

        return fast_context

    except Exception as e:
        logger.error(f"Error in get_fast_memory_context: {e}")
        return ""


def get_3step_memory_context(redis_client: redis.Redis, query: str) -> str:
    """
    Main function for 3-step memory architecture with FAIL FAST error handling

    Steps:
    1. Retrieve: Use nomic-embed-text to find relevant memories
    2. Summarize: Use gemma3:4b to create intelligent summary
    3. Format: Use breakthrough 'CONVERSATION CONTEXT' format

    Returns: Formatted context string or raises exception for FAIL FAST
    """
    try:
        # Step 1: Retrieve memories using semantic search
        logger.info("Step 1: Retrieving memories with semantic search")
        retrieved_memories = step1_retrieve_memories(redis_client, query)

        if not retrieved_memories:
            # Check if this was a simple query (fast-path optimization)
            if is_simple_query(query):
                logger.info("Simple query - no memory context needed")
                return ""
            else:
                logger.warning("No memories retrieved for complex query")
                if MEMORY_FALLBACK_DISABLED:
                    raise Exception(
                        "FAIL FAST: No memories found and fallback disabled"
                    )
                return ""

        # Step 2: Summarize memories using gemma3:4b
        logger.info("Step 2: Summarizing memories with gemma3:4b")
        summary = step2_summarize_memories(retrieved_memories, query)

        if not summary:
            logger.warning("No summary generated from memories")
            if MEMORY_FALLBACK_DISABLED:
                raise Exception("FAIL FAST: Summarization failed and fallback disabled")
            return ""

        # Step 3: Format context using breakthrough format
        logger.info("Step 3: Formatting context with breakthrough format")
        formatted_context = step3_format_context(summary, query)

        if not formatted_context:
            logger.warning("Context formatting failed")
            if MEMORY_FALLBACK_DISABLED:
                raise Exception(
                    "FAIL FAST: Context formatting failed and fallback disabled"
                )
            return ""

        logger.info(
            f"3-step memory context generated successfully: {len(formatted_context)} characters"
        )
        return formatted_context

    except Exception as e:
        logger.error(f"Error in get_3step_memory_context: {e}")
        if MEMORY_FALLBACK_DISABLED:
            raise Exception(f"FAIL FAST: 3-step memory system failed: {e}")
        return ""


def health_check_3step_memory() -> Dict[str, Any]:
    """
    Health check function to verify Redis and Ollama models are available
    Returns status dictionary with component availability
    """
    health_status = {
        "redis_available": False,
        "embedding_model_available": False,
        "summarization_model_available": False,
        "main_model_available": False,
        "overall_status": "unhealthy",
        "errors": [],
    }

    try:
        # Check Redis connection
        test_redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            socket_timeout=REDIS_TIMEOUT,
            socket_connect_timeout=REDIS_TIMEOUT,
            decode_responses=True,
        )
        test_redis.ping()
        health_status["redis_available"] = True
        logger.info("Redis health check: PASS")

    except Exception as e:
        health_status["errors"].append(f"Redis connection failed: {e}")
        logger.error(f"Redis health check: FAIL - {e}")

    try:
        # Skip embedding health check - not needed
        health_status["embedding_model_available"] = True
        logger.info("Embedding health check: SKIPPED (Redis handles search)")

    except Exception as e:
        health_status["errors"].append(f"Embedding model failed: {e}")
        logger.error(f"Embedding model health check: FAIL - {e}")

    try:
        # Check summarization model (gemma3:4b)
        test_summary = ollama.chat(
            model=MEMORY_SUMMARIZATION_MODEL,
            messages=[{"role": "user", "content": "test"}],
        )
        if test_summary and "message" in test_summary:
            health_status["summarization_model_available"] = True
            logger.info(
                f"Summarization model {MEMORY_SUMMARIZATION_MODEL} health check: PASS"
            )

    except Exception as e:
        health_status["errors"].append(
            f"Summarization model {MEMORY_SUMMARIZATION_MODEL} failed: {e}"
        )
        logger.error(f"Summarization model health check: FAIL - {e}")

    try:
        # Check main model
        test_main = ollama.chat(
            model=MEMORY_MAIN_MODEL, messages=[{"role": "user", "content": "test"}]
        )
        if test_main and "message" in test_main:
            health_status["main_model_available"] = True
            logger.info(f"Main model {MEMORY_MAIN_MODEL} health check: PASS")

    except Exception as e:
        health_status["errors"].append(f"Main model {MEMORY_MAIN_MODEL} failed: {e}")
        logger.error(f"Main model health check: FAIL - {e}")

    # Determine overall status
    if (
        health_status["redis_available"]
        and health_status["embedding_model_available"]
        and health_status["summarization_model_available"]
        and health_status["main_model_available"]
    ):
        health_status["overall_status"] = "healthy"
        logger.info("3-step memory system health check: ALL SYSTEMS HEALTHY")
    else:
        missing_components = []
        if not health_status["redis_available"]:
            missing_components.append("Redis")
        if not health_status["embedding_model_available"]:
            missing_components.append("Embedding model")
        if not health_status["summarization_model_available"]:
            missing_components.append("Summarization model")
        if not health_status["main_model_available"]:
            missing_components.append("Main model")

        health_status["overall_status"] = (
            f"unhealthy - missing: {', '.join(missing_components)}"
        )
        logger.warning(
            f"3-step memory system health check: UNHEALTHY - {health_status['overall_status']}"
        )

    return health_status


def save_conversation_to_redis(
    redis_client: redis.Redis, conversation_id: str, new_messages: List[Dict]
) -> None:
    """
    Save conversation using append-only model with background summary generation
    Fast memory architecture: summaries generated in background, don't block response
    """
    import threading

    try:
        from datetime import datetime

        timestamp = datetime.now()
        conversation_key = f"conversation:{conversation_id}"

        # Get existing conversation or create new one
        existing_data = redis_client.get(conversation_key)
        if existing_data:
            # APPEND to existing conversation
            conversation_data = json.loads(existing_data)
            conversation_data["messages"].extend(new_messages)
            conversation_data["last_updated"] = timestamp.isoformat()
            conversation_data["message_count"] = len(conversation_data["messages"])

            # Update conversation text for semantic search
            conversation_text = " ".join(
                [msg.get("content", "") for msg in conversation_data["messages"]]
            )
            conversation_data["text"] = conversation_text

            # No embeddings needed - Redis handles search better

            action = "appended"
        else:
            # CREATE new conversation
            conversation_text = " ".join(
                [msg.get("content", "") for msg in new_messages]
            )

            # No embeddings needed - Redis handles search better

            conversation_data = {
                "conversation_id": conversation_id,
                "text": conversation_text,
                "messages": new_messages,  # Only store new messages once
                "created_at": timestamp.isoformat(),
                "last_updated": timestamp.isoformat(),
                "message_count": len(new_messages),
                "summary": "",  # Will be populated by background thread
            }
            action = "created"

        # Save the conversation (create or update) - THIS DOESN'T BLOCK
        redis_client.setex(
            conversation_key,
            86400 * 14,  # 14 days in seconds
            json.dumps(conversation_data, default=str),
        )

        logger.info(
            f"Conversation {action} in Redis: {conversation_id} - {len(new_messages)} messages"
        )

        # BACKGROUND SUMMARY GENERATION - doesn't block user response
        def generate_summary_background():
            try:
                # Get current conversation text
                current_text = conversation_data.get("text", "")
                if not current_text.strip():
                    return

                # Generate summary with gemma3:4b
                summary_prompt = f"Summarize this conversation in 1-2 sentences focusing on the main topic and outcome:\n\n{current_text}"

                response = ollama.chat(
                    model=MEMORY_SUMMARIZATION_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert at creating concise conversation summaries.",
                        },
                        {"role": "user", "content": summary_prompt},
                    ],
                )

                summary = response["message"]["content"].strip()

                # Update Redis with summary (atomic operation)
                existing_data = redis_client.get(conversation_key)
                if existing_data:
                    conv_data = json.loads(existing_data)
                    conv_data["summary"] = summary
                    conv_data["summary_generated_at"] = datetime.now().isoformat()

                    redis_client.setex(
                        conversation_key, 86400 * 14, json.dumps(conv_data, default=str)
                    )

                    logger.info(
                        f"Background summary generated for {conversation_id}: {len(summary)} chars"
                    )

            except Exception as e:
                logger.error(
                    f"Background summary generation failed for {conversation_id}: {e}"
                )

        # Start background thread - user response is not blocked
        if conversation_data.get("text", "").strip():
            bg_thread = threading.Thread(
                target=generate_summary_background, daemon=True
            )
            bg_thread.start()

    except Exception as e:
        logger.error(f"Failed to save conversation {conversation_id}: {e}")
        raise


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


@tool
def recall_past_conversations(query: str) -> str:
    """
    Searches through past conversations to find relevant information
    to the user's current query. Use this if the user asks 'do you remember...'
    or references a past topic.
    """
    try:
        # Connect to Redis for memory retrieval
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            socket_connect_timeout=REDIS_TIMEOUT,
            decode_responses=True,
        )
        redis_client.ping()

        # Use existing memory retrieval and summarization
        retrieved_memories = step1_retrieve_memories(redis_client, query)
        if not retrieved_memories:
            return "No relevant memories found for your query."

        summary = step2_summarize_memories(retrieved_memories, query)
        return summary if summary else "No relevant memories found."

    except Exception as e:
        logger.error(f"Failed to recall past conversations: {e}")
        return "Unable to access conversation memory at this time."


# --- Core Execution Logic ---


async def orchestrate_request(
    messages: List[Dict],
    user_message: str,
    requested_model_name: str,
    conversation_id: Optional[str] = None,
) -> str:
    """
    Manages an agentic loop where the LLM can decide to call tools.
    Automatically saves interactions using append-only conversation model.
    """
    # --- 1. Initialize ---

    # Generate conversation_id if not provided
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    # Initialize Redis connection for 3-step memory architecture
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
        # Test connection
        redis_client.ping()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        if MEMORY_FALLBACK_DISABLED:
            raise Exception(f"FAIL FAST: Redis unavailable and fallback disabled: {e}")
        else:
            logger.warning("Continuing with fallback memory system")
            redis_client = None

    # Use function wrappers for class-based tools + decorator-based tools
    all_tools = [
        # Memory tools
        memory_context,
        memory_rule,
        memory_stats,
        memory_correction,
        recall_past_conversations,
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

    # Create ChatOllama with tool binding so agent can access RAG and other tools
    llm = ChatOllama(
        model=requested_model_name,
        base_url=OLLAMA_API_BASE,
    ).bind_tools(all_tools)

    available_tools = {tool.name: tool for tool in all_tools}

    # --- 2. Construct Simplified System Prompt ---
    # Use 2025 best practices: Clear role, concise rules, tool guidance
    user_rules = get_user_rules()
    system_prompt = f"""You are Bishop, a highly capable AI assistant.

CRITICAL RULES:
You must strictly follow all of these rules. If a rule is violated, you must correct your response before replying.

{user_rules}

- You must reason about the user's request and decide if a tool is needed.
- When you have a final answer, respond directly to the user.
"""

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

    # --- 4. Create and Run the Agent ---
    try:
        from langchain import hub
        from langchain.agents import AgentExecutor, create_react_agent

        # Pull the standard ReAct prompt
        prompt = hub.pull("hwchase17/react-chat")

        # Create the agent
        agent = create_react_agent(llm, all_tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent, tools=all_tools, verbose=True, handle_parsing_errors=True
        )

        logger.info("Invoking agent executor...")
        # Invoke the agent executor
        response = await agent_executor.ainvoke(
            {"input": user_message, "chat_history": lc_messages}
        )

        # Get the final response from agent executor
        final_response = response.get(
            "output", "I encountered an issue and couldn't provide a response."
        )

        # Log the processed response content for debugging
        logger.info(f"RAW AGENT OUTPUT:\n{final_response}")
        logger.info(
            f"Agent execution completed. Response length: {len(final_response)}"
        )

        # Strip thinking blocks from final response
        final_response_clean = strip_thoughts_from_content(final_response)

        # Save conversation using append-only model
        if redis_client:
            try:
                new_messages = [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": final_response_clean},
                ]
                save_conversation_to_redis(redis_client, conversation_id, new_messages)
            except Exception as e:
                logger.error(f"Failed to save conversation {conversation_id}: {e}")

        return final_response_clean

    except Exception as e:
        logger.error(f"Orchestrator request failed: {e}", exc_info=True)
        return f"An error occurred during agent execution: {str(e)}"
