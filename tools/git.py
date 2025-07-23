#!/usr/bin/env python3
"""
Git Tools - Version Control Operations
=====================================

This module contains all git-related tools for the MCP server.
Provides unified interface for git operations like status, diff, commit, branch, log.
"""

import logging
import os
import subprocess
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from .base import AsyncTool

logger = logging.getLogger(__name__)

# ===== SCHEMAS =====


class GitStatusSchema(BaseModel):
    path: str = Field(
        description="Path to git repository (default: current directory)", default="."
    )


class GitDiffSchema(BaseModel):
    path: str = Field(
        description="Path to git repository (default: current directory)", default="."
    )
    file_path: Optional[str] = Field(
        description="Specific file to diff (optional)", default=None
    )
    staged: bool = Field(description="Show staged changes only", default=False)


class GitCommitSchema(BaseModel):
    path: str = Field(
        description="Path to git repository (default: current directory)", default="."
    )
    message: str = Field(description="Commit message")
    add_all: bool = Field(
        description="Add all changes before committing", default=False
    )


class GitBranchSchema(BaseModel):
    path: str = Field(
        description="Path to git repository (default: current directory)", default="."
    )
    action: str = Field(description="Action: 'list', 'create', 'checkout', 'delete'")
    branch_name: Optional[str] = Field(
        description="Branch name (required for create/checkout/delete)", default=None
    )


class GitLogSchema(BaseModel):
    path: str = Field(
        description="Path to git repository (default: current directory)", default="."
    )
    limit: int = Field(description="Number of commits to show", default=10)
    oneline: bool = Field(description="Show one line per commit", default=True)


# ===== TOOL CLASSES =====


class LangchainGitStatusTool(AsyncTool):
    name: str = "git_status"
    description: str = (
        "Get git repository status showing staged, modified, and untracked files."
    )
    args_schema: Type[BaseModel] = GitStatusSchema

    def _run(self, path: str = ".") -> str:
        logger.info(f"Git Status Tool: path='{path}'")
        try:
            os.chdir(path)
            result = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return f"Git status failed: {result.stderr}"

            # Parse porcelain output
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

            staged = []
            modified = []
            untracked = []

            for line in lines:
                if len(line) >= 3:
                    status = line[:2]
                    filename = line[3:]

                    if status[0] in ["A", "M", "D", "R", "C"]:
                        staged.append(f"{status[0]} {filename}")
                    elif status[1] in ["M", "D"]:
                        modified.append(f"{status[1]} {filename}")
                    elif status == "??":
                        untracked.append(filename)

            # Get current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            current_branch = (
                branch_result.stdout.strip()
                if branch_result.returncode == 0
                else "unknown"
            )

            summary = f"Git Status (branch: {current_branch}):\n"
            summary += f"• Staged: {len(staged)} files\n"
            summary += f"• Modified: {len(modified)} files\n"
            summary += f"• Untracked: {len(untracked)} files\n\n"

            if staged:
                summary += (
                    "Staged changes:\n"
                    + "\n".join(f"  {item}" for item in staged)
                    + "\n\n"
                )
            if modified:
                summary += (
                    "Modified files:\n"
                    + "\n".join(f"  M {item}" for item in modified)
                    + "\n\n"
                )
            if untracked:
                summary += (
                    "Untracked files:\n"
                    + "\n".join(f"  ?? {item}" for item in untracked[:10])
                    + "\n"
                )
                if len(untracked) > 10:
                    summary += f"  ... and {len(untracked) - 10} more\n"

            return summary

        except subprocess.TimeoutExpired:
            return "Git status command timed out"
        except Exception as e:
            logger.error(f"Git Status Tool error: {e}")
            return f"Git status error: {str(e)}"


class LangchainGitDiffTool(AsyncTool):
    name: str = "git_diff"
    description: str = "Show git diff for changes in the repository."
    args_schema: Type[BaseModel] = GitDiffSchema

    def _run(
        self, path: str = ".", file_path: Optional[str] = None, staged: bool = False
    ) -> str:
        logger.info(
            f"Git Diff Tool: path='{path}', file='{file_path}', staged={staged}"
        )
        try:
            os.chdir(path)

            cmd = ["git", "diff"]
            if staged:
                cmd.append("--staged")
            if file_path:
                cmd.append(file_path)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                return f"Git diff failed: {result.stderr}"

            if not result.stdout.strip():
                return "No changes found" + (" in staged files" if staged else "")

            # Limit output size
            diff_output = result.stdout
            if len(diff_output) > 5000:
                diff_output = diff_output[:5000] + "\n... (output truncated)"

            return f"Git Diff {'(staged)' if staged else ''}:\n{diff_output}"

        except subprocess.TimeoutExpired:
            return "Git diff command timed out"
        except Exception as e:
            logger.error(f"Git Diff Tool error: {e}")
            return f"Git diff error: {str(e)}"


