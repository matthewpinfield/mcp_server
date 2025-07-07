#!/usr/bin/env python3
"""
Subprocess helper utilities to eliminate redundant subprocess handling
"""

import subprocess
import logging
import os
from typing import Tuple, Optional, List

logger = logging.getLogger(__name__)

def run_command(
    cmd: List[str], 
    cwd: str, 
    timeout: int = 60,
    capture_output: bool = True,
    text: bool = True
) -> Tuple[Optional[str], Optional[str], int]:
    """
    Runs a command and handles common errors consistently.
    
    Args:
        cmd: Command as list of strings
        cwd: Working directory
        timeout: Timeout in seconds
        capture_output: Whether to capture stdout/stderr
        text: Whether to return strings instead of bytes
        
    Returns:
        Tuple of (stdout, stderr, returncode)
        Returns (None, error_message, error_code) on failure
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            env=os.environ
        )
        return result.stdout, result.stderr, result.returncode
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        return None, f"Command timed out after {timeout} seconds", -1
        
    except FileNotFoundError:
        logger.error(f"Command not found: {cmd[0]}")
        return None, f"Command not found: {cmd[0]}", -2
        
    except Exception as e:
        logger.error(f"Subprocess error running {' '.join(cmd)}: {e}")
        return None, f"An unexpected error occurred: {e}", -3

def run_git_command(
    git_args: List[str], 
    cwd: str, 
    timeout: int = 30
) -> Tuple[Optional[str], Optional[str], int]:
    """
    Convenience function for running git commands.
    
    Args:
        git_args: Git command arguments (without 'git')
        cwd: Repository directory
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (stdout, stderr, returncode)
    """
    cmd = ["git"] + git_args
    return run_command(cmd, cwd, timeout)

def is_git_installed() -> bool:
    """Check if git is installed and available."""
    try:
        result = subprocess.run(
            ["git", "--version"], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False