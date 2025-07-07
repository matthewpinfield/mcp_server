#!/usr/bin/env python3
"""
Repository Analysis Tools - Codebase Structure and Metrics
=========================================================

This module contains repository analysis tools for the MCP server.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool as LangchainBaseTool

logger = logging.getLogger(__name__)

class RepoExploreSchema(BaseModel):
    path: str = Field(description="Repository path", default=".")
    analysis_type: str = Field(description="Analysis type: 'structure', 'files', 'git'", default="structure")

class DependencyAnalysisSchema(BaseModel):
    path: str = Field(description="Project path", default=".")

class CodeMetricsSchema(BaseModel):
    path: str = Field(description="Project path", default=".")

class LangchainRepoExploreTool(LangchainBaseTool):
    name: str = "explore_repository"
    description: str = "Analyze repository structure, files, and git information"
    args_schema: Type[BaseModel] = RepoExploreSchema

    def _run(self, path: str = ".", analysis_type: str = "structure") -> str:
        logger.info(f"Repo Explore: path='{path}', type='{analysis_type}'")
        try:
            repo_path = Path(path).resolve()
            if not repo_path.exists():
                return f"Path does not exist: {path}"
            
            if analysis_type == "structure":
                return self._analyze_structure(repo_path)
            elif analysis_type == "files":
                return self._analyze_files(repo_path)
            elif analysis_type == "git":
                return self._analyze_git(repo_path)
            else:
                return f"Unknown analysis type: {analysis_type}"
                
        except Exception as e:
            return f"Repository analysis error: {str(e)}"
    
    def _analyze_structure(self, path: Path) -> str:
        """Analyze directory structure"""
        try:
            result = subprocess.run(['tree', str(path), '-L', '3'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return f"Repository structure:\n{result.stdout}"
            else:
                # Fallback to basic listing
                items = list(path.iterdir())
                structure = f"Repository contents ({len(items)} items):\n"
                for item in items[:20]:
                    structure += f"{'📁' if item.is_dir() else '📄'} {item.name}\n"
                return structure
        except:
            return "Structure analysis failed"
    
    def _analyze_files(self, path: Path) -> str:
        """Analyze file types and counts"""
        try:
            extensions = {}
            total_files = 0
            
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    total_files += 1
                    ext = file_path.suffix.lower()
                    extensions[ext] = extensions.get(ext, 0) + 1
            
            result = f"File analysis (total: {total_files} files):\n"
            for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10]:
                ext_name = ext if ext else "no extension"
                result += f"  {ext_name}: {count} files\n"
            
            return result
        except Exception as e:
            return f"File analysis error: {e}"
    
    def _analyze_git(self, path: Path) -> str:
        """Analyze git repository information"""
        try:
            os.chdir(path)
            
            # Check if it's a git repo
            result = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return "Not a git repository"
            
            # Get basic git info
            info = "Git repository information:\n"
            
            # Current branch
            branch_result = subprocess.run(['git', 'branch', '--show-current'], 
                                         capture_output=True, text=True, timeout=10)
            if branch_result.returncode == 0:
                info += f"Current branch: {branch_result.stdout.strip()}\n"
            
            # Commit count
            count_result = subprocess.run(['git', 'rev-list', '--count', 'HEAD'], 
                                        capture_output=True, text=True, timeout=10)
            if count_result.returncode == 0:
                info += f"Total commits: {count_result.stdout.strip()}\n"
            
            # Last commit
            log_result = subprocess.run(['git', 'log', '-1', '--oneline'], 
                                      capture_output=True, text=True, timeout=10)
            if log_result.returncode == 0:
                info += f"Last commit: {log_result.stdout.strip()}\n"
            
            return info
            
        except Exception as e:
            return f"Git analysis error: {e}"

    async def _arun(self, path: str = ".", analysis_type: str = "structure") -> str:
        return self._run(path, analysis_type)

class LangchainDependencyAnalysisTool(LangchainBaseTool):
    name: str = "analyze_dependencies"
    description: str = "Analyze project dependencies from manifest files"
    args_schema: Type[BaseModel] = DependencyAnalysisSchema

    def _run(self, path: str = ".") -> str:
        logger.info(f"Dependency Analysis: path='{path}'")
        try:
            project_path = Path(path).resolve()
            if not project_path.exists():
                return f"Path does not exist: {path}"
            
            dependencies = {}
            
            # Check for different dependency files
            if (project_path / 'package.json').exists():
                dependencies.update(self._analyze_npm(project_path))
            if (project_path / 'requirements.txt').exists():
                dependencies.update(self._analyze_python(project_path))
            if (project_path / 'pubspec.yaml').exists():
                dependencies.update(self._analyze_flutter(project_path))
            if (project_path / 'Cargo.toml').exists():
                dependencies.update(self._analyze_rust(project_path))
            
            if not dependencies:
                return "No dependency files found"
            
            result = "Project dependencies:\n\n"
            for ecosystem, deps in dependencies.items():
                result += f"**{ecosystem}** ({len(deps)} dependencies):\n"
                for dep in deps[:10]:  # Limit to first 10
                    result += f"  - {dep}\n"
                if len(deps) > 10:
                    result += f"  ... and {len(deps) - 10} more\n"
                result += "\n"
            
            return result
            
        except Exception as e:
            return f"Dependency analysis error: {str(e)}"
    
    def _analyze_npm(self, path: Path) -> dict:
        """Analyze package.json dependencies"""
        try:
            import json
            with open(path / 'package.json', 'r') as f:
                data = json.load(f)
            
            deps = []
            for dep_type in ['dependencies', 'devDependencies']:
                if dep_type in data:
                    for name, version in data[dep_type].items():
                        deps.append(f"{name}: {version}")
            
            return {"Node.js": deps}
        except:
            return {}
    
    def _analyze_python(self, path: Path) -> dict:
        """Analyze requirements.txt"""
        try:
            with open(path / 'requirements.txt', 'r') as f:
                deps = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            return {"Python": deps}
        except:
            return {}
    
    def _analyze_flutter(self, path: Path) -> dict:
        """Analyze pubspec.yaml"""
        try:
            import yaml
            with open(path / 'pubspec.yaml', 'r') as f:
                data = yaml.safe_load(f)
            
            deps = []
            for dep_type in ['dependencies', 'dev_dependencies']:
                if dep_type in data:
                    for name, version in data[dep_type].items():
                        deps.append(f"{name}: {version}")
            
            return {"Flutter/Dart": deps}
        except:
            return {}
    
    def _analyze_rust(self, path: Path) -> dict:
        """Analyze Cargo.toml"""
        return {"Rust": ["Cargo.toml analysis not implemented"]}

    async def _arun(self, path: str = ".") -> str:
        return self._run(path)

class LangchainCodeMetricsTool(LangchainBaseTool):
    name: str = "get_code_metrics"
    description: str = "Calculate code metrics and statistics"
    args_schema: Type[BaseModel] = CodeMetricsSchema

    def _run(self, path: str = ".") -> str:
        logger.info(f"Code Metrics: path='{path}'")
        try:
            project_path = Path(path).resolve()
            if not project_path.exists():
                return f"Path does not exist: {path}"
            
            # Try using cloc if available
            try:
                result = subprocess.run(['cloc', str(project_path)], 
                                      capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    return f"Code metrics (cloc):\n{result.stdout}"
            except FileNotFoundError:
                pass
            
            # Fallback to basic analysis
            metrics = self._basic_metrics(project_path)
            return f"Basic code metrics:\n{metrics}"
            
        except Exception as e:
            return f"Code metrics error: {str(e)}"
    
    def _basic_metrics(self, path: Path) -> str:
        """Basic file and line counting"""
        total_files = 0
        total_lines = 0
        code_files = 0
        
        code_extensions = {'.py', '.js', '.dart', '.java', '.cpp', '.c', '.rs', '.go'}
        
        for file_path in path.rglob('*'):
            if file_path.is_file():
                total_files += 1
                
                if file_path.suffix.lower() in code_extensions:
                    code_files += 1
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = len(f.readlines())
                            total_lines += lines
                    except:
                        pass
        
        return f"""Total files: {total_files}
Code files: {code_files}
Total lines: {total_lines}
Average lines per code file: {total_lines // max(code_files, 1)}"""

    async def _arun(self, path: str = ".") -> str:
        return self._run(path)