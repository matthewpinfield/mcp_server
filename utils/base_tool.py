#!/usr/bin/env python3
"""
Base tool classes to eliminate code duplication
"""

import asyncio
import logging
from langchain_core.tools import BaseTool as LangchainBaseTool
from typing import Any

logger = logging.getLogger(__name__)

class AsyncTool(LangchainBaseTool):
    """Base tool with standardized async implementation to eliminate code duplication"""
    
    async def _arun(self, *args, **kwargs) -> str:
        """
        Standardized async implementation that all tools can use.
        Eliminates the duplicate _arun methods found in 20+ tool classes.
        """
        # Just call _run directly - the backup file tools don't need executor
        return self._run(*args, **kwargs)