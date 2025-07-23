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

logger = logging.getLogger(__name__)


class AsyncTool(LangchainBaseTool):
    """
    A base tool with a default async implementation.
    Eliminates the duplicate _arun method across all tool classes.
    """

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Run the tool asynchronously in a thread pool."""
        loop = asyncio.get_running_loop()
        # This new line correctly handles both positional and keyword arguments.
        return await loop.run_in_executor(
            None, functools.partial(self._run, *args, **kwargs)
        )
