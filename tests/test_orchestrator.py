from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# This assumes your file is in core/orchestrator.py
# Adjust the import path if necessary.
from core.orchestrator import MemoryTools, orchestrate_request

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


@patch("core.orchestrator.AgentExecutor")
@patch("core.orchestrator.redis.Redis")
async def test_orchestrate_request_with_redis_success(
    mock_redis_class, mock_agent_executor_class
):
    """
    Tests the happy path: Redis connects successfully.
    """
    # --- Arrange ---
    mock_redis_instance = mock_redis_class.return_value
    mock_redis_instance.ping.return_value = True

    mock_executor_instance = mock_agent_executor_class.return_value
    mock_executor_instance.ainvoke.return_value = {"output": "Success"}

    # --- Act ---
    await orchestrate_request(
        messages=[], user_message="Hello", requested_model_name="test-model"
    )

    # --- Assert ---
    mock_agent_executor_class.assert_called_once()
    args, kwargs = mock_agent_executor_class.call_args
    passed_tools = kwargs.get("tools", [])
    recall_tool_found = any(tool.name == "recall" for tool in passed_tools)
    assert recall_tool_found
    recall_tool = next(tool for tool in passed_tools if tool.name == "recall")
    assert "disabled" not in recall_tool.description.lower()


# FIX: Add a patch to control the MEMORY_FALLBACK_DISABLED flag
@patch("core.orchestrator.MEMORY_FALLBACK_DISABLED", False)
@patch("core.orchestrator.AgentExecutor")
@patch("core.orchestrator.redis.Redis")
async def test_orchestrate_request_with_redis_failure(
    mock_redis_class, mock_agent_executor_class
):
    """
    Tests the fallback path: Redis connection fails and fallback is ENABLED.
    """
    # --- Arrange ---
    mock_redis_class.side_effect = ConnectionError("Redis connection failed")

    mock_executor_instance = mock_agent_executor_class.return_value
    mock_executor_instance.ainvoke.return_value = {"output": "Success but no memory"}

    # --- Act ---
    await orchestrate_request(
        messages=[], user_message="Hello", requested_model_name="test-model"
    )

    # --- Assert ---
    mock_agent_executor_class.assert_called_once()
    args, kwargs = mock_agent_executor_class.call_args
    passed_tools = kwargs.get("tools", [])
    recall_tool_found = any(tool.name == "recall" for tool in passed_tools)
    assert recall_tool_found
    recall_tool = next(tool for tool in passed_tools if tool.name == "recall")
    assert "disabled" in recall_tool.description.lower()


# FIX: Make the test function async itself
@patch("core.orchestrator.step2_summarize_memories")
@patch("core.orchestrator.step1_retrieve_memories")
async def test_memory_tools_recall_method(mock_step1, mock_step2):
    """
    Tests the MemoryTools.recall method in isolation to verify its internal logic.
    """
    # --- Arrange ---
    mock_redis_client = MagicMock()
    mock_step1.return_value = [{"conversation": "some data"}]
    mock_step2.return_value = "This is a summary."

    memory_tool_instance = MemoryTools(redis_client=mock_redis_client)

    # --- Act ---
    # Since the underlying function is not async, we don't need to await it.
    # The test runner handles the async context.
    result = memory_tool_instance.recall.func(memory_tool_instance, query="test query")

    # --- Assert ---
    mock_step1.assert_called_once_with(mock_redis_client, "test query")
    mock_step2.assert_called_once_with([{"conversation": "some data"}], "test query")
    assert result == "This is a summary."