class LangchainGitCommitTool(AsyncTool):
    name: str = "git_commit"
    description: str = "Commit changes to git repository."
    args_schema: Type[BaseModel] = GitCommitSchema

    def _run(self, path: str = ".", message: str = "", add_all: bool = False) -> str:
        logger.info(f"Git Commit Tool: path='{path}', add_all={add_all}")
        try:
            os.chdir(path)

            if add_all:
                add_result = subprocess.run(
                    ["git", "add", "."], capture_output=True, text=True, timeout=30
                )
                if add_result.returncode != 0:
                    return f"Git add failed: {add_result.stderr}"

            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return f"Git commit failed: {result.stderr}"

            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
            )
            commit_hash = (
                hash_result.stdout.strip()[:8]
                if hash_result.returncode == 0
                else "unknown"
            )

            return (
                f"Commit successful: {commit_hash}\nMessage: {message}\n{result.stdout}"
            )

        except subprocess.TimeoutExpired:
            return "Git commit command timed out"
        except Exception as e:
            logger.error(f"Git Commit Tool error: {e}")
            return f"Git commit error: {str(e)}"


class LangchainGitBranchTool(AsyncTool):
    name: str = "git_branch"
    description: str = "Manage git branches (list, create, checkout, delete)."
    args_schema: Type[BaseModel] = GitBranchSchema

    def _run(
        self, path: str = ".", action: str = "list", branch_name: Optional[str] = None
    ) -> str:
        logger.info(
            f"Git Branch Tool: path='{path}', action='{action}', branch='{branch_name}'"
        )
        try:
            os.chdir(path)

            if action == "list":
                result = subprocess.run(
                    ["git", "branch", "-a"], capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    return f"Git branch list failed: {result.stderr}"
                return f"Git branches:\n{result.stdout}"

            elif action == "create":
                if not branch_name:
                    return "Branch name required for create action"
                result = subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    return f"Git branch create failed: {result.stderr}"
                return f"Created and checked out branch: {branch_name}\n{result.stdout}"

            elif action == "checkout":
                if not branch_name:
                    return "Branch name required for checkout action"
                result = subprocess.run(
                    ["git", "checkout", branch_name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    return f"Git checkout failed: {result.stderr}"
                return f"Checked out branch: {branch_name}\n{result.stdout}"

            elif action == "delete":
                if not branch_name:
                    return "Branch name required for delete action"
                result = subprocess.run(
                    ["git", "branch", "-d", branch_name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    return f"Git branch delete failed: {result.stderr}"
                return f"Deleted branch: {branch_name}\n{result.stdout}"

            else:
                return f"Unknown action: {action}. Use: list, create, checkout, delete"

        except subprocess.TimeoutExpired:
            return "Git branch command timed out"
        except Exception as e:
            logger.error(f"Git Branch Tool error: {e}")
            return f"Git branch error: {str(e)}"


class LangchainGitLogTool(AsyncTool):
    name: str = "git_log"
    description: str = "Show git commit history."
    args_schema: Type[BaseModel] = GitLogSchema

    def _run(self, path: str = ".", limit: int = 10, oneline: bool = True) -> str:
        logger.info(f"Git Log Tool: path='{path}', limit={limit}, oneline={oneline}")
        try:
            os.chdir(path)

            cmd = ["git", "log", f"-{limit}"]
            if oneline:
                cmd.append("--oneline")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                return f"Git log failed: {result.stderr}"

            if not result.stdout.strip():
                return "No commits found"

            return f"Git Log (last {limit} commits):\n{result.stdout}"

        except subprocess.TimeoutExpired:
            return "Git log command timed out"
        except Exception as e:
            logger.error(f"Git Log Tool error: {e}")
            return f"Git log error: {str(e)}"
