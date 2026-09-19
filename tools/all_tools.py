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
    LangchainWriteFileTool,
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

# RAG Tools
from .rag import (
    LangchainCodeSearchTool,
    LangchainFlutterDocTool,
)

# Sandbox Tools
from .sandbox import MultiLanguageSandboxTool, SandboxStatsTool

# Web Tools
from .web import LangchainWebSearchTool

# Memory Tools (Web-style two-step approach)
from .memory import (
    LangchainMemorySearchTool,
    LangchainGetFullMemoryTool,
    LangchainMemoryStatsTool,
    LangchainSaveAgentNoteTool,
    LangchainSearchAgentNotesTool,
)

# Rules Tools
from .rules import (
    LangchainAddRuleTool,
    LangchainListRulesTool,
    LangchainUpdateRuleTool,
    LangchainDeleteRuleTool,
)

__all__ = [
    # Git Tools
    "LangchainGitStatusTool",
    "LangchainGitDiffTool",
    "LangchainGitCommitTool",
    "LangchainGitBranchTool",
    "LangchainGitLogTool",
    # Code Analysis Tools
    "LangchainAutoLinterTool",
    "LangchainRepoExploreTool",
    "LangchainDependencyAnalysisTool",
    "LangchainCodeMetricsTool",
    "LangchainSystemFileReaderTool",
    "LangchainWriteFileTool",
    # Development Tools
    "LangchainBuildCommandTool",
    "LangchainPackageSearchTool",
    "LangchainDateTimeTool",
    # Sandbox Tools
    "MultiLanguageSandboxTool",
    "SandboxStatsTool",
    # Web Tools
    "LangchainWebSearchTool",
    # GitHub Tools
    "LangchainGitHubRepoSearchTool",
    "LangchainGitHubIssuesTool",
    "LangchainGitHubReleasesTool",
    # RAG Tools
    "LangchainFlutterDocTool",
    "LangchainCodeSearchTool",
    # Memory Tools
    "LangchainMemorySearchTool",
    "LangchainGetFullMemoryTool", 
    "LangchainMemoryStatsTool",
    "LangchainSaveAgentNoteTool",
    "LangchainSearchAgentNotesTool",
    # Rules Tools
    "LangchainAddRuleTool",
    "LangchainListRulesTool",
    "LangchainUpdateRuleTool",
    "LangchainDeleteRuleTool",
]

# Shared tool instances - created once at module load to avoid repeated instantiation
# Only includes tools that are actually functional and accessible to the agent
SHARED_TOOLS = [
    # Git Tools
    LangchainGitStatusTool(), LangchainGitDiffTool(), LangchainGitCommitTool(),
    LangchainGitBranchTool(), LangchainGitLogTool(),
    # Code Analysis Tools
    LangchainAutoLinterTool(), LangchainRepoExploreTool(), LangchainDependencyAnalysisTool(),
    LangchainCodeMetricsTool(), LangchainSystemFileReaderTool(), LangchainWriteFileTool(),
    # Development Tools
    LangchainBuildCommandTool(), LangchainPackageSearchTool(), LangchainDateTimeTool(),
    # Sandbox Tools
    MultiLanguageSandboxTool(), SandboxStatsTool(),
    # Web Tools
    LangchainWebSearchTool(),
    # GitHub Tools
    LangchainGitHubRepoSearchTool(), LangchainGitHubIssuesTool(), LangchainGitHubReleasesTool(),
    # RAG Tools
    LangchainFlutterDocTool(), LangchainCodeSearchTool(),
    # Memory Tools (two-step approach + stats + agent notes - user memory save is automatic via orchestrator)
    LangchainMemorySearchTool(), LangchainGetFullMemoryTool(), LangchainMemoryStatsTool(),
    LangchainSaveAgentNoteTool(), LangchainSearchAgentNotesTool(),
    # Rules Tools (list only - add/update/delete handled via slash commands)
    LangchainListRulesTool(),
]
