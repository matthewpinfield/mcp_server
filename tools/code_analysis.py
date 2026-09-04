#!/usr/bin/env python3
"""
Code Analysis Tools - Combined Static Analysis Suite
===================================================

This module contains all code analysis tools as per mcp_engineering_plan.md:
- AutoLinterTool (from linter.py)
- RepoExploreTool (from repo.py) 
- DependencyAnalysisTool (from repo.py)
- CodeMetricsTool (from repo.py)
"""

import subprocess
import os
import json
import logging
from pathlib import Path
from typing import Type, Optional, List
from pydantic import BaseModel, Field

from .base import AsyncTool

logger = logging.getLogger(__name__)

# ===== SCHEMAS =====

class AutoLinterSchema(BaseModel):
    directory: str = Field(description="Directory to analyze (default: current directory)", default=".")
    action: str = Field(description="Action: 'analyze', 'fix', 'format', 'suggest', 'check'", default="analyze")
    language: Optional[str] = Field(description="Language: 'flutter', 'javascript', 'python', 'rust', 'go', 'java' (auto-detected if not specified)", default=None)
    auto_fix: bool = Field(description="Automatically apply fixes where possible", default=False)

class RepoExploreSchema(BaseModel):
    path: str = Field(description="Repository path", default=".")
    analysis_type: str = Field(description="Analysis type: 'structure', 'files', 'git'", default="structure")

class DependencyAnalysisSchema(BaseModel):
    path: str = Field(description="Project path", default=".")

class CodeMetricsSchema(BaseModel):
    path: str = Field(description="Project path", default=".")

# ===== HELPER FUNCTIONS =====

# These tools are meant to analyze arbitrary codebases the user points them at
# (e.g. via Continue IDE), so we don't restrict to a single project root.
# Instead, block known-sensitive system locations that have no legitimate
# reason to be "analyzed" as a codebase.
SENSITIVE_PATH_PREFIXES = [
    "/etc", "/root", "/proc", "/sys", "/boot", "/var/lib",
    str(Path.home() / ".ssh"), str(Path.home() / ".aws"),
    str(Path.home() / ".gnupg"), str(Path.home() / ".config"),
]

def _is_path_safe(path: Path) -> bool:
    """Reject paths that fall under known-sensitive system locations."""
    resolved = str(path.resolve())
    return not any(
        resolved == prefix or resolved.startswith(prefix + os.sep)
        for prefix in SENSITIVE_PATH_PREFIXES
    )

def _load_gitignore_patterns(repo_path: Path) -> List[str]:
    """Load gitignore patterns from .gitignore file"""
    gitignore_path = repo_path / ".gitignore"
    patterns = []
    if gitignore_path.exists():
        try:
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line)
        except Exception as e:
            logger.warning(f"Could not read .gitignore: {e}")
    return patterns

def _matches_gitignore_pattern(file_path: str, pattern: str) -> bool:
    """Check if a file path matches a gitignore pattern"""
    import fnmatch
    if pattern.endswith('/'):
        return fnmatch.fnmatch(file_path + '/', pattern)
    return fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(os.path.basename(file_path), pattern)

def _is_ignored_by_gitignore(file_path: Path, repo_path: Path, gitignore_patterns: List[str]) -> bool:
    """Check if a file should be ignored based on gitignore patterns"""
    try:
        rel_path = file_path.relative_to(repo_path)
        rel_path_str = str(rel_path).replace('\\', '/')
        
        for pattern in gitignore_patterns:
            if _matches_gitignore_pattern(rel_path_str, pattern):
                return True
        return False
    except ValueError:
        return False

# ===== TOOL CLASSES =====

