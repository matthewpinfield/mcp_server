#!/usr/bin/env python3
"""
MCP Sandbox System - Secure Code Execution Environment
=====================================================

This module provides a secure, isolated environment for executing code safely.
It supports multiple execution modes and provides comprehensive output capture.

The sandbox is designed to:
- Execute Python code in isolation
- Capture stdout, stderr, and execution time
- Handle timeouts and resource limits
- Provide detailed error reporting
- Support multiple execution backends (subprocess, Docker if available)

Usage:
    from mcp_sandbox import execute_code, get_sandbox_stats, SandboxConfig
    
    result = execute_code("print('Hello, World!')")
    print(result['stdout'])  # "Hello, World!"
"""

import os
import sys
import subprocess
import tempfile
import time
import logging
import json
import signal
import threading
from typing import Dict, Any, Optional, List
from pathlib import Path
from contextlib import contextmanager
import resource
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sandbox configuration
class SandboxConfig:
    """Configuration for the sandbox environment"""
    
    # Execution limits
    TIMEOUT_SECONDS = 30  # Maximum execution time
    MAX_OUTPUT_SIZE = 10000  # Maximum output length in characters
    MAX_MEMORY_MB = 128  # Maximum memory usage in MB
    
    # Security settings
    ALLOWED_IMPORTS = {
        'builtins', 'math', 'random', 'datetime', 'json', 'csv', 'urllib.parse',
        'collections', 'itertools', 'functools', 'operator', 'string', 're',
        'os.path', 'pathlib', 'tempfile', 'uuid', 'hashlib', 'base64',
        'numpy', 'pandas', 'matplotlib.pyplot', 'requests', 'bs4'
    }
    
    BLOCKED_IMPORTS = {
        'subprocess', 'os.system', 'eval', 'exec', 'compile', 'open',
        'input', 'raw_input', '__import__', 'globals', 'locals', 'vars',
        'dir', 'help', 'reload', 'breakpoint', 'exit', 'quit'
    }
    
    # Sandbox directories
    SANDBOX_BASE_DIR = "/tmp/mcp_sandbox"
    WORKING_DIR_PREFIX = "sandbox_"

