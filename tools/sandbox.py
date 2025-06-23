#!/usr/bin/env python3
"""
Multi-Language Code Sandbox Execution Tools
===========================================

Real implementation using Docker containers for secure, isolated code execution
across multiple programming languages.

Supported Languages:
- Python, JavaScript, TypeScript, Java, C++, Go, Rust, PHP, Ruby, C, Dart, Flutter

Security:
- Docker-based isolation
- Execution time limits
- Memory limits
- Network isolation
- No persistent file access
"""

import subprocess
import json
import logging
import tempfile
import os
import time
from typing import Type, Dict, Optional, List
from pydantic.v1 import BaseModel, Field
from pathlib import Path

from .base import AsyncTool

logger = logging.getLogger(__name__)

# Language configuration for Docker-based execution
LANGUAGE_CONFIG = {
    'python': {
        'image': 'python:3.11-alpine',
        'file_ext': '.py',
        'cmd_template': ['python', '{filename}'],
        'timeout': 30
    },
    'javascript': {
        'image': 'node:18-alpine',
        'file_ext': '.js',
        'cmd_template': ['node', '{filename}'],
        'timeout': 30
    },
    'typescript': {
        'image': 'node:18-alpine',
        'file_ext': '.ts',
        'cmd_template': ['sh', '-c', 'npm install -g typescript && tsc {filename} --outDir /tmp && node /tmp/{basename}.js'],
        'timeout': 45
    },
    'java': {
        'image': 'openjdk:11-alpine',
        'file_ext': '.java',
        'cmd_template': ['sh', '-c', 'javac {filename} && java {classname}'],
        'timeout': 45
    },
    'cpp': {
        'image': 'gcc:alpine',
        'file_ext': '.cpp',
        'cmd_template': ['sh', '-c', 'g++ {filename} -o /tmp/program && /tmp/program'],
        'timeout': 45
    },
    'c': {
        'image': 'gcc:alpine',
        'file_ext': '.c',
        'cmd_template': ['sh', '-c', 'gcc {filename} -o /tmp/program && /tmp/program'],
        'timeout': 45
    },
    'go': {
        'image': 'golang:alpine',
        'file_ext': '.go',
        'cmd_template': ['go', 'run', '{filename}'],
        'timeout': 30
    },
    'rust': {
        'image': 'rust:alpine',
        'file_ext': '.rs',
        'cmd_template': ['sh', '-c', 'rustc {filename} -o /tmp/program && /tmp/program'],
        'timeout': 60
    },
    'php': {
        'image': 'php:alpine',
        'file_ext': '.php',
        'cmd_template': ['php', '{filename}'],
        'timeout': 30
    },
    'ruby': {
        'image': 'ruby:alpine',
        'file_ext': '.rb',
        'cmd_template': ['ruby', '{filename}'],
        'timeout': 30
    },
    'dart': {
        'image': 'dart:stable',
        'file_ext': '.dart',
        'cmd_template': ['dart', 'run', '{filename}'],
        'timeout': 30
    },
    'flutter': {
        'image': 'cirrusci/flutter:stable',
        'file_ext': '.dart',
        'cmd_template': ['sh', '-c', 'flutter create --template=console /tmp/flutter_app && cp {filename} /tmp/flutter_app/lib/main.dart && cd /tmp/flutter_app && flutter run --device-id=flutter-tester'],
        'timeout': 120
    }
}

class SandboxExecuteSchema(BaseModel):
    tool_input: str = Field(description="JSON string containing: {\"code\": \"code to execute\", \"language\": \"python|javascript|typescript|java|cpp|c|go|rust|php|ruby|dart|flutter\", \"timeout\": 30, \"stdin_input\": \"\"}")

class SandboxStatsSchema(BaseModel):
    pass  # No parameters needed

