#!/usr/bin/env python3
"""
Development Tools - Build Commands and Package Search
====================================================

This module contains development workflow tools as per mcp_engineering_plan.md:
- BuildCommandTool (from build.py)
- PackageSearchTool (from package.py)
"""

import subprocess
import os
import json
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Type, Optional, Dict, Any
from pydantic import BaseModel, Field

from .base import AsyncTool

logger = logging.getLogger(__name__)

# ===== SCHEMAS =====

class BuildCommandSchema(BaseModel):
    command: str = Field(description="Build command: 'build', 'test', 'run', 'clean', 'install', 'detect'")
    directory: str = Field(description="Project directory", default=".")
    options: Optional[str] = Field(description="Additional command options", default=None)

class PackageSearchSchema(BaseModel):
    ecosystem: str = Field(description="Package ecosystem: 'npm', 'pypi', 'pub', 'crates', 'maven', 'rubygems'")
    query: str = Field(description="Package search query")
    max_results: int = Field(description="Maximum number of results", default=5)

class DateTimeSchema(BaseModel):
    pass  # No parameters needed

class SystemFileReaderSchema(BaseModel):
    file_path: str = Field(description="Absolute Linux path to any file on the system (e.g., /opt/mcp/rag/main_rag.db, /home/user/Documents/file.txt, /var/log/syslog, /etc/config.conf)")
    encoding: str = Field(description="File encoding for text files", default="utf-8")
    max_lines: int = Field(description="Maximum number of lines to read (0 for all)", default=1000)

# Known-sensitive system locations with no legitimate reason to be read as a
# project/log/data file (credentials, shadow passwords, kernel internals).
SENSITIVE_PATH_PREFIXES = [
    "/etc", "/root", "/proc", "/sys", "/boot", "/var/lib",
    str(Path.home() / ".ssh"), str(Path.home() / ".aws"),
    str(Path.home() / ".gnupg"), str(Path.home() / ".config"),
]

def _is_path_safe(path: str) -> bool:
    """Reject paths that fall under known-sensitive system locations."""
    resolved = str(Path(path).resolve())
    return not any(
        resolved == prefix or resolved.startswith(prefix + os.sep)
        for prefix in SENSITIVE_PATH_PREFIXES
    )

# ===== TOOL CLASSES =====

