#!/usr/bin/env python3
"""
Import all tools from modular implementations
Following mcp_engineering_plan.md structure: 6 functional groupings
"""

# Code Analysis Tools
from .code_analysis import (
    LangchainAutoLinterTool,
    LangchainCodeMetricsTool,
    LangchainDependencyAnalysisTool,
    LangchainRepoExploreTool,
    LangchainSystemFileReaderTool,
)

# Development Tools
from .development import (
    LangchainBuildCommandTool,
    LangchainDateTimeTool,
    LangchainPackageSearchTool,
)

# Git Tools
from .git import (
    LangchainGitBranchTool,
    LangchainGitCommitTool,
    LangchainGitDiffTool,
    LangchainGitLogTool,
    LangchainGitStatusTool,
)

# GitHub Tools
from .github import (
    LangchainGitHubIssuesTool,
    LangchainGitHubReleasesTool,
    LangchainGitHubRepoSearchTool,
)

# Knowledge Tools
from .knowledge import (
    LangchainCodeSearchTool,
    LangchainFlutterDocTool,
)

# Sandbox Tools
from .sandbox import MultiLanguageSandboxTool, SandboxStatsTool

# Web Tools
# FIX: Import the new decorator-based tool function, not the old class.
from .web import search_web

# FIX: Update __all__ to export the correct tool name.
__all__ = [
    "LangchainGitStatusTool",
    "LangchainGitDiffTool",
    "LangchainGitCommitTool",
    "LangchainGitBranchTool",
    "LangchainGitLogTool",
    "LangchainAutoLinterTool",
    "LangchainRepoExploreTool",
    "LangchainDependencyAnalysisTool",
    "LangchainCodeMetricsTool",
    "LangchainSystemFileReaderTool",
    "LangchainBuildCommandTool",
    "LangchainPackageSearchTool",
    "MultiLanguageSandboxTool",
    "SandboxStatsTool",
    "search_web",
    "LangchainGitHubRepoSearchTool",
    "LangchainGitHubIssuesTool",
    "LangchainGitHubReleasesTool",
    "LangchainFlutterDocTool",
    "LangchainCodeSearchTool",
    "LangchainDateTimeTool",
]
