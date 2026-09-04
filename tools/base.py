#!/usr/bin/env python3
"""
Base tool class for all MCP tools
Eliminates code duplication as identified in claude_code_errors.md
"""

import asyncio
import logging
from langchain_core.tools import BaseTool as LangchainBaseTool

logger = logging.getLogger(__name__)

class AsyncTool(LangchainBaseTool):
    """
    A base tool with a default async implementation.
    Eliminates the duplicate _arun method across all tool classes.
    """
    
    async def _arun(self, *args, **kwargs):
        """Default async implementation that runs _run in executor"""
        # Import here to avoid circular imports
        from main import executor
        
        if not executor:
            return "Error: Server configuration issue (executor is not initialized)."
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, self._run, *args, **kwargs)