class LangchainBuildCommandTool(AsyncTool):
    name: str = "build_command"
    description: str = "Execute build commands for various project types (Flutter, Node.js, Python, Rust, Go, Maven, Gradle). Supports build, test, run, clean, and install operations."
    args_schema: Type[BaseModel] = BuildCommandSchema

    def _run(self, command: str, directory: str = ".", options: Optional[str] = None) -> str:
        logger.info(f"Build Command Tool: command='{command}', directory='{directory}', options='{options}'")
        
        try:
            project_path = Path(directory).resolve()
            if not _is_path_safe(directory):
                return f"Access denied: '{directory}' is a restricted system location."
            if not project_path.exists():
                return f"Directory does not exist: {directory}"

            if command == "detect":
                return self._detect_project_type(project_path)
            
            # Detect project type
            project_type = self._get_project_type(project_path)
            if not project_type:
                return "Could not detect project type. Supported: Flutter, Node.js, Python, Rust, Go, Maven, Gradle"
            
            # Execute command based on project type
            return self._execute_build_command(project_path, project_type, command, options)
            
        except Exception as e:
            logger.error(f"Build Command Tool error: {e}")
            return f"Build command error: {str(e)}"

    def _detect_project_type(self, project_path: Path) -> str:
        """Detect and report project type"""
        result = f"**Project Type Detection** for: {project_path.name}\n\n"
        
        project_types = []
        
        if (project_path / "pubspec.yaml").exists():
            project_types.append("Flutter/Dart")
        
        if (project_path / "package.json").exists():
            project_types.append("Node.js/JavaScript")
        
        if (project_path / "requirements.txt").exists() or (project_path / "pyproject.toml").exists():
            project_types.append("Python")
        
        if (project_path / "Cargo.toml").exists():
            project_types.append("Rust")
        
        if (project_path / "go.mod").exists():
            project_types.append("Go")
        
        if (project_path / "pom.xml").exists():
            project_types.append("Maven (Java)")
        
        if (project_path / "build.gradle").exists() or (project_path / "build.gradle.kts").exists():
            project_types.append("Gradle (Java/Kotlin)")
        
        if project_types:
            result += "**Detected Project Types**:\n"
            for ptype in project_types:
                result += f"  • {ptype}\n"
            
            result += "\n**Available Commands**: build, test, run, clean, install"
        else:
            result += "**No recognized project types found**\n"
            result += "Supported: Flutter, Node.js, Python, Rust, Go, Maven, Gradle"
        
        return result

    def _get_project_type(self, project_path: Path) -> Optional[str]:
        """Get primary project type"""
        if (project_path / "pubspec.yaml").exists():
            return "flutter"
        elif (project_path / "package.json").exists():
            return "nodejs"
        elif (project_path / "Cargo.toml").exists():
            return "rust"
        elif (project_path / "go.mod").exists():
            return "go"
        elif (project_path / "pom.xml").exists():
            return "maven"
        elif (project_path / "build.gradle").exists() or (project_path / "build.gradle.kts").exists():
            return "gradle"
        elif (project_path / "requirements.txt").exists() or (project_path / "pyproject.toml").exists():
            return "python"
        return None

    def _execute_build_command(self, project_path: Path, project_type: str, command: str, options: Optional[str]) -> str:
        """Execute build command for specific project type"""
        try:
            cmd_map = {
                "flutter": {
                    "build": ["flutter", "build", "apk"],
                    "test": ["flutter", "test"],
                    "run": ["flutter", "run"],
                    "clean": ["flutter", "clean"],
                    "install": ["flutter", "pub", "get"]
                },
                "nodejs": {
                    "build": ["npm", "run", "build"],
                    "test": ["npm", "test"],
                    "run": ["npm", "start"],
                    "clean": ["npm", "run", "clean"],
                    "install": ["npm", "install"]
                },
                "rust": {
                    "build": ["cargo", "build"],
                    "test": ["cargo", "test"],
                    "run": ["cargo", "run"],
                    "clean": ["cargo", "clean"],
                    "install": ["cargo", "build"]
                },
                "go": {
                    "build": ["go", "build"],
                    "test": ["go", "test", "./..."],
                    "run": ["go", "run", "."],
                    "clean": ["go", "clean"],
                    "install": ["go", "mod", "download"]
                },
                "maven": {
                    "build": ["mvn", "compile"],
                    "test": ["mvn", "test"],
                    "run": ["mvn", "exec:java"],
                    "clean": ["mvn", "clean"],
                    "install": ["mvn", "install"]
                },
                "gradle": {
                    "build": ["./gradlew", "build"],
                    "test": ["./gradlew", "test"],
                    "run": ["./gradlew", "run"],
                    "clean": ["./gradlew", "clean"],
                    "install": ["./gradlew", "dependencies"]
                },
                "python": {
                    "build": ["python", "setup.py", "build"],
                    "test": ["python", "-m", "pytest"],
                    "run": ["python", "main.py"],
                    "clean": ["find", ".", "-name", "*.pyc", "-delete"],
                    "install": ["pip", "install", "-r", "requirements.txt"]
                }
            }
            
            if project_type not in cmd_map:
                return f"Unsupported project type: {project_type}"
            
            if command not in cmd_map[project_type]:
                available = ", ".join(cmd_map[project_type].keys())
                return f"Command '{command}' not available for {project_type}. Available: {available}"
            
            # Get base command
            cmd = cmd_map[project_type][command].copy()
            
            # Add options if provided
            if options:
                cmd.extend(options.split())
            
            # Special handling for certain commands
            if project_type == "flutter" and command == "build":
                # Default to APK, but allow override
                if not options:
                    cmd = ["flutter", "build", "apk"]
            elif project_type == "python" and command == "run":
                # Try to find main entry point
                main_files = ["main.py", "app.py", "run.py"]
                entry_point = None
                for main_file in main_files:
                    if (project_path / main_file).exists():
                        entry_point = main_file
                        break
                if entry_point:
                    cmd = ["python", entry_point]
                else:
                    return "No main entry point found (main.py, app.py, run.py)"
            
            # Execute command
            logger.info(f"Executing: {' '.join(cmd)} in {project_path}")
            
            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Format response
            response = f"**{project_type.title()} {command.title()} Command**\n\n"
            response += f"Command: `{' '.join(cmd)}`\n"
            response += f"Exit Code: {result.returncode}\n\n"
            
            if result.stdout:
                response += f"**Output**:\n```\n{result.stdout}\n```\n\n"
            
            if result.stderr:
                response += f"**Errors**:\n```\n{result.stderr}\n```\n\n"
            
            if result.returncode == 0:
                response += f"✅ **Status**: Command completed successfully"
            else:
                response += f"❌ **Status**: Command failed with exit code {result.returncode}"
            
            return response
            
        except subprocess.TimeoutExpired:
            return f"❌ **Timeout**: {command} command timed out after 5 minutes"
        except FileNotFoundError as e:
            return f"❌ **Tool Not Found**: {e}. Make sure required tools are installed and in PATH."
        except Exception as e:
            return f"❌ **Error**: {str(e)}"