def check_docker_available() -> bool:
    """Check if Docker is available and running"""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def execute_code_in_docker(code: str, language: str, timeout: int = 30, stdin_input: str = "") -> Dict:
    """Execute code in a Docker container"""
    if language not in LANGUAGE_CONFIG:
        return {
            "success": False,
            "error": f"Unsupported language: {language}. Supported: {', '.join(LANGUAGE_CONFIG.keys())}"
        }
    
    if not check_docker_available():
        return {
            "success": False,
            "error": "Docker is not available or not running"
        }
    
    config = LANGUAGE_CONFIG[language]
    max_timeout = min(timeout, 120)  # Hard limit of 2 minutes
    
    try:
        # Create temporary file for code
        with tempfile.NamedTemporaryFile(mode='w', suffix=config['file_ext'], delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        # Get filename components
        filename = os.path.basename(temp_file)
        basename = os.path.splitext(filename)[0]
        classname = basename if language == 'java' else basename
        
        # Format command template
        cmd = []
        for part in config['cmd_template']:
            cmd.append(part.format(
                filename=f'/code/{filename}',
                basename=basename,
                classname=classname
            ))
        
        # Build Docker command
        docker_cmd = [
            'docker', 'run',
            '--rm',
            '--network=none',  # No network access
            '--memory=128m',   # 128MB memory limit
            '--cpus=0.5',      # 0.5 CPU limit
            f'--volume={temp_file}:/code/{filename}:ro',  # Mount code file as read-only
            '--workdir=/code',
            config['image']
        ] + cmd
        
        logger.info(f"Executing {language} code in Docker: {docker_cmd}")
        
        # Execute with timeout
        start_time = time.time()
        result = subprocess.run(
            docker_cmd,
            input=stdin_input,
            capture_output=True,
            text=True,
            timeout=max_timeout
        )
        execution_time = time.time() - start_time
        
        # Clean up temp file
        os.unlink(temp_file)
        
        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": execution_time,
            "language": language,
            "timeout_used": max_timeout
        }
        
    except subprocess.TimeoutExpired:
        # Clean up temp file
        if 'temp_file' in locals():
            try:
                os.unlink(temp_file)
            except:
                pass
        return {
            "success": False,
            "error": f"Code execution timed out after {max_timeout} seconds",
            "execution_time": max_timeout,
            "language": language
        }
    except Exception as e:
        # Clean up temp file
        if 'temp_file' in locals():
            try:
                os.unlink(temp_file)
            except:
                pass
        return {
            "success": False,
            "error": f"Execution error: {str(e)}",
            "language": language
        }

