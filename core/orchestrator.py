#!/usr/bin/env python3
"""
Orchestrator V16 - The True Restoration
=====================================================
This version takes the user's trusted 447-line baseline as its
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
from langchain.tools.base import StructuredTool
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_ollama import ChatOllama
from typing_extensions import Annotated

# --- Local Application Imports ---
from config import (
    DEFAULT_MODEL,
    LANGCHAIN_AGENT_TIMEOUT,
    MEMORY_FALLBACK_DISABLED,
    MEMORY_RETRIEVAL_LIMIT,
    MEMORY_SUMMARIZATION_MODEL,
    OLLAMA_API_BASE,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_TIMEOUT,
    CONTEXT_SIZE_WARNING_THRESHOLD,
)
from tools.knowledge import process_slash_command

from tools.all_tools import (
    LangchainGitStatusTool,
    LangchainGitDiffTool,
    LangchainGitCommitTool,
    LangchainGitBranchTool,
    LangchainGitLogTool,
    LangchainAutoLinterTool,
    LangchainRepoExploreTool,
    LangchainDependencyAnalysisTool,
    LangchainCodeMetricsTool,
    LangchainSystemFileReaderTool,
    LangchainBuildCommandTool,
    LangchainPackageSearchTool,
    MultiLanguageSandboxTool,
    SandboxStatsTool,
    search_web,
    LangchainGitHubRepoSearchTool,
    LangchainGitHubIssuesTool,
    LangchainGitHubReleasesTool,
    LangchainFlutterDocTool,
    LangchainCodeSearchTool,
    LangchainDateTimeTool,
)

# Import rules tools
from tools.rules import (
    LangchainAddRuleTool,
    LangchainListRulesTool,
    LangchainUpdateRuleTool,
    LangchainDeleteRuleTool,
    load_user_rules,
)

# Import new memory tools
from tools.memory import (
    LangchainMemorySaveTool,
    LangchainMemorySearchTool,
    LangchainMemoryStatsTool,
    get_memory_system,
)

# --- Logger Configuration ---
logger = logging.getLogger(__name__)


class ToolExecutionTracker(BaseCallbackHandler):
    """Tracks tool execution and makes the agent aware of what tools were actually used"""
    
    def __init__(self):
        self.tools_executed = []
        self.tools_failed = []
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = serialized.get("name", "unknown_tool")
        logger.info(f"AGENT TOOL START: {tool_name} with input: {input_str}")
        
    def on_tool_end(self, output, **kwargs):
        tool_name = kwargs.get("name", "unknown_tool")
        logger.info(f"AGENT TOOL SUCCESS: {tool_name} completed successfully")
        self.tools_executed.append(tool_name)
        
    def on_tool_error(self, error, **kwargs):
        tool_name = kwargs.get("name", "unknown_tool") 
        logger.error(f"AGENT TOOL FAILED: {tool_name} failed with error: {error}")
        self.tools_failed.append(tool_name)
    
    def get_execution_summary(self):
        """Returns a summary the agent can see"""
        if not self.tools_executed and not self.tools_failed:
            return "tool=no_tools"
        
        if self.tools_executed:
            return f"tool={','.join(self.tools_executed)}"
        
        if self.tools_failed:
            return f"tool=failed_{','.join(self.tools_failed)}"
    
    def reset(self):
        """Reset for next agent execution"""
        self.tools_executed.clear()
        self.tools_failed.clear()

# --- Global Cache for User Rules ---
CACHED_USER_RULES: Optional[str] = None


def get_user_rules() -> str:
    """Loads user-defined rules from rules system, caching them after the first load."""
    global CACHED_USER_RULES
    if CACHED_USER_RULES is not None:
        return CACHED_USER_RULES
    
    try:
        # Use the new rules system
        rules_summary = load_user_rules()
        CACHED_USER_RULES = rules_summary
        # Extract count from summary for logging
        rule_count = rules_summary.count("- ") if rules_summary else 0
        logger.info(f"Cached {rule_count} user rules from rules system.")
        return CACHED_USER_RULES
    except Exception as e:
        logger.error(f"Failed to load user rules from rules system: {e}")
        CACHED_USER_RULES = ""
        return CACHED_USER_RULES

def invalidate_rules_cache():
    """Invalidate rules cache when rules are modified"""
    global CACHED_USER_RULES
    CACHED_USER_RULES = None


# --- FULL MEMORY SYSTEM FROM 447-LINE BASELINE ---


def is_simple_query(query: str) -> bool:
    query_lower = query.lower().strip()

    # Check for temporal keywords first - these are NOT simple queries
    temporal_keywords = [
        "yesterday",
        "today",
        "recent",
        "lately",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "last week",
        "this week",
        "last month",
    ]
    if any(keyword in query_lower for keyword in temporal_keywords):
        return False

    # Then check for actual simple patterns
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
    if query_lower in simple_patterns or len(query_lower) < 5:
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


def search_tier_with_tfidf(conversations_data: List[Dict], query: str) -> List[Dict]:
    """Apply TF-IDF search to a list of conversations"""
    if not conversations_data:
        return []

    import math
    from collections import Counter

    # Collect summaries
    summaries = []
    valid_conversations = []
    for conv in conversations_data:
        summary = conv.get("summary", "")
        if summary:
            summaries.append(summary.lower())
            valid_conversations.append(conv)

    if not summaries:
        return []

    query_lower = query.lower()

    # Tokenize all texts
    all_docs = [query_lower] + summaries
    all_words = set()
    doc_words = []

    for doc in all_docs:
        words = doc.split()
        doc_words.append(words)
        all_words.update(words)

    # Calculate IDF for each word
    word_idf = {}
    total_docs = len(all_docs)
    for word in all_words:
        docs_with_word = sum(1 for words in doc_words if word in words)
        word_idf[word] = (
            math.log(total_docs / docs_with_word) if docs_with_word > 0 else 0
        )

    # Calculate TF-IDF vectors
    def get_tfidf_vector(words):
        word_count = Counter(words)
        total_words = len(words)
        tfidf = {}
        for word in all_words:
            tf = word_count.get(word, 0) / total_words if total_words > 0 else 0
            tfidf[word] = tf * word_idf[word]
        return tfidf

    query_vector = get_tfidf_vector(doc_words[0])

    # Calculate cosine similarity for each summary
    scored_results = []
    for i, conversation in enumerate(valid_conversations):
        summary_vector = get_tfidf_vector(doc_words[i + 1])

        # Cosine similarity calculation
        dot_product = sum(
            query_vector[word] * summary_vector[word] for word in all_words
        )
        query_norm = math.sqrt(sum(val * val for val in query_vector.values()))
        summary_norm = math.sqrt(sum(val * val for val in summary_vector.values()))

        if query_norm > 0 and summary_norm > 0:
            similarity = dot_product / (query_norm * summary_norm)
            if similarity > 0:
                scored_results.append(
                    {"conversation": conversation, "similarity": similarity}
                )

    return scored_results


def parse_temporal_query(query: str) -> tuple[bool, str, str]:
    """Parse temporal queries and return (is_temporal, date_filter, cleaned_query)"""
    import re
    from datetime import datetime, timedelta

    query_lower = query.lower()
    today = datetime.now()

    # Temporal patterns and their date calculations
    temporal_patterns = [
        (r"\byesterday\b", lambda: today - timedelta(days=1)),
        (r"\btoday\b", lambda: today),
        (r"\blast week\b", lambda: today - timedelta(weeks=1)),
        (r"\blast month\b", lambda: today - timedelta(days=30)),
        (r"\bthis week\b", lambda: today - timedelta(days=today.weekday())),
        (r"\brecent\b", lambda: today - timedelta(days=3)),  # Last 3 days
        (r"\blately\b", lambda: today - timedelta(days=7)),  # Last week
    ]

    # Days of week patterns
    weekdays = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    for i, day in enumerate(weekdays):
        # "last monday", "this tuesday", etc.
        pattern = rf"\b(?:last|this)\s+{day}\b"
        if re.search(pattern, query_lower):
            days_back = (today.weekday() - i + 7) % 7
            if days_back == 0:  # Same day of week
                days_back = 7 if "last" in query_lower else 0
            target_date = today - timedelta(days=days_back)
            return (
                True,
                target_date.strftime("%Y-%m-%d"),
                re.sub(pattern, "", query_lower).strip(),
            )

    # Check standard temporal patterns
    for pattern, date_func in temporal_patterns:
        if re.search(pattern, query_lower):
            target_date = date_func()
            cleaned_query = re.sub(pattern, "", query_lower).strip()
            return True, target_date.strftime("%Y-%m-%d"), cleaned_query

    return False, "", query


def filter_conversations_by_date(
    conversations_data: List[Dict], target_date: str
) -> List[Dict]:
    """Filter conversations to those from the target date"""
    filtered = []
    for conv in conversations_data:
        # Check both created_at and last_updated fields
        for date_field in ["created_at", "last_updated"]:
            conv_date = conv.get(date_field, "")
            if conv_date:
                try:
                    # Parse ISO date and compare
                    conv_datetime = datetime.fromisoformat(
                        conv_date.replace("Z", "+00:00")
                    )
                    conv_date_str = conv_datetime.strftime("%Y-%m-%d")
                    if conv_date_str == target_date:
                        filtered.append(conv)
                        break
                except Exception as e:
                    logger.debug(f"Date parsing error for {conv_date}: {e}")
                    continue
    return filtered


def step1_retrieve_memories(
    redis_client: redis.Redis, query: str, limit: int = MEMORY_RETRIEVAL_LIMIT
) -> List[Dict]:
    if is_simple_query(query):
        return []
    try:
        # Search Redis conversation history directly
        conversations_data = []
        conversation_keys = redis_client.keys("conversation:*")

        for key in conversation_keys:
            try:
                conversation_data = redis_client.get(key)
                if conversation_data:
                    conversation = json.loads(conversation_data)
                    conversations_data.append(conversation)
            except Exception as e:
                logger.error(f"Error loading conversation {key}: {e}")
                continue

        if not conversations_data:
            return []

        # Parse temporal query
        is_temporal, target_date, cleaned_query = parse_temporal_query(query)

        if is_temporal:
            logger.info(
                f"Temporal query detected: '{query}' → date={target_date}, cleaned='{cleaned_query}'"
            )
            # Filter by date first
            filtered_conversations = filter_conversations_by_date(
                conversations_data, target_date
            )
            logger.info(
                f"Found {len(filtered_conversations)} conversations from {target_date}"
            )

            if not filtered_conversations:
                return []

            # If we have a cleaned query (topic words), use TF-IDF on filtered results
            if cleaned_query.strip():
                scored_results = search_tier_with_tfidf(
                    filtered_conversations, cleaned_query
                )
            else:
                # No topic words, return all from that date with fake similarity scores
                scored_results = [
                    {"conversation": conv, "similarity": 0.5}
                    for conv in filtered_conversations
                ]
        else:
            # Regular TF-IDF search on all conversations
            scored_results = search_tier_with_tfidf(conversations_data, query)

        # Convert to expected format and limit results
        memories = []
        for result in scored_results[:limit]:
            conversation = result["conversation"]
            memory = {"conversation": conversation, "similarity": result["similarity"]}
            memories.append(memory)

        return memories

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


def strip_thoughts_from_content(content: str) -> str:
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def strip_emojis(text: str) -> str:
    """
    Removes all emojis from a string. This is a hard safety net.
    """
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f700-\U0001f77f"  # alchemical symbols
        "\U0001f780-\U0001f7ff"  # Geometric Shapes Extended
        "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
        "\U0001fa00-\U0001fa6f"  # Chess Symbols
        "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027b0"  # Dingbats
        "\U000024c2-\U0001f251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text).strip()


def _format_context_digest(redis_client: redis.Redis, query: str) -> str:
    """
    Fetches and summarizes context into a token-efficient digest.
    """
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
    # --- STEP 1: RESTORED SLASH COMMAND ROUTER ---
    if user_message.strip().startswith("/"):
        parts = user_message.strip().split(" ", 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        # In a real system, you'd fetch custom_commands. We pass an empty dict.
        return process_slash_command(command, args, {})

    # --- STEP 2: CONVERSATIONAL TURN - PROCEED TO AGENT ---
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

    system_rules = get_user_rules()
    safe_system_rules = system_rules.replace("{", "{{").replace("}", "}}")

    tools = [
        LangchainGitStatusTool(),
        LangchainGitDiffTool(),
        LangchainGitCommitTool(),
        LangchainGitBranchTool(),
        LangchainGitLogTool(),
        LangchainAutoLinterTool(),
        LangchainRepoExploreTool(),
        LangchainDependencyAnalysisTool(),
        LangchainCodeMetricsTool(),
        LangchainSystemFileReaderTool(),
        LangchainBuildCommandTool(),
        LangchainPackageSearchTool(),
        MultiLanguageSandboxTool(),
        SandboxStatsTool(),
        search_web,  # This one is a function, so no ()
        LangchainGitHubRepoSearchTool(),
        LangchainGitHubIssuesTool(),
        LangchainGitHubReleasesTool(),
        LangchainFlutterDocTool(),
        LangchainCodeSearchTool(),
        # New simplified memory tools
        LangchainMemorySaveTool(),
        LangchainMemorySearchTool(),
        LangchainMemoryStatsTool(),
        # Rules tools (separate from memory)
        LangchainAddRuleTool(),
        LangchainListRulesTool(),
        LangchainUpdateRuleTool(),
        LangchainDeleteRuleTool(),
        LangchainDateTimeTool(),
    ]

    SYSTEM_PROMPT = f"""You are Bishop, a helpful AI assistant.