class LangchainPackageSearchTool(AsyncTool):
    name: str = "search_packages"
    description: str = "Search for packages/libraries across different ecosystems (npm, PyPI, pub.dev, crates.io, etc.)"
    args_schema: Type[BaseModel] = PackageSearchSchema

    def _run(self, ecosystem: str, query: str, max_results: int = 5) -> str:
        logger.info(f"Package Search: ecosystem='{ecosystem}', query='{query}', max_results={max_results}")
        
        try:
            ecosystem = ecosystem.lower()
            max_results = min(max_results, 10)  # Limit to 10 results max
            
            if ecosystem == "npm":
                return self._search_npm(query, max_results)
            elif ecosystem == "pypi":
                return self._search_pypi(query, max_results)
            elif ecosystem == "pub":
                return self._search_pub(query, max_results)
            elif ecosystem == "crates":
                return self._search_crates(query, max_results)
            elif ecosystem == "maven":
                return self._search_maven(query, max_results)
            elif ecosystem == "rubygems":
                return self._search_rubygems(query, max_results)
            else:
                return f"Unsupported ecosystem: {ecosystem}. Supported: npm, pypi, pub, crates, maven, rubygems"
                
        except Exception as e:
            logger.error(f"Package Search error: {e}")
            return f"Package search error: {str(e)}"

    def _search_npm(self, query: str, max_results: int) -> str:
        """Search npm packages"""
        try:
            url = f"https://registry.npmjs.org/-/v1/search"
            params = {"text": query, "size": max_results}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            packages = data.get("objects", [])
            
            if not packages:
                return f"No npm packages found for '{query}'"
            
            result = f"**npm Packages** for '{query}':\n\n"
            
            for i, pkg_obj in enumerate(packages, 1):
                pkg = pkg_obj.get("package", {})
                name = pkg.get("name", "Unknown")
                version = pkg.get("version", "Unknown")
                description = pkg.get("description", "No description")
                
                # Truncate long descriptions
                if len(description) > 100:
                    description = description[:100] + "..."
                
                result += f"{i}. **{name}** (v{version})\n"
                result += f"   {description}\n"
                result += f"   Install: `npm install {name}`\n\n"
            
            return result
            
        except requests.RequestException as e:
            return f"npm search failed: {e}"
        except Exception as e:
            return f"npm search error: {e}"

    def _search_pypi(self, query: str, max_results: int) -> str:
        """Search PyPI packages"""
        try:
            url = f"https://pypi.org/pypi/{query}/json"
            
            # Try exact match first
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    info = data.get("info", {})
                    
                    result = f"**PyPI Package** '{query}':\n\n"
                    result += f"**{info.get('name', query)}** (v{info.get('version', 'Unknown')})\n"
                    result += f"{info.get('summary', 'No description')}\n"
                    result += f"Install: `pip install {info.get('name', query)}`\n"
                    result += f"Homepage: {info.get('home_page', 'N/A')}\n"
                    
                    return result
            except:
                pass
            
            # Fallback to search API (if available) or suggest alternatives
            return f"PyPI package '{query}' not found. Try searching on https://pypi.org/search/?q={query}"
            
        except Exception as e:
            return f"PyPI search error: {e}"

    def _search_pub(self, query: str, max_results: int) -> str:
        """Search pub.dev packages"""
        try:
            url = f"https://pub.dev/api/search"
            params = {"q": query, "size": max_results}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            packages = data.get("packages", [])
            
            if not packages:
                return f"No pub.dev packages found for '{query}'"
            
            result = f"**pub.dev Packages** for '{query}':\n\n"
            
            for i, pkg in enumerate(packages, 1):
                name = pkg.get("package", "Unknown")
                version = pkg.get("latest", {}).get("version", "Unknown")
                description = pkg.get("latest", {}).get("pubspec", {}).get("description", "No description")
                
                # Truncate long descriptions
                if len(description) > 100:
                    description = description[:100] + "..."
                
                result += f"{i}. **{name}** (v{version})\n"
                result += f"   {description}\n"
                result += f"   Install: Add `{name}: ^{version}` to pubspec.yaml\n\n"
            
            return result
            
        except requests.RequestException as e:
            return f"pub.dev search failed: {e}"
        except Exception as e:
            return f"pub.dev search error: {e}"

    def _search_crates(self, query: str, max_results: int) -> str:
        """Search crates.io packages"""
        try:
            url = f"https://crates.io/api/v1/crates"
            params = {"q": query, "per_page": max_results}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            crates = data.get("crates", [])
            
            if not crates:
                return f"No crates found for '{query}'"
            
            result = f"**crates.io Packages** for '{query}':\n\n"
            
            for i, crate in enumerate(crates, 1):
                name = crate.get("name", "Unknown")
                version = crate.get("max_version", "Unknown")
                description = crate.get("description", "No description")
                
                # Truncate long descriptions
                if len(description) > 100:
                    description = description[:100] + "..."
                
                result += f"{i}. **{name}** (v{version})\n"
                result += f"   {description}\n"
                result += f"   Install: Add `{name} = \"{version}\"` to Cargo.toml\n\n"
            
            return result
            
        except requests.RequestException as e:
            return f"crates.io search failed: {e}"
        except Exception as e:
            return f"crates.io search error: {e}"

    def _search_maven(self, query: str, max_results: int) -> str:
        """Search Maven Central packages"""
        try:
            url = f"https://search.maven.org/solrsearch/select"
            params = {
                "q": query,
                "rows": max_results,
                "wt": "json"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            docs = data.get("response", {}).get("docs", [])
            
            if not docs:
                return f"No Maven packages found for '{query}'"
            
            result = f"**Maven Central Packages** for '{query}':\n\n"
            
            for i, doc in enumerate(docs, 1):
                group_id = doc.get("g", "Unknown")
                artifact_id = doc.get("a", "Unknown")
                version = doc.get("latestVersion", "Unknown")
                
                result += f"{i}. **{group_id}:{artifact_id}** (v{version})\n"
                result += f"   Install: Add to pom.xml dependencies:\n"
                result += f"   ```xml\n"
                result += f"   <dependency>\n"
                result += f"     <groupId>{group_id}</groupId>\n"
                result += f"     <artifactId>{artifact_id}</artifactId>\n"
                result += f"     <version>{version}</version>\n"
                result += f"   </dependency>\n"
                result += f"   ```\n\n"
            
            return result
            
        except requests.RequestException as e:
            return f"Maven search failed: {e}"
        except Exception as e:
            return f"Maven search error: {e}"

    def _search_rubygems(self, query: str, max_results: int) -> str:
        """Search RubyGems packages"""
        try:
            url = f"https://rubygems.org/api/v1/search.json"
            params = {"query": query}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            gems = response.json()
            
            if not gems:
                return f"No RubyGems found for '{query}'"
            
            # Limit results
            gems = gems[:max_results]
            
            result = f"**RubyGems** for '{query}':\n\n"
            
            for i, gem in enumerate(gems, 1):
                name = gem.get("name", "Unknown")
                version = gem.get("version", "Unknown")
                info = gem.get("info", "No description")
                
                # Truncate long descriptions
                if len(info) > 100:
                    info = info[:100] + "..."
                
                result += f"{i}. **{name}** (v{version})\n"
                result += f"   {info}\n"
                result += f"   Install: `gem install {name}`\n\n"
            
            return result
            
        except requests.RequestException as e:
            return f"RubyGems search failed: {e}"
        except Exception as e:
            return f"RubyGems search error: {e}"


class LangchainDateTimeTool(AsyncTool):
    name: str = "get_current_datetime"
    description: str = "Get the current date and time information. Use this when user asks about today's date, current time, what day it is, etc."
    args_schema: Type[BaseModel] = DateTimeSchema

    def _run(self) -> str:
        logger.info("DateTime Tool called")
        try:
            now = datetime.now()
            
            # Format comprehensive date/time information
            result = f"**Current Date & Time Information:**\n\n"
            result += f"📅 **Date**: {now.strftime('%A, %B %d, %Y')}\n"
            result += f"🕐 **Time**: {now.strftime('%I:%M:%S %p')}\n"
            result += f"🌍 **Full DateTime**: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            result += f"📆 **Day of Week**: {now.strftime('%A')}\n"
            result += f"📅 **Month**: {now.strftime('%B')}\n"
            result += f"🗓️ **Year**: {now.year}\n"
            result += f"⭐ **Day of Year**: Day {now.timetuple().tm_yday} of {now.year}\n"
            
            return result
            
        except Exception as e:
            logger.error(f"DateTime Tool error: {e}")
            return f"Error getting current date/time: {str(e)}"


class LangchainSystemFileReaderTool(AsyncTool):
    name: str = "read_system_file"
    description: str = "Read any file from anywhere on the Ubuntu Linux system. Can access files outside project directory including /opt, /home, /var, /etc, mounted drives, etc. Handles both text and binary files intelligently."
    args_schema: Type[BaseModel] = SystemFileReaderSchema

    def _run(self, file_path: str, encoding: str = "utf-8", max_lines: int = 1000) -> str:
        logger.info(f"System File Reader: Accessing '{file_path}'")
        
        try:
            if not _is_path_safe(file_path):
                return f"❌ Access denied: '{file_path}' is a restricted system location."

            # Validate path exists
            if not os.path.exists(file_path):
                return f"❌ File not found: {file_path}"
            
            # Check if it's a directory
            if os.path.isdir(file_path):
                return f"❌ Path is a directory, not a file: {file_path}"
            
            # Get file info
            file_stat = os.stat(file_path)
            file_size_mb = file_stat.st_size / (1024 * 1024)
            
            logger.info(f"File size: {file_size_mb:.2f} MB")
            
            # Handle different file types
            file_ext = Path(file_path).suffix.lower()
            
            # Database files
            if file_ext in ['.db', '.sqlite', '.sqlite3']:
                return self._handle_database_file(file_path)
            
            # Binary files that should be described, not read
            elif file_ext in ['.bin', '.exe', '.so', '.img', '.iso']:
                return self._handle_binary_file(file_path, file_stat)
            
            # Text-based files
            else:
                return self._handle_text_file(file_path, encoding, max_lines, file_stat)
                
        except PermissionError:
            return f"❌ Permission denied accessing: {file_path}"
        except Exception as e:
            logger.error(f"System File Reader error: {e}")
            return f"❌ Error reading {file_path}: {str(e)}"
    
    def _handle_database_file(self, file_path: str) -> str:
        """Handle SQLite database files"""
        try:
            import sqlite3
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Get table list
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            result = f"📊 **SQLite Database**: {file_path}\n\n"
            result += f"**Tables ({len(tables)}):**\n"
            
            for table_name, in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                result += f"  • {table_name}: {count} rows\n"
            
            # Get schema for first few tables
            result += f"\n**Schema Sample:**\n"
            for table_name, in tables[:3]:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                result += f"\n**{table_name}:**\n"
                for col in columns:
                    result += f"  - {col[1]} ({col[2]})\n"
            
            conn.close()
            return result
            
        except Exception as e:
            return f"❌ Error reading database: {str(e)}"
    
    def _handle_binary_file(self, file_path: str, file_stat) -> str:
        """Handle binary files"""
        from datetime import datetime
        
        size_mb = file_stat.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(file_stat.st_mtime)
        
        return f"🔧 **Binary File**: {file_path}\n" \
               f"📦 Size: {size_mb:.2f} MB\n" \
               f"📅 Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}\n" \
               f"ℹ️  Use appropriate binary tools to examine contents."
    
    def _handle_text_file(self, file_path: str, encoding: str, max_lines: int, file_stat) -> str:
        """Handle text files"""
        from datetime import datetime
        
        size_mb = file_stat.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(file_stat.st_mtime)
        
        # Read file content
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            if max_lines == 0:
                content = f.read()
                lines_read = len(content.splitlines())
            else:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.rstrip())
                content = '\n'.join(lines)
                lines_read = len(lines)
        
        result = f"📄 **File**: {file_path}\n"
        result += f"📦 Size: {size_mb:.2f} MB\n"
        result += f"📅 Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}\n"
        result += f"📋 Lines: {lines_read}" + (f" (limited from file)" if max_lines > 0 and lines_read >= max_lines else "") + "\n\n"
        result += f"**Content:**\n```\n{content}\n```"
        
        return result