def get_sandbox_stats() -> Dict:
    """Get real sandbox system statistics"""
    try:
        # Check Docker availability
        docker_available = check_docker_available()
        
        # Get Docker info if available
        docker_info = {}
        if docker_available:
            try:
                result = subprocess.run(['docker', 'info', '--format', 'json'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    docker_info = json.loads(result.stdout)
            except:
                pass
        
        # Check available language images
        available_languages = []
        if docker_available:
            for lang, config in LANGUAGE_CONFIG.items():
                try:
                    # Check if image exists locally
                    result = subprocess.run(['docker', 'image', 'inspect', config['image']], 
                                          capture_output=True, timeout=10)
                    if result.returncode == 0:
                        available_languages.append(lang)
                except:
                    pass
        
        return {
            "status": "success",
            "stats": {
                "docker_available": docker_available,
                "docker_version": docker_info.get("ServerVersion", "unknown") if docker_available else None,
                "supported_languages": list(LANGUAGE_CONFIG.keys()),
                "available_languages": available_languages,
                "max_timeout": 120,
                "memory_limit": "128MB",
                "cpu_limit": "0.5",
                "network_isolation": True,
                "total_languages": len(LANGUAGE_CONFIG)
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to get sandbox stats: {str(e)}"
        }

# ===== TOOL CLASSES =====

class MultiLanguageSandboxTool(AsyncTool):
    name: str = "execute_code"
    description: str = (
        "Execute code in a secure, isolated Docker-based sandbox environment. "
        "Supports multiple programming languages: Python, JavaScript, TypeScript, Java, C++, C, Go, Rust, PHP, Ruby, Dart, Flutter. "
        "SECURITY: Complete isolation via Docker containers with network restrictions, memory limits (128MB), CPU limits (0.5), and execution timeouts. "
        "LIMITS: Max 120s timeout, no persistent storage, no network access. "
        "Use for: testing code snippets, running algorithms, code verification, and educational purposes."
    )
    args_schema: Type[BaseModel] = SandboxExecuteSchema

    def _run(self, tool_input: str) -> str:
        # Parse the JSON input string (LangChain ReAct agent compatible)
        try:
            import json
            if isinstance(tool_input, str) and tool_input.startswith('{'):
                # Try to parse as JSON
                parsed = json.loads(tool_input)
                code = parsed.get('code', '')
                language = parsed.get('language', 'python')
                timeout = parsed.get('timeout', None)
                stdin_input = parsed.get('stdin_input', '')
            else:
                # Plain text - treat as code with default language Python
                code = tool_input
                language = "python"
                timeout = None
                stdin_input = ""
                
        except json.JSONDecodeError:
            # If JSON parsing fails, treat as plain code with default language
            code = tool_input
            language = "python"
            timeout = None
            stdin_input = ""
        
        logger.info(f"Multi-Language Sandbox: executing {len(code)} chars of {language} code")
        
        # Use language-specific timeout or default
        if timeout is None:
            timeout = LANGUAGE_CONFIG.get(language, {}).get('timeout', 30)
        
        try:
            result = execute_code_in_docker(code, language.lower(), timeout, stdin_input)
            
            if result.get("success"):
                response = f"✅ Code executed successfully in {result.get('execution_time', 0):.3f}s\n"
                response += f"Language: {result.get('language', language)}\n"
                
                stdout = result.get("stdout", "")
                if stdout:
                    response += f"\n📤 Output:\n{stdout}"
                else:
                    response += "\n📭 No output produced"
                
                stderr = result.get("stderr", "")
                if stderr:
                    response += f"\n⚠️  Stderr:\n{stderr}"
                
                return response
            else:
                error_msg = result.get("error", "Unknown error")
                stderr = result.get("stderr", "")
                
                response = f"❌ Code execution failed\n"
                response += f"Language: {result.get('language', language)}\n"
                response += f"Error: {error_msg}\n"
                
                if stderr:
                    response += f"Stderr: {stderr}"
                
                return response
                
        except Exception as e:
            logger.error(f"Multi-Language Sandbox error: {e}")
            return f"❌ Sandbox execution error: {str(e)}"

class SandboxStatsTool(AsyncTool):
    name: str = "get_sandbox_stats"
    description: str = "Get real-time information about the multi-language sandbox system status, available languages, and Docker configuration."
    args_schema: Type[BaseModel] = SandboxStatsSchema

    def _run(self) -> str:
        logger.info("Getting sandbox statistics")
        try:
            result = get_sandbox_stats()
            
            if result["status"] == "success":
                stats = result["stats"]
                
                response = "🔧 **Multi-Language Sandbox Statistics**\n\n"
                response += f"🐳 Docker Available: {'✅' if stats['docker_available'] else '❌'}\n"
                
                if stats['docker_available']:
                    response += f"🔧 Docker Version: {stats.get('docker_version', 'unknown')}\n"
                    response += f"🌐 Network Isolation: {'✅' if stats['network_isolation'] else '❌'}\n"
                    response += f"💾 Memory Limit: {stats['memory_limit']}\n"
                    response += f"⚡ CPU Limit: {stats['cpu_limit']}\n"
                    response += f"⏱️  Max Timeout: {stats['max_timeout']}s\n\n"
                    
                    response += f"📚 **Supported Languages** ({stats['total_languages']}):\n"
                    for lang in stats['supported_languages']:
                        status = "✅" if lang in stats['available_languages'] else "📥"
                        response += f"  {status} {lang}\n"
                    
                    if stats['available_languages']:
                        response += f"\n🚀 **Ready Languages**: {len(stats['available_languages'])}/{stats['total_languages']}\n"
                    else:
                        response += f"\n⚠️  **No Docker images available** - run `docker pull` for required images\n"
                else:
                    response += "\n❌ **Docker not available** - install and start Docker to use sandbox\n"
                
                return response
            else:
                return f"❌ Failed to get sandbox stats: {result.get('error', 'Unknown error')}"
                
        except Exception as e:
            logger.error(f"Sandbox Stats error: {e}")
            return f"❌ Sandbox stats error: {str(e)}"