class LangchainAutoLinterTool(AsyncTool):
    name: str = "auto_linter"
    description: str = "Automatically detects language and runs appropriate linting/formatting tools (Flutter, JavaScript, Python, Rust, Go, Java). Can analyze, fix formatting issues, or provide suggestions."
    args_schema: Type[BaseModel] = AutoLinterSchema

    def _run(self, directory: str = ".", action: str = "analyze", language: Optional[str] = None, auto_fix: bool = False) -> str:
        logger.info(f"Auto-Linter Tool: dir='{directory}', action='{action}', language='{language}', auto_fix={auto_fix}")
        
        try:
            path = Path(directory).resolve()
            if not _is_path_safe(path):
                return f"Access denied: '{directory}' is a restricted system location."
            if not path.exists():
                return f"Directory does not exist: {directory}"

            # Auto-detect language if not specified
            if not language:
                language = self._detect_language(path)
            
            if not language:
                return "Could not detect project language. Specify manually with language parameter."
            
            logger.info(f"Detected/using language: {language}")
            
            # Run language-specific analysis
            if language == "flutter":
                return self._flutter_analysis(path, action, auto_fix)
            elif language == "javascript":
                return self._javascript_analysis(path, action, auto_fix)
            elif language == "python":
                return self._python_analysis(path, action, auto_fix)
            elif language == "rust":
                return self._rust_analysis(path, action, auto_fix)
            elif language == "go":
                return self._go_analysis(path, action, auto_fix)
            elif language == "java":
                return self._java_analysis(path, action, auto_fix)
            else:
                return f"Unsupported language: {language}"
                
        except Exception as e:
            logger.error(f"Auto-Linter Tool error: {e}")
            return f"Linter error: {str(e)}"

    def _detect_language(self, path: Path) -> Optional[str]:
        """Auto-detect project language based on files"""
        if (path / "pubspec.yaml").exists():
            return "flutter"
        elif (path / "package.json").exists():
            return "javascript"
        elif (path / "requirements.txt").exists() or (path / "pyproject.toml").exists() or any(path.glob("*.py")):
            return "python"
        elif (path / "Cargo.toml").exists():
            return "rust"
        elif (path / "go.mod").exists():
            return "go"
        elif (path / "pom.xml").exists() or any(path.glob("*.java")):
            return "java"
        return None

    def _flutter_analysis(self, path: Path, action: str, auto_fix: bool) -> List[str]:
        """Flutter/Dart analysis"""
        results = []
        try:
            if action in ["analyze", "check"]:
                result = subprocess.run(
                    ["flutter", "analyze"], 
                    cwd=path, 
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                if result.returncode == 0:
                    results.append("**Flutter Analyze**: No issues found")
                else:
                    results.append(f"**Flutter Analyze Issues**:\n{result.stdout}")
            
            if action in ["format", "fix"] or auto_fix:
                result = subprocess.run(
                    ["dart", "format", "."], 
                    cwd=path, 
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                if result.returncode == 0:
                    results.append("**Dart Format**: Code formatted successfully")
                else:
                    results.append(f"**Dart Format Error**: {result.stderr}")
                    
        except subprocess.TimeoutExpired:
            results.append("**Flutter Analysis**: Timed out")
        except FileNotFoundError:
            results.append("**Flutter**: Flutter/Dart not found in PATH")
        except Exception as e:
            results.append(f"**Flutter Analysis Error**: {e}")
        
        return "\n".join(results)

    def _javascript_analysis(self, path: Path, action: str, auto_fix: bool) -> str:
        """JavaScript/Node.js analysis"""
        results = []
        try:
            # Check for ESLint
            if (path / "node_modules" / ".bin" / "eslint").exists() or (path / ".eslintrc.js").exists():
                if action in ["analyze", "check"]:
                    result = subprocess.run(
                        ["npx", "eslint", ".", "--format", "compact"],
                        cwd=path,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.returncode == 0:
                        results.append("**ESLint**: No issues found")
                    else:
                        results.append(f"**ESLint Issues**:\n{result.stdout}")
                
                if action in ["fix"] or auto_fix:
                    result = subprocess.run(
                        ["npx", "eslint", ".", "--fix"],
                        cwd=path,
                        capture_output=True, 
                        text=True,
                        timeout=60
                    )
                    results.append("**ESLint**: Auto-fix attempted")
            
            # Check for Prettier
            if (path / "node_modules" / ".bin" / "prettier").exists():
                if action in ["format"] or auto_fix:
                    result = subprocess.run(
                        ["npx", "prettier", "--write", "."],
                        cwd=path,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    results.append("**Prettier**: Code formatted")
                    
        except subprocess.TimeoutExpired:
            results.append("**JavaScript Analysis**: Timed out")
        except Exception as e:
            results.append(f"**JavaScript Analysis Error**: {e}")
        
        return "\n".join(results) if results else "**JavaScript**: No linting tools found (ESLint, Prettier)"

    def _python_analysis(self, path: Path, action: str, auto_fix: bool) -> str:
        """Python analysis"""
        results = []
        try:
            # Try different Python linters
            linters = [
                (["flake8", "."], "Flake8"),
                (["pylint", "."], "Pylint"),
                (["black", "--check", "."], "Black (format check)")
            ]
            
            for cmd, name in linters:
                try:
                    result = subprocess.run(
                        cmd, 
                        cwd=path, 
                        capture_output=True, 
                        text=True, 
                        timeout=60
                    )
                    if result.returncode == 0:
                        results.append(f"**{name}**: No issues found")
                    else:
                        results.append(f"**{name}**: Issues found\n{result.stdout}")
                    break  # Use first available linter
                except FileNotFoundError:
                    continue
            
            if auto_fix or action == "format":
                # Try Black formatting
                try:
                    result = subprocess.run(
                        ["black", "."], 
                        cwd=path, 
                        capture_output=True, 
                        text=True, 
                        timeout=60
                    )
                    results.append("**Black**: Code formatted")
                except FileNotFoundError:
                    results.append("**Black**: Not available for formatting")
                    
        except Exception as e:
            results.append(f"**Python Analysis Error**: {e}")
        
        return "\n".join(results) if results else "**Python**: No linting tools found"

    def _rust_analysis(self, path: Path, action: str, auto_fix: bool) -> str:
        """Rust analysis"""
        results = []
        try:
            if action in ["analyze", "check"]:
                result = subprocess.run(
                    ["cargo", "clippy"], 
                    cwd=path, 
                    capture_output=True, 
                    text=True, 
                    timeout=120
                )
                if result.returncode == 0:
                    results.append("**Cargo Clippy**: No issues found")
                else:
                    results.append(f"**Cargo Clippy Issues**:\n{result.stdout}")
            
            if auto_fix or action == "format":
                result = subprocess.run(
                    ["cargo", "fmt"], 
                    cwd=path, 
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                results.append("**Cargo Format**: Code formatted")
                
        except subprocess.TimeoutExpired:
            results.append("**Rust Analysis**: Timed out")
        except FileNotFoundError:
            results.append("**Rust**: Cargo not found in PATH")
        except Exception as e:
            results.append(f"**Rust Analysis Error**: {e}")
        
        return "\n".join(results)

    def _go_analysis(self, path: Path, action: str, auto_fix: bool) -> str:
        """Go analysis"""
        results = []
        try:
            if action in ["analyze", "check"]:
                result = subprocess.run(
                    ["go", "vet", "./..."], 
                    cwd=path, 
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                if result.returncode == 0:
                    results.append("**Go Vet**: No issues found")
                else:
                    results.append(f"**Go Vet Issues**:\n{result.stdout}")
            
            if auto_fix or action == "format":
                result = subprocess.run(
                    ["go", "fmt", "./..."], 
                    cwd=path, 
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                results.append("**Go Format**: Code formatted")
                
        except subprocess.TimeoutExpired:
            results.append("**Go Analysis**: Timed out")
        except FileNotFoundError:
            results.append("**Go**: Go not found in PATH")
        except Exception as e:
            results.append(f"**Go Analysis Error**: {e}")
        
        return "\n".join(results)

    def _java_analysis(self, path: Path, action: str, auto_fix: bool) -> str:
        """Java analysis"""
        results = []
        try:
            # Check for Maven
            if (path / "pom.xml").exists():
                if action in ["analyze", "check"]:
                    result = subprocess.run(
                        ["mvn", "compile"], 
                        cwd=path, 
                        capture_output=True, 
                        text=True, 
                        timeout=120
                    )
                    if result.returncode == 0:
                        results.append("**Maven Compile**: No compilation errors")
                    else:
                        results.append(f"**Maven Compile Issues**:\n{result.stdout}")
            
            # Check for Gradle
            elif (path / "build.gradle").exists():
                if action in ["analyze", "check"]:
                    result = subprocess.run(
                        ["./gradlew", "compileJava"], 
                        cwd=path, 
                        capture_output=True, 
                        text=True, 
                        timeout=120
                    )
                    if result.returncode == 0:
                        results.append("**Gradle Compile**: No compilation errors")
                    else:
                        results.append(f"**Gradle Compile Issues**:\n{result.stdout}")
                        
        except subprocess.TimeoutExpired:
            results.append("**Java Analysis**: Timed out")
        except Exception as e:
            results.append(f"**Java Analysis Error**: {e}")
        
        return "\n".join(results) if results else "**Java**: No build system found (Maven/Gradle)"

class LangchainRepoExploreTool(AsyncTool):
    name: str = "explore_repository"
    description: str = "Explore repository structure, analyze files, and get project information. Provides detailed insights into codebase organization and composition."
    args_schema: Type[BaseModel] = RepoExploreSchema

    def _run(self, path: str = ".", analysis_type: str = "structure") -> str:
        logger.info(f"Repository Explorer: path='{path}', analysis_type='{analysis_type}'")
        
        try:
            repo_path = Path(path).resolve()
            if not _is_path_safe(repo_path):
                return f"Access denied: '{path}' is a restricted system location."
            if not repo_path.exists():
                return f"Path does not exist: {path}"

            if analysis_type == "structure":
                return self._analyze_structure(repo_path)
            elif analysis_type == "files":
                return self._analyze_files(repo_path)
            elif analysis_type == "git":
                return self._analyze_git_info(repo_path)
            else:
                return f"Unknown analysis type: {analysis_type}. Use 'structure', 'files', or 'git'"
                
        except Exception as e:
            logger.error(f"Repository Explorer error: {e}")
            return f"Repository exploration error: {str(e)}"

    def _analyze_structure(self, repo_path: Path) -> str:
        """Analyze repository structure"""
        result = f"**Repository Structure Analysis**: {repo_path.name}\n\n"
        
        # Load gitignore patterns
        gitignore_patterns = _load_gitignore_patterns(repo_path)
        
        # Basic info
        total_files = 0
        total_dirs = 0
        file_types = {}
        
        # Walk through directory
        for root, dirs, files in os.walk(repo_path):
            root_path = Path(root)
            
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'build', 'dist']]
            
            total_dirs += len(dirs)
            
            for file in files:
                file_path = root_path / file
                
                # Check gitignore
                if _is_ignored_by_gitignore(file_path, repo_path, gitignore_patterns):
                    continue
                
                total_files += 1
                ext = file_path.suffix.lower()
                if ext:
                    file_types[ext] = file_types.get(ext, 0) + 1
        
        result += f"📁 **Directories**: {total_dirs}\n"
        result += f"📄 **Files**: {total_files}\n\n"
        
        # Top file types
        if file_types:
            result += "**File Types**:\n"
            sorted_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:10]
            for ext, count in sorted_types:
                result += f"  {ext}: {count} files\n"
        
        return result

    def _analyze_files(self, repo_path: Path) -> str:
        """Analyze file composition"""
        result = f"**File Analysis**: {repo_path.name}\n\n"
        
        # Language detection
        languages = {
            '.py': 'Python',
            '.js': 'JavaScript', 
            '.ts': 'TypeScript',
            '.dart': 'Dart',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.rs': 'Rust',
            '.go': 'Go',
            '.php': 'PHP',
            '.rb': 'Ruby'
        }
        
        lang_counts = {}
        large_files = []
        
        for file_path in repo_path.rglob('*'):
            if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                ext = file_path.suffix.lower()
                if ext in languages:
                    lang = languages[ext]
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1
                
                # Check file size
                try:
                    size = file_path.stat().st_size
                    if size > 100000:  # Files larger than 100KB
                        large_files.append((file_path.name, size // 1024))
                except:
                    pass
        
        if lang_counts:
            result += "**Programming Languages**:\n"
            for lang, count in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True):
                result += f"  {lang}: {count} files\n"
            result += "\n"
        
        if large_files:
            result += "**Large Files** (>100KB):\n"
            for name, size_kb in sorted(large_files, key=lambda x: x[1], reverse=True)[:10]:
                result += f"  {name}: {size_kb}KB\n"
        
        return result

    def _analyze_git_info(self, repo_path: Path) -> str:
        """Analyze Git repository information"""
        result = f"**Git Repository Analysis**: {repo_path.name}\n\n"
        
        try:
            # Check if it's a git repo
            git_dir = repo_path / '.git'
            if not git_dir.exists():
                return "Not a Git repository"
            
            # Get current branch
            try:
                result_cmd = subprocess.run(
                    ["git", "branch", "--show-current"], 
                    cwd=repo_path, 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result_cmd.returncode == 0:
                    result += f"**Current Branch**: {result_cmd.stdout.strip()}\n"
            except:
                pass
            
            # Get commit count
            try:
                result_cmd = subprocess.run(
                    ["git", "rev-list", "--count", "HEAD"], 
                    cwd=repo_path, 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result_cmd.returncode == 0:
                    result += f"**Total Commits**: {result_cmd.stdout.strip()}\n"
            except:
                pass
            
            # Get recent commits
            try:
                result_cmd = subprocess.run(
                    ["git", "log", "--oneline", "-5"], 
                    cwd=repo_path, 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                if result_cmd.returncode == 0:
                    result += f"\n**Recent Commits**:\n{result_cmd.stdout}"
            except:
                pass
                
        except Exception as e:
            result += f"Git analysis error: {e}"
        
        return result

class LangchainDependencyAnalysisTool(AsyncTool):
    name: str = "analyze_dependencies"
    description: str = "Analyze project dependencies and package management files. Supports multiple ecosystems (npm, pip, cargo, go mod, etc.)."
    args_schema: Type[BaseModel] = DependencyAnalysisSchema

    def _run(self, path: str = ".") -> str:
        logger.info(f"Dependency Analysis: path='{path}'")

        try:
            project_path = Path(path).resolve()
            if not _is_path_safe(project_path):
                return f"Access denied: '{path}' is a restricted system location."
            if not project_path.exists():
                return f"Path does not exist: {path}"

            results = []
            
            # Check different package managers
            if (project_path / "package.json").exists():
                results.append(self._analyze_npm(project_path))
            
            if (project_path / "requirements.txt").exists():
                results.append(self._analyze_pip(project_path))
            
            if (project_path / "Cargo.toml").exists():
                results.append(self._analyze_cargo(project_path))
            
            if (project_path / "go.mod").exists():
                results.append(self._analyze_go_mod(project_path))
            
            if (project_path / "pubspec.yaml").exists():
                results.append(self._analyze_pubspec(project_path))
            
            if not results:
                return "No recognized dependency files found"
            
            return "\n\n".join(results)
            
        except Exception as e:
            logger.error(f"Dependency Analysis error: {e}")
            return f"Dependency analysis error: {str(e)}"

    def _analyze_npm(self, project_path: Path) -> str:
        """Analyze package.json dependencies"""
        try:
            with open(project_path / "package.json", 'r') as f:
                package_data = json.load(f)
            
            result = "**npm Dependencies**:\n"
            
            deps = package_data.get('dependencies', {})
            dev_deps = package_data.get('devDependencies', {})
            
            result += f"  Production: {len(deps)} packages\n"
            result += f"  Development: {len(dev_deps)} packages\n"
            
            if deps:
                result += "\n  **Key Dependencies**:\n"
                for name, version in list(deps.items())[:10]:
                    result += f"    {name}: {version}\n"
            
            return result
        except Exception as e:
            return f"npm analysis error: {e}"

    def _analyze_pip(self, project_path: Path) -> str:
        """Analyze requirements.txt dependencies"""
        try:
            with open(project_path / "requirements.txt", 'r') as f:
                lines = f.readlines()
            
            deps = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
            
            result = f"**pip Dependencies**: {len(deps)} packages\n"
            
            if deps:
                result += "\n  **Requirements**:\n"
                for dep in deps[:10]:
                    result += f"    {dep}\n"
            
            return result
        except Exception as e:
            return f"pip analysis error: {e}"

    def _analyze_cargo(self, project_path: Path) -> str:
        """Analyze Cargo.toml dependencies"""
        try:
            import toml
            with open(project_path / "Cargo.toml", 'r') as f:
                cargo_data = toml.load(f)
            
            deps = cargo_data.get('dependencies', {})
            dev_deps = cargo_data.get('dev-dependencies', {})
            
            result = "**Cargo Dependencies**:\n"
            result += f"  Production: {len(deps)} crates\n"
            result += f"  Development: {len(dev_deps)} crates\n"
            
            if deps:
                result += "\n  **Key Dependencies**:\n"
                for name, version in list(deps.items())[:10]:
                    result += f"    {name}: {version}\n"
            
            return result
        except ImportError:
            return "Cargo analysis requires 'toml' package"
        except Exception as e:
            return f"Cargo analysis error: {e}"

    def _analyze_go_mod(self, project_path: Path) -> str:
        """Analyze go.mod dependencies"""
        try:
            with open(project_path / "go.mod", 'r') as f:
                content = f.read()
            
            lines = content.split('\n')
            deps = []
            in_require = False
            
            for line in lines:
                line = line.strip()
                if line.startswith('require'):
                    in_require = True
                    if '(' in line:
                        continue
                    else:
                        deps.append(line.replace('require ', ''))
                elif in_require:
                    if line == ')':
                        in_require = False
                    elif line:
                        deps.append(line)
            
            result = f"**Go Modules**: {len(deps)} dependencies\n"
            
            if deps:
                result += "\n  **Key Dependencies**:\n"
                for dep in deps[:10]:
                    result += f"    {dep}\n"
            
            return result
        except Exception as e:
            return f"Go mod analysis error: {e}"

    def _analyze_pubspec(self, project_path: Path) -> str:
        """Analyze pubspec.yaml dependencies"""
        try:
            import yaml
            with open(project_path / "pubspec.yaml", 'r') as f:
                pubspec_data = yaml.safe_load(f)
            
            deps = pubspec_data.get('dependencies', {})
            dev_deps = pubspec_data.get('dev_dependencies', {})
            
            result = "**Dart/Flutter Dependencies**:\n"
            result += f"  Production: {len(deps)} packages\n"
            result += f"  Development: {len(dev_deps)} packages\n"
            
            if deps:
                result += "\n  **Key Dependencies**:\n"
                for name, version in list(deps.items())[:10]:
                    result += f"    {name}: {version}\n"
            
            return result
        except ImportError:
            return "Pubspec analysis requires 'pyyaml' package"
        except Exception as e:
            return f"Pubspec analysis error: {e}"

class LangchainCodeMetricsTool(AsyncTool):
    name: str = "code_metrics"
    description: str = "Calculate code metrics including lines of code, complexity, and other statistical information about the codebase."
    args_schema: Type[BaseModel] = CodeMetricsSchema

    def _run(self, path: str = ".") -> str:
        logger.info(f"Code Metrics: path='{path}'")

        try:
            project_path = Path(path).resolve()
            if not _is_path_safe(project_path):
                return f"Access denied: '{path}' is a restricted system location."
            if not project_path.exists():
                return f"Path does not exist: {path}"

            # Load gitignore patterns
            gitignore_patterns = _load_gitignore_patterns(project_path)
            
            # Initialize metrics
            metrics = {
                'total_files': 0,
                'total_lines': 0,
                'code_lines': 0,
                'comment_lines': 0,
                'blank_lines': 0,
                'languages': {}
            }
            
            # Language mappings
            language_map = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.ts': 'TypeScript', 
                '.dart': 'Dart',
                '.java': 'Java',
                '.cpp': 'C++',
                '.c': 'C',
                '.rs': 'Rust',
                '.go': 'Go',
                '.php': 'PHP',
                '.rb': 'Ruby',
                '.css': 'CSS',
                '.html': 'HTML',
                '.xml': 'XML',
                '.json': 'JSON',
                '.yaml': 'YAML',
                '.yml': 'YAML'
            }
            
            # Process files
            for file_path in project_path.rglob('*'):
                if not file_path.is_file():
                    continue
                
                # Skip hidden files and gitignored files
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                
                if _is_ignored_by_gitignore(file_path, project_path, gitignore_patterns):
                    continue
                
                ext = file_path.suffix.lower()
                if ext not in language_map:
                    continue
                
                language = language_map[ext]
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    metrics['total_files'] += 1
                    file_metrics = self._analyze_file_metrics(lines, language)
                    
                    # Update totals
                    metrics['total_lines'] += file_metrics['total']
                    metrics['code_lines'] += file_metrics['code']
                    metrics['comment_lines'] += file_metrics['comments']
                    metrics['blank_lines'] += file_metrics['blank']
                    
                    # Update language metrics
                    if language not in metrics['languages']:
                        metrics['languages'][language] = {
                            'files': 0,
                            'lines': 0,
                            'code_lines': 0
                        }
                    
                    lang_metrics = metrics['languages'][language]
                    lang_metrics['files'] += 1
                    lang_metrics['lines'] += file_metrics['total']
                    lang_metrics['code_lines'] += file_metrics['code']
                    
                except Exception as e:
                    logger.warning(f"Could not analyze {file_path}: {e}")
                    continue
            
            return self._format_metrics_report(metrics)
            
        except Exception as e:
            logger.error(f"Code Metrics error: {e}")
            return f"Code metrics error: {str(e)}"

    def _analyze_file_metrics(self, lines: List[str], language: str) -> dict:
        """Analyze metrics for a single file"""
        metrics = {
            'total': len(lines),
            'code': 0,
            'comments': 0,
            'blank': 0
        }
        
        # Define comment patterns by language
        comment_patterns = {
            'Python': ['#'],
            'JavaScript': ['//', '/*', '*/'],
            'TypeScript': ['//', '/*', '*/'],
            'Dart': ['//', '/*', '*/'],
            'Java': ['//', '/*', '*/'],
            'C++': ['//', '/*', '*/'],
            'C': ['//', '/*', '*/'],
            'Rust': ['//', '/*', '*/'],
            'Go': ['//', '/*', '*/'],
            'PHP': ['//', '/*', '*/', '#'],
            'Ruby': ['#'],
            'CSS': ['/*', '*/'],
            'HTML': ['<!--', '-->'],
            'XML': ['<!--', '-->']
        }
        
        patterns = comment_patterns.get(language, ['#', '//'])
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                metrics['blank'] += 1
            elif any(stripped.startswith(pattern) for pattern in patterns):
                metrics['comments'] += 1
            else:
                metrics['code'] += 1
        
        return metrics

    def _format_metrics_report(self, metrics: dict) -> str:
        """Format the metrics into a readable report"""
        result = "**Code Metrics Report**\n\n"
        
        # Overall statistics
        result += f"📊 **Overall Statistics**:\n"
        result += f"  Total Files: {metrics['total_files']:,}\n"
        result += f"  Total Lines: {metrics['total_lines']:,}\n"
        result += f"  Code Lines: {metrics['code_lines']:,}\n"
        result += f"  Comment Lines: {metrics['comment_lines']:,}\n"
        result += f"  Blank Lines: {metrics['blank_lines']:,}\n\n"
        
        # Calculate percentages
        if metrics['total_lines'] > 0:
            code_pct = (metrics['code_lines'] / metrics['total_lines']) * 100
            comment_pct = (metrics['comment_lines'] / metrics['total_lines']) * 100
            blank_pct = (metrics['blank_lines'] / metrics['total_lines']) * 100
            
            result += f"📈 **Composition**:\n"
            result += f"  Code: {code_pct:.1f}%\n"
            result += f"  Comments: {comment_pct:.1f}%\n"
            result += f"  Blank: {blank_pct:.1f}%\n\n"
        
        # Language breakdown
        if metrics['languages']:
            result += f"🗣️ **Languages**:\n"
            sorted_langs = sorted(
                metrics['languages'].items(), 
                key=lambda x: x[1]['lines'], 
                reverse=True
            )
            
            for lang, lang_metrics in sorted_langs[:10]:
                result += f"  {lang}: {lang_metrics['files']} files, {lang_metrics['lines']:,} lines\n"
        
        # Averages
        if metrics['total_files'] > 0:
            avg_lines = metrics['total_lines'] / metrics['total_files']
            result += f"\n📏 **Averages**:\n"
            result += f"  Lines per file: {avg_lines:.1f}\n"
        
        return result