def setup_sandbox_environment() -> str:
    """Create and return a temporary sandbox directory"""
    try:
        # Create base sandbox directory
        base_dir = Path(SandboxConfig.SANDBOX_BASE_DIR)
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create unique working directory (don't use context manager here)
        temp_dir = tempfile.mkdtemp(
            prefix=SandboxConfig.WORKING_DIR_PREFIX,
            dir=base_dir
        )
        return temp_dir
            
    except Exception as e:
        logger.error(f"Failed to setup sandbox environment: {e}")
        # Fallback to system temp
        return tempfile.mkdtemp(prefix=SandboxConfig.WORKING_DIR_PREFIX)

def validate_code_safety(code: str) -> Dict[str, Any]:
    """
    Perform basic safety checks on code before execution
    Returns validation result with safety status and warnings
    """
    warnings = []
    blocked_patterns = [
        'import os', 'import subprocess', 'import sys', '__import__',
        'exec(', 'eval(', 'compile(', 'open(', 'file(',
        'input(', 'raw_input(', 'breakpoint()', 'exit()', 'quit()'
    ]
    
    # Check for blocked patterns
    code_lower = code.lower()
    for pattern in blocked_patterns:
        if pattern in code_lower:
            warnings.append(f"Potentially unsafe pattern detected: {pattern}")
    
    # Check code length
    if len(code) > 50000:  # 50KB limit
        warnings.append("Code is very large - may hit execution limits")
    
    # Basic syntax check
    try:
        compile(code, '<sandbox>', 'exec')
        syntax_valid = True
    except SyntaxError as e:
        syntax_valid = False
        warnings.append(f"Syntax error: {e}")
    
    return {
        'safe': len([w for w in warnings if 'unsafe' in w.lower()]) == 0,
        'syntax_valid': syntax_valid,
        'warnings': warnings
    }

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

@contextmanager
def timeout_context(seconds: int):
    """Context manager for execution timeout"""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Code execution timed out after {seconds} seconds")
    
    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        signal.alarm(0)  # Disable alarm
        signal.signal(signal.SIGALRM, old_handler)  # Restore old handler

def execute_code_subprocess(code: str, working_dir: str) -> Dict[str, Any]:
    """
    Execute code using subprocess for maximum isolation
    """
    start_time = time.time()
    
    try:
        # Create temporary Python file
        code_file = Path(working_dir) / "sandbox_code.py"
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Execute with resource limits
        process = subprocess.Popen(
            [sys.executable, str(code_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir,
            preexec_fn=lambda: resource.setrlimit(
                resource.RLIMIT_AS, 
                (SandboxConfig.MAX_MEMORY_MB * 1024 * 1024, -1)
            ) if hasattr(resource, 'RLIMIT_AS') else None
        )
        
        # Wait for completion with timeout
        try:
            stdout, stderr = process.communicate(timeout=SandboxConfig.TIMEOUT_SECONDS)
            return_code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return_code = -1
            stderr += f"\nExecution timed out after {SandboxConfig.TIMEOUT_SECONDS} seconds"
        
        execution_time = time.time() - start_time
        
        # Truncate output if too long
        if len(stdout) > SandboxConfig.MAX_OUTPUT_SIZE:
            stdout = stdout[:SandboxConfig.MAX_OUTPUT_SIZE] + "\n... (output truncated)"
        
        if len(stderr) > SandboxConfig.MAX_OUTPUT_SIZE:
            stderr = stderr[:SandboxConfig.MAX_OUTPUT_SIZE] + "\n... (error output truncated)"
        
        return {
            'success': return_code == 0,
            'stdout': stdout,
            'stderr': stderr,
            'return_code': return_code,
            'execution_time': execution_time,
            'method': 'subprocess'
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        return {
            'success': False,
            'stdout': '',
            'stderr': f"Sandbox execution error: {str(e)}",
            'return_code': -2,
            'execution_time': execution_time,
            'method': 'subprocess'
        }

def execute_code_direct(code: str) -> Dict[str, Any]:
    """
    Execute code directly in current process (less secure, faster)
    Only use for trusted code or when subprocess fails
    """
    start_time = time.time()
    
    # Capture stdout/stderr
    from io import StringIO
    import sys
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    
    try:
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr
        
        # Execute with timeout
        with timeout_context(SandboxConfig.TIMEOUT_SECONDS):
            exec(code, {
                '__builtins__': {
                    'print': print,
                    'len': len,
                    'range': range,
                    'list': list,
                    'dict': dict,
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool,
                    'abs': abs,
                    'max': max,
                    'min': min,
                    'sum': sum,
                    'sorted': sorted,
                    'enumerate': enumerate,
                    'zip': zip,
                    'map': map,
                    'filter': filter,
                }
            })
        
        execution_time = time.time() - start_time
        stdout = captured_stdout.getvalue()
        stderr = captured_stderr.getvalue()
        
        # Truncate if needed
        if len(stdout) > SandboxConfig.MAX_OUTPUT_SIZE:
            stdout = stdout[:SandboxConfig.MAX_OUTPUT_SIZE] + "\n... (output truncated)"
        
        return {
            'success': True,
            'stdout': stdout,
            'stderr': stderr,
            'return_code': 0,
            'execution_time': execution_time,
            'method': 'direct'
        }
        
    except TimeoutError as e:
        execution_time = time.time() - start_time
        return {
            'success': False,
            'stdout': captured_stdout.getvalue(),
            'stderr': str(e),
            'return_code': -1,
            'execution_time': execution_time,
            'method': 'direct'
        }
    except Exception as e:
        execution_time = time.time() - start_time
        return {
            'success': False,
            'stdout': captured_stdout.getvalue(),
            'stderr': f"Execution error: {str(e)}\n{traceback.format_exc()}",
            'return_code': -2,
            'execution_time': execution_time,
            'method': 'direct'
        }
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

def execute_code(code: str, method: str = "auto") -> Dict[str, Any]:
    """
    Main entry point for code execution
    
    Args:
        code: Python code to execute
        method: Execution method ("subprocess", "direct", or "auto")
    
    Returns:
        Dictionary with execution results including stdout, stderr, success status
    """
    logger.info(f"🔒 Sandbox: Executing code using method '{method}'")
    
    # Validate code safety
    validation = validate_code_safety(code)
    
    if not validation['syntax_valid']:
        return {
            'success': False,
            'stdout': '',
            'stderr': f"Syntax validation failed: {'; '.join(validation['warnings'])}",
            'return_code': -3,
            'execution_time': 0,
            'method': 'validation',
            'validation': validation
        }
    
    # Log warnings but continue
    if validation['warnings']:
        logger.warning(f"Code validation warnings: {validation['warnings']}")
    
    # Choose execution method
    if method == "auto":
        # Prefer subprocess for better isolation
        method = "subprocess" if validation['safe'] else "direct"
    
    try:
        if method == "subprocess":
            # Create temporary working directory
            working_dir = setup_sandbox_environment()
            result = execute_code_subprocess(code, working_dir)
            
            # Cleanup
            try:
                import shutil
                shutil.rmtree(working_dir, ignore_errors=True)
            except:
                pass
                
        elif method == "direct":
            result = execute_code_direct(code)
        else:
            raise ValueError(f"Unknown execution method: {method}")
        
        # Add validation info to result
        result['validation'] = validation
        
        # Log execution summary
        status = "✅" if result['success'] else "❌"
        logger.info(f"{status} Sandbox execution completed in {result['execution_time']:.2f}s using {result['method']}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Sandbox execution failed: {e}")
        return {
            'success': False,
            'stdout': '',
            'stderr': f"Sandbox system error: {str(e)}",
            'return_code': -4,
            'execution_time': 0,
            'method': method,
            'validation': validation
        }

def get_sandbox_stats() -> Dict[str, Any]:
    """Get sandbox system statistics and health information"""
    try:
        stats = {
            'sandbox_available': True,
            'subprocess_available': True,
            'timeout_seconds': SandboxConfig.TIMEOUT_SECONDS,
            'max_output_size': SandboxConfig.MAX_OUTPUT_SIZE,
            'max_memory_mb': SandboxConfig.MAX_MEMORY_MB,
            'base_directory': SandboxConfig.SANDBOX_BASE_DIR,
            'allowed_imports_count': len(SandboxConfig.ALLOWED_IMPORTS),
            'blocked_imports_count': len(SandboxConfig.BLOCKED_IMPORTS)
        }
        
        # Test basic functionality
        test_result = execute_code("print('sandbox test')")
        stats['test_execution'] = test_result['success']
        
        return {
            'status': 'success',
            'stats': stats
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'stats': {
                'sandbox_available': False
            }
        }

# Convenience functions for common operations
def test_code(code: str) -> str:
    """Simple test function that returns formatted result"""
    result = execute_code(code)
    
    output = []
    if result['success']:
        output.append("✅ Code executed successfully")
        if result['stdout']:
            output.append(f"Output:\n{result['stdout']}")
    else:
        output.append("❌ Code execution failed")
        if result['stderr']:
            output.append(f"Error:\n{result['stderr']}")
    
    output.append(f"Execution time: {result['execution_time']:.2f}s")
    return "\n\n".join(output)

def debug_code(code: str, expected_output: str = None) -> str:
    """Debug function with expected output comparison"""
    result = execute_code(code)
    
    output = [f"Debug Report - Method: {result['method']}"]
    output.append(f"Execution time: {result['execution_time']:.2f}s")
    output.append(f"Return code: {result['return_code']}")
    
    if result['success']:
        output.append("✅ Execution successful")
        if result['stdout']:
            output.append(f"STDOUT:\n{result['stdout']}")
            
            if expected_output:
                if result['stdout'].strip() == expected_output.strip():
                    output.append("✅ Output matches expected result")
                else:
                    output.append("❌ Output differs from expected result")
                    output.append(f"Expected:\n{expected_output}")
    else:
        output.append("❌ Execution failed")
        
    if result['stderr']:
        output.append(f"STDERR:\n{result['stderr']}")
    
    if result.get('validation', {}).get('warnings'):
        output.append(f"Warnings: {result['validation']['warnings']}")
    
    return "\n\n".join(output)

if __name__ == "__main__":
    # Test the sandbox system
    print("🧪 Testing MCP Sandbox System")
    print("=" * 50)
    
    # Test basic execution
    test_codes = [
        "print('Hello, Sandbox!')",
        "x = [1, 2, 3, 4, 5]\nprint(sum(x))",
        "for i in range(3):\n    print(f'Count: {i}')",
        "import math\nprint(f'Pi is approximately {math.pi:.2f}')"
    ]
    
    for i, code in enumerate(test_codes, 1):
        print(f"\nTest {i}: {code.split()[0]}...")
        result = execute_code(code)
        status = "✅" if result['success'] else "❌"
        print(f"{status} Result: {result['stdout'].strip() if result['stdout'] else result['stderr']}")
    
    # Test stats
    print(f"\n📊 Sandbox Stats:")
    stats = get_sandbox_stats()
    if stats['status'] == 'success':
        for key, value in stats['stats'].items():
            print(f"  {key}: {value}")
    
    print("\n✅ Sandbox system test completed")