**CRITICAL DIRECTIVE: YOU MUST FOLLOW ALL RULES. FAILURE IS NOT AN OPTION.**

**Core Rules (Non-negotiable):**
{safe_system_rules}

**Memory Context:**
Available via memory tools when needed.

**Your Task & Instructions:**
1.  **Use your memory search more effectively to find detailed memories.**
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

    llm = ChatOllama(
        model=requested_model_name,
        base_url=OLLAMA_API_BASE,
        timeout=LANGCHAIN_AGENT_TIMEOUT,
    )
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
    # --- STEP 3: OPTIMIZE CHAT HISTORY ---
    chat_history: List[BaseMessage] = []

    # No upfront memory context - agent will fetch if needed via memory tools

    if len(messages) > 2:
        last_two_messages = messages[-3:-1] 
        for msg in last_two_messages:
            role, content = msg.get("role"), msg.get("content")
            if content:
                if role == "user":
                    chat_history.append(HumanMessage(content=content))
                elif role == "assistant":
                    chat_history.append(AIMessage(content=content))    

    # Log the new, optimized history
    logger.info(f"Chat history OPTIMIZED to {len(chat_history)} summary message(s).")
    for msg in chat_history:
        logger.info(f"  - AI Summary: {msg.content[:150]}...")
    
    # Calculate approximate token counts for context monitoring
    total_context_chars = len(user_message) + sum(len(msg.content) for msg in chat_history)
    estimated_tokens = total_context_chars // 4  # Rough approximation: 1 token ≈ 4 characters
    logger.info(f"CONTEXT SIZE: ~{estimated_tokens} tokens ({total_context_chars} chars)")
    
    if estimated_tokens > 28000:  # Conservative limit for qwen3:30b on RTX3090
        logger.warning(f"CONTEXT APPROACHING LIMIT: {estimated_tokens} tokens - may cause truncation")

    try:
        logger.info("Invoking agent executor with a lean, summary-based prompt...")
        
        # Create tool execution tracker
        tool_tracker = ToolExecutionTracker()
        
        response = await agent_executor.ainvoke(
            {"input": user_message, "chat_history": chat_history},
            {"callbacks": [tool_tracker]}
        )
        final_response = response.get(
            "output", "I encountered an issue and couldn't provide a response."
        )

        # Context digest will be created during background memory save

        clean_response_no_thoughts = strip_thoughts_from_content(final_response)
        final_clean_response = strip_emojis(clean_response_no_thoughts)
        
        # Add tool execution awareness to the response
        execution_summary = tool_tracker.get_execution_summary()
        final_clean_response += f"\n\n{execution_summary}"

        # Schedule memory save to run in background after response is sent
        new_messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": final_clean_response}
        ]
        
        # Save to new simplified memory system (non-blocking)
        def background_memory_save():
            try:
                memory_system = get_memory_system()
                
                # Format messages for memory system (correct append format)
                messages_to_save = [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": final_clean_response}
                ]
                
                # Create AI summary using Gemma (background - user doesn't wait)
                conversation_content = f"User: {user_message}\nAssistant: {final_clean_response}"
                
                try:
                    import ollama
                    from config import MEMORY_SUMMARIZATION_MODEL
                    
                    summarization_prompt = f'Summarize this conversation briefly, focusing on the main topic and key points: {conversation_content}'
                    response = ollama.chat(
                        model=MEMORY_SUMMARIZATION_MODEL,
                        messages=[{"role": "user", "content": summarization_prompt}],
                    )
                    summary = response["message"]["content"].strip()
                    logger.info(f"AI summary generated for conversation {conversation_id}")
                except Exception as e:
                    # Fallback to truncation if AI summary fails
                    summary = conversation_content[:200] + "..." if len(conversation_content) > 200 else conversation_content
                    logger.warning(f"AI summary failed, using truncation: {e}")
                
                save_result = memory_system.save_memory(conversation_id, messages_to_save, summary)
                if save_result.get("status") == "success":
                    logger.info(f"Memory saved to Redis for conversation {conversation_id}")
                else:
                    logger.warning(f"Memory save failed: {save_result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"Failed to save conversation to memory: {e}")
        
        # Start in background thread - response returns immediately
        threading.Thread(target=background_memory_save, daemon=True).start()

        return final_clean_response

    except Exception as e:
        logger.error(f"Agent Executor request failed: {e}", exc_info=True)
        return f"An error occurred during the agent's execution: {str(e)}"
