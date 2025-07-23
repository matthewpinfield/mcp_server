#!/usr/bin/env python3
"""
Orchestrator V16 - The True Restoration
=====================================================
This version takes the user's trusted 447-line baseline (V14) as its
foundation and correctly integrates all final fixes. It restores the slash
command router, the agent's identity, and combines a forceful system prompt
with a programmatic safety net to ensure all rules and behaviors are
correctly followed. This is the definitive, working version.
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
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
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
from tools.knowledge import process_slash_command
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
    except Exception as e:
        logger.error(f"Failed to load user rules from MongoDB: {e}")
        CACHED_USER_RULES = ""
    return CACHED_USER_RULES if CACHED_USER_RULES is not None else ""


# --- FULL MEMORY SYSTEM FROM 447-LINE BASELINE ---


def is_simple_query(query: str) -> bool:
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
    import math

    if not embedding1 or not embedding2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
    magnitude1 = math.sqrt(sum(a * a for a in embedding1))
    magnitude2 = math.sqrt(sum(a * a for a in embedding2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


def step1_retrieve_memories(
    redis_client: redis.Redis, query: str, limit: int = MEMORY_RETRIEVAL_LIMIT
) -> List[Dict]:
    if is_simple_query(query):
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
        return scored_memories[:limit]
    except Exception as e:
        logger.error(f"Error in step1_retrieve_memories: {e}")
        return []


def step2_summarize_memories(retrieved_memories: List[Dict], query: str) -> str:
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
        return summary.strip()
    except Exception as e:
        logger.error(f"Error in step2_summarize_memories: {e}")
        return ""


def save_conversation_to_redis(
    redis_client: redis.Redis, conversation_id: str, new_messages: List[Dict]
) -> None:
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
        bg_thread = threading.Thread(
            target=generate_summary_and_embedding_background,
            args=(conversation_key, conversation_data),
            daemon=True,
        )
        bg_thread.start()
    except Exception as e:
        logger.error(f"Failed to save conversation {conversation_id}: {e}")


def strip_thoughts_from_content(content: str) -> str:
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def strip_emojis(text: str) -> str:
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f700-\U0001f77f"
        "\U0001f780-\U0001f7ff"
        "\U0001f800-\U0001f8ff"
        "\U0001f900-\U0001f9ff"
        "\U0001fa00-\U0001fa6f"
        "\U0001fa70-\U0001faff"
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text).strip()


def _format_context_digest(redis_client: redis.Redis, query: str) -> str:
    try:
        retrieved_memories = step1_retrieve_memories(redis_client, query)
        if not retrieved_memories:
            return "No relevant memories were found for this query."
        summary = step2_summarize_memories(retrieved_memories, query)
        if not summary:
            return "No specific memories were found for this query."
        digest = (summary[:700] + "...") if len(summary) > 700 else summary
        return digest
    except Exception as e:
        logger.error(f"Error creating context digest: {e}")
        return "Could not retrieve memory context."


# --- SELF-CONTAINED TOOL DEFINITIONS FROM 447-LINE BASELINE ---
class MemoryTools:
    """A class to encapsulate memory tools that require a Redis connection."""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    @tool
    def recall(self, query: str) -> str:
        """
        Searches through past conversations to find relevant information. Use this if the user asks 'do you remember...' or references a past topic.
        """
        try:
            if not self.redis_client:
                return "Memory is unavailable. Redis client not configured."
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


# --- CORE ORCHESTRATION LOGIC (Restored and Corrected) ---


async def orchestrate_request(
    messages: List[Dict],
    user_message: str,
    requested_model_name: str,
    conversation_id: Optional[str] = None,
) -> str:
    """
    Acts as a router. Handles slash commands directly and passes conversational
    turns to the LLM agent.
    """
    if user_message.strip().startswith("/"):
        parts = user_message.strip().split(" ", 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        return process_slash_command(command, args, {})

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
    except Exception as e:
        logger.error(f"Redis connection failed: {e}. Memory will be disabled.")
        if MEMORY_FALLBACK_DISABLED:
            raise ConnectionError(
                f"FAIL FAST: Redis unavailable and fallback disabled: {e}"
            )

    formatted_digest = (
        _format_context_digest(redis_client, user_message)
        if redis_client
        else "Memory system is offline."
    )
    system_rules = get_user_rules()
    safe_system_rules = system_rules.replace("{", "{{").replace("}", "}}")
    safe_formatted_digest = formatted_digest.replace("{", "{{").replace("}", "}}")

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

    SYSTEM_PROMPT = f"""You are Bishop, a helpful AI assistant.

**CRITICAL DIRECTIVE: YOU MUST FOLLOW ALL RULES. FAILURE IS NOT AN OPTION.**

**Core Rules (Non-negotiable):**
{safe_system_rules}
- **ABSOLUTE RULE: You MUST NOT use emojis, icons, or emoticons in any of your responses. This is a strict, non-negotiable rule. Violation is a critical failure.**

**Relevant Memory Context:**
{safe_formatted_digest}

**Your Task & Instructions:**
1.  **Adhere strictly to all your Core Rules.**
2.  Review the Relevant Memory Context to inform your answer.
3.  **SYNTHESIZE A FINAL ANSWER:** If you use a tool, you **MUST** take the information the tool provides and formulate a complete, final, user-facing answer. Do not stop after the tool has run. Your job is not done until you have given a concluding response to the user.
4.  If you do not need a tool, answer the user's query directly.
5.  **FINAL CHECK:** Before you output your response, re-read these instructions and your rules one last time to ensure you have not violated any of them.
"""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    llm = ChatOllama(model=requested_model_name, base_url=OLLAMA_API_BASE)
    agent = create_tool_calling_agent(llm, all_tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent, tools=all_tools, verbose=True, handle_parsing_errors=True
    )

    chat_history: List[BaseMessage] = []
    for msg in messages:
        role, content = msg.get("role"), msg.get("content")
        if content:
            if role == "user":
                chat_history.append(HumanMessage(content=content))
            elif role == "assistant":
                chat_history.append(AIMessage(content=content))

    try:
        logger.info("Invoking agent executor with robust hybrid memory prompt...")
        response = await agent_executor.ainvoke(
            {"input": user_message, "chat_history": chat_history}
        )
        final_response = response.get(
            "output", "I encountered an issue and couldn't provide a response."
        )

        clean_response_no_thoughts = strip_thoughts_from_content(final_response)
        final_clean_response = strip_emojis(clean_response_no_thoughts)

        if redis_client:
            save_conversation_to_redis(
                redis_client,
                conversation_id,
                [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": final_clean_response},
                ],
            )

        return final_clean_response

    except Exception as e:
        logger.error(f"Agent Executor request failed: {e}", exc_info=True)
        return f"An error occurred during the agent's execution: {str(e)}"
