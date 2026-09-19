#!/usr/bin/env python3
"""
Base tool class for all MCP tools
Eliminates code duplication as identified in claude_code_errors.md
"""

import asyncio
import functools
import logging
from typing import Any

from langchain_core.tools import BaseTool as LangchainBaseTool
from pydantic import ValidationError

logger = logging.getLogger(__name__)


def _report_validation_error(e: ValidationError) -> str:
    """
    Turn a malformed tool call into a recoverable observation the agent can
    see and correct, instead of letting it crash the whole turn. Without
    this, an unreliable model occasionally producing a malformed tool call
    (e.g. missing a required argument) kills the entire multi-step task
    rather than just that one call.
    """
    logger.warning(f"Tool call failed validation, returning error to agent for retry: {e}")
    return (
        f"Error: this tool call had invalid arguments and was not executed: {e}. "
        f"Check the required arguments and call the tool again correctly."
    )


class AsyncTool(LangchainBaseTool):
    """
    A base tool with a default async implementation.
    Eliminates the duplicate _arun method across all tool classes.
    """

    handle_validation_error: Any = _report_validation_error

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Run the tool asynchronously in a thread pool."""
        loop = asyncio.get_running_loop()
        # This new line correctly handles both positional and keyword arguments.
        return await loop.run_in_executor(
            None, functools.partial(self._run, *args, **kwargs)
        )
