#!/usr/bin/env python3
"""
Build Tools - Project Build and Test Execution
==============================================

This module contains build and test execution tools for the MCP server.
Provides project-specific build, test, run, and clean commands.
"""

import subprocess
import os
import json
import logging
from pathlib import Path
from typing import Type, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool as LangchainBaseTool

logger = logging.getLogger(__name__)

# ===== SCHEMAS =====

class BuildCommandSchema(BaseModel):
    command: str = Field(description="Build command: 'build', 'test', 'run', 'clean', 'install', 'detect'")
    directory: str = Field(description="Project directory", default=".")
    options: Optional[str] = Field(description="Additional command options", default=None)

# ===== TOOL CLASS =====

class LangchainBuildCommandTool(LangchainBaseTool):
    name: str = "execute_build_command"
    description: str = "Execute project-specific build, test, run, and clean commands. Auto-detects project type (Flutter, npm, Python, etc.)"
    args_schema: Type[BaseModel] = BuildCommandSchema

    def _run(self, command: str, directory: str = ".", options: Optional[str] = None) -> str:
        logger.info(f"Build Command: command='{command}', directory='{directory}', options='{options}'")
        try:
            path = Path(directory).resolve()
            if not path.exists():
                return f"Directory does not exist: {directory}"
            
            os.chdir(path)
            
            if command == "detect":
                return self._detect_project_type(path)
            
            project_type = self._detect_project_type_internal(path)
            
            if command == "build":
                return self._run_build(path, project_type, options)
            elif command == "test":
                return self._run_test(path, project_type, options)
            elif command == "run":
                return self._run_project(path, project_type, options)
            elif command == "clean":
                return self._run_clean(path, project_type, options)
            elif command == "install":
                return self._run_install(path, project_type, options)
            else:
                return f"Unknown command '{command}'. Use: build, test, run, clean, install, detect"
                
        except Exception as e:
            logger.error(f"Build Command error: {e}")
            return f"Build command failed: {str(e)}"
    
    def _detect_project_type_internal(self, path: Path) -> str:
        """Internal project type detection"""
        if (path / 'pubspec.yaml').exists():
            return 'flutter'
        elif (path / 'package.json').exists():
            return 'nodejs'
        elif (path / 'requirements.txt').exists() or (path / 'setup.py').exists():
            return 'python'
        elif (path / 'Cargo.toml').exists():
            return 'rust'
        elif (path / 'go.mod').exists():
            return 'go'
        elif (path / 'pom.xml').exists():
            return 'maven'
        elif (path / 'build.gradle').exists() or (path / 'build.gradle.kts').exists():
            return 'gradle'
        elif (path / 'Makefile').exists():
            return 'make'
        else:
            return 'unknown'
    
    def _detect_project_type(self, path: Path) -> str:
        """Detect and describe project type"""
        project_type = self._detect_project_type_internal(path)
        
        details = {
            'flutter': 'Flutter/Dart project (pubspec.yaml found)',
            'nodejs': 'Node.js project (package.json found)',
            'python': 'Python project (requirements.txt or setup.py found)',
            'rust': 'Rust project (Cargo.toml found)',
            'go': 'Go project (go.mod found)',
            'maven': 'Maven project (pom.xml found)',
            'gradle': 'Gradle project (build.gradle found)',
            'make': 'Makefile project (Makefile found)',
            'unknown': 'Unknown project type - no recognized build files found'
        }
        
        return f"Project type detected: {details.get(project_type, 'Unknown')}"
    
    def _run_build(self, path: Path, project_type: str, options: Optional[str]) -> str:
        """Run build command for the detected project type"""
        try:
            if project_type == 'flutter':
                cmd = ['flutter', 'build', 'apk'] if not options else ['flutter', 'build'] + options.split()
            elif project_type == 'nodejs':
                cmd = ['npm', 'run', 'build'] if not options else ['npm'] + options.split()
            elif project_type == 'python':
                cmd = ['python', 'setup.py', 'build'] if not options else options.split()
            elif project_type == 'rust':
                cmd = ['cargo', 'build'] if not options else ['cargo', 'build'] + options.split()
            elif project_type == 'go':
                cmd = ['go', 'build'] if not options else ['go', 'build'] + options.split()
            elif project_type == 'maven':
                cmd = ['mvn', 'compile'] if not options else ['mvn'] + options.split()
            elif project_type == 'gradle':
                cmd = ['./gradlew', 'build'] if not options else ['./gradlew'] + options.split()
            elif project_type == 'make':
                cmd = ['make'] if not options else ['make'] + options.split()
            else:
                return f"Build not supported for project type: {project_type}"
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            output = f"Build command: {' '.join(cmd)}\n"
            output += f"Exit code: {result.returncode}\n\n"
            
            if result.stdout:
                output += f"Output:\n{result.stdout}\n"
            if result.stderr:
                output += f"Errors:\n{result.stderr}\n"
            
            return output
            
        except subprocess.TimeoutExpired:
            return "Build command timed out (5 minutes)"
        except FileNotFoundError:
            return f"Build tool not found for {project_type} project"
        except Exception as e:
            return f"Build execution error: {e}"
    
    def _run_test(self, path: Path, project_type: str, options: Optional[str]) -> str:
        """Run test command for the detected project type"""
        try:
            if project_type == 'flutter':
                cmd = ['flutter', 'test'] if not options else ['flutter', 'test'] + options.split()
            elif project_type == 'nodejs':
                cmd = ['npm', 'test'] if not options else ['npm', 'test'] + options.split()
            elif project_type == 'python':
                cmd = ['python', '-m', 'pytest'] if not options else ['python', '-m', 'pytest'] + options.split()
            elif project_type == 'rust':
                cmd = ['cargo', 'test'] if not options else ['cargo', 'test'] + options.split()
            elif project_type == 'go':
                cmd = ['go', 'test', './...'] if not options else ['go', 'test'] + options.split()
            elif project_type == 'maven':
                cmd = ['mvn', 'test'] if not options else ['mvn', 'test'] + options.split()
            elif project_type == 'gradle':
                cmd = ['./gradlew', 'test'] if not options else ['./gradlew', 'test'] + options.split()
            else:
                return f"Test not supported for project type: {project_type}"
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            output = f"Test command: {' '.join(cmd)}\n"
            output += f"Exit code: {result.returncode}\n\n"
            
            if result.stdout:
                output += f"Output:\n{result.stdout}\n"
            if result.stderr:
                output += f"Errors:\n{result.stderr}\n"
            
            return output
            
        except subprocess.TimeoutExpired:
            return "Test command timed out (5 minutes)"
        except FileNotFoundError:
            return f"Test tool not found for {project_type} project"
        except Exception as e:
            return f"Test execution error: {e}"
    
    def _run_project(self, path: Path, project_type: str, options: Optional[str]) -> str:
        """Run the project"""
        if project_type == 'flutter':
            return "Use 'flutter run' directly for Flutter projects (requires device/emulator)"
        elif project_type == 'nodejs':
            return "Use 'npm start' or 'node index.js' directly for Node.js projects"
        elif project_type == 'python':
            return "Specify the Python file to run (e.g., 'python main.py')"
        else:
            return f"Run not supported for project type: {project_type}"
    
    def _run_clean(self, path: Path, project_type: str, options: Optional[str]) -> str:
        """Clean build artifacts"""
        try:
            if project_type == 'flutter':
                cmd = ['flutter', 'clean']
            elif project_type == 'nodejs':
                cmd = ['npm', 'run', 'clean'] if (path / 'package.json').exists() else ['rm', '-rf', 'node_modules']
            elif project_type == 'rust':
                cmd = ['cargo', 'clean']
            elif project_type == 'go':
                cmd = ['go', 'clean']
            elif project_type == 'maven':
                cmd = ['mvn', 'clean']
            elif project_type == 'gradle':
                cmd = ['./gradlew', 'clean']
            elif project_type == 'make':
                cmd = ['make', 'clean']
            else:
                return f"Clean not supported for project type: {project_type}"
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return f"Clean successful: {' '.join(cmd)}\n{result.stdout}"
            else:
                return f"Clean failed: {result.stderr}"
                
        except Exception as e:
            return f"Clean error: {e}"
    
    def _run_install(self, path: Path, project_type: str, options: Optional[str]) -> str:
        """Install dependencies"""
        try:
            if project_type == 'flutter':
                cmd = ['flutter', 'pub', 'get']
            elif project_type == 'nodejs':
                cmd = ['npm', 'install']
            elif project_type == 'python':
                cmd = ['pip', 'install', '-r', 'requirements.txt'] if (path / 'requirements.txt').exists() else ['pip', 'install', '.']
            elif project_type == 'rust':
                cmd = ['cargo', 'build']  # Cargo automatically installs dependencies
            elif project_type == 'go':
                cmd = ['go', 'mod', 'download']
            else:
                return f"Install not supported for project type: {project_type}"
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            output = f"Install command: {' '.join(cmd)}\n"
            output += f"Exit code: {result.returncode}\n\n"
            
            if result.stdout:
                output += f"Output:\n{result.stdout}\n"
            if result.stderr:
                output += f"Errors:\n{result.stderr}\n"
            
            return output
            
        except subprocess.TimeoutExpired:
            return "Install command timed out (5 minutes)"
        except Exception as e:
            return f"Install error: {e}"

    async def _arun(self, command: str, directory: str = ".", options: Optional[str] = None) -> str:
        return self._run(command, directory, options)