#!/usr/bin/env python3
"""
Linter Tools - Code Analysis and Auto-fixing
===========================================

This module contains auto-linter tools for the MCP server.
Provides language-specific linting, formatting, and auto-fixing capabilities.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Type

from langchain_core.tools import BaseTool as LangchainBaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ===== SCHEMAS =====


class AutoLinterSchema(BaseModel):
    directory: str = Field(
        description="Directory to analyze (default: current directory)", default="."
    )
    action: str = Field(
        description="Action: 'analyze', 'fix', 'format', 'suggest', 'check'",
        default="analyze",
    )
    language: Optional[str] = Field(
        description="Language: 'flutter', 'javascript', 'python', 'rust', 'go', 'java' (auto-detected if not specified)",
        default=None,
    )
    auto_fix: bool = Field(
        description="Automatically apply fixes where possible", default=False
    )


# ===== TOOL CLASS =====


class LangchainAutoLinterTool(LangchainBaseTool):
    name: str = "auto_linter_analyzer"
    description: str = (
        "Integrates with VS Code extension auto-linters and fixers for multiple languages. Knows about Flutter analyze, dart fix, ESLint, Prettier, etc."
    )
    args_schema: Type[BaseModel] = AutoLinterSchema

    def _run(
        self,
        directory: str = ".",
        action: str = "analyze",
        language: Optional[str] = None,
        auto_fix: bool = False,
    ) -> str:
        logger.info(
            f"Auto-Linter: directory='{directory}', action='{action}', language='{language}', auto_fix={auto_fix}"
        )
        try:
            path = Path(directory).resolve()
            if not path.exists():
                return f"Directory does not exist: {directory}"

            # Auto-detect language if not specified
            if not language:
                language = self._detect_project_language(path)

            if action == "analyze":
                return self._run_analysis(path, language)
            elif action == "fix":
                return self._run_auto_fix(path, language, auto_fix)
            elif action == "format":
                return self._run_formatting(path, language)
            elif action == "suggest":
                return self._generate_suggestions(path, language)
            elif action == "check":
                return self._run_comprehensive_check(path, language)
            else:
                return f"Invalid action '{action}'. Use: analyze, fix, format, suggest, check"

        except Exception as e:
            logger.error(f"Auto-Linter error: {e}")
            return f"Auto-linter operation failed: {str(e)}"

    def _detect_project_language(self, path: Path) -> str:
        """Auto-detect the primary language of the project"""
        # Check for project files to determine language
        if (path / "pubspec.yaml").exists():
            return "flutter"
        elif (path / "package.json").exists():
            # Check if it's React, Vue, etc.
            try:
                with open(path / "package.json", "r") as f:
                    package_data = json.load(f)
                dependencies = {
                    **package_data.get("dependencies", {}),
                    **package_data.get("devDependencies", {}),
                }

                if "react" in dependencies:
                    return "react"
                elif "vue" in dependencies:
                    return "vue"
                elif "@angular/core" in dependencies:
                    return "angular"
                else:
                    return "javascript"
            except:
                return "javascript"
        elif (path / "requirements.txt").exists() or (path / "setup.py").exists():
            return "python"
        elif (path / "Cargo.toml").exists():
            return "rust"
        elif (path / "go.mod").exists():
            return "go"
        elif (path / "pom.xml").exists() or (path / "build.gradle").exists():
            return "java"
        else:
            return "unknown"

    def _run_analysis(self, path: Path, language: str) -> str:
        """Run language-specific analysis tools"""
        results = []

        if language == "flutter":
            results.extend(self._flutter_analysis(path))
        elif language in ["javascript", "react", "vue", "angular"]:
            results.extend(self._javascript_analysis(path))
        elif language == "python":
            results.extend(self._python_analysis(path))
        elif language == "rust":
            results.extend(self._rust_analysis(path))
        elif language == "go":
            results.extend(self._go_analysis(path))
        elif language == "java":
            results.extend(self._java_analysis(path))
        else:
            return f"Auto-linter not configured for language: {language}"

        if not results:
            return f"No issues found or linting tools not available for {language}"

        summary = f"Auto-Linter Analysis Results for {language.title()}:\n\n"
        summary += "\n".join(results)

        return summary

    def _flutter_analysis(self, path: Path) -> List[str]:
        """Run Flutter/Dart specific analysis"""
        results = []

        try:
            os.chdir(path)
            # Run flutter analyze
            result = subprocess.run(
                ["flutter", "analyze"], capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                results.append("✅ Flutter Analysis: No issues found")
            else:
                results.append(f"⚠️ Flutter Analysis Issues:\n{result.stdout}")
        except subprocess.TimeoutExpired:
            results.append("❌ Flutter analyze timed out")
        except FileNotFoundError:
            results.append("❌ Flutter CLI not found")
        except Exception as e:
            results.append(f"❌ Flutter analysis error: {e}")

        return results

    def _javascript_analysis(self, path: Path) -> List[str]:
        """Run JavaScript/Node.js specific analysis"""
        results = []

        try:
            os.chdir(path)

            # Check for ESLint
            if (path / "node_modules" / ".bin" / "eslint").exists():
                result = subprocess.run(
                    ["npx", "eslint", "."], capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    results.append("✅ ESLint: No issues found")
                else:
                    results.append(f"⚠️ ESLint Issues:\n{result.stdout[:1000]}")
            else:
                results.append("ℹ️ ESLint not configured")

        except Exception as e:
            results.append(f"❌ JavaScript analysis error: {e}")

        return results

    def _python_analysis(self, path: Path) -> List[str]:
        """Run Python specific analysis"""
        results = []

        try:
            os.chdir(path)

            # Try flake8
            try:
                result = subprocess.run(
                    ["flake8", "."], capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    results.append("✅ Flake8: No issues found")
                else:
                    results.append(f"⚠️ Flake8 Issues:\n{result.stdout[:1000]}")
            except FileNotFoundError:
                results.append("ℹ️ Flake8 not installed")

        except Exception as e:
            results.append(f"❌ Python analysis error: {e}")

        return results

    def _rust_analysis(self, path: Path) -> List[str]:
        """Run Rust specific analysis"""
        results = []

        try:
            os.chdir(path)
            result = subprocess.run(
                ["cargo", "clippy"], capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                results.append("✅ Cargo Clippy: No issues found")
            else:
                results.append(f"⚠️ Cargo Clippy Issues:\n{result.stdout[:1000]}")
        except Exception as e:
            results.append(f"❌ Rust analysis error: {e}")

        return results

    def _go_analysis(self, path: Path) -> List[str]:
        """Run Go specific analysis"""
        results = []

        try:
            os.chdir(path)

            # Run go vet
            result = subprocess.run(
                ["go", "vet", "./..."], capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                results.append("✅ Go Vet: No issues found")
            else:
                results.append(f"⚠️ Go Vet Issues:\n{result.stderr[:1000]}")

        except Exception as e:
            results.append(f"❌ Go analysis error: {e}")

        return results

    def _java_analysis(self, path: Path) -> List[str]:
        """Run Java specific analysis"""
        results = []
        results.append("ℹ️ Java analysis not yet implemented")
        return results

    def _run_auto_fix(self, path: Path, language: str, auto_fix: bool) -> str:
        """Run auto-fix tools for the specified language"""
        if not auto_fix:
            return "Auto-fix not enabled. Set auto_fix=true to apply fixes."

        results = []

        try:
            os.chdir(path)

            if language == "flutter":
                # Run dart fix
                result = subprocess.run(
                    ["dart", "fix", "--apply"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                results.append(f"Dart Fix Applied:\n{result.stdout}")

            elif language in ["javascript", "react", "vue", "angular"]:
                # Run ESLint fix
                if (path / "node_modules" / ".bin" / "eslint").exists():
                    result = subprocess.run(
                        ["npx", "eslint", ".", "--fix"],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    results.append(f"ESLint Fix Applied:\n{result.stdout}")

            elif language == "python":
                # Run black formatter
                try:
                    result = subprocess.run(
                        ["black", "."], capture_output=True, text=True, timeout=60
                    )
                    results.append(f"Black Formatter Applied:\n{result.stdout}")
                except FileNotFoundError:
                    results.append("Black formatter not installed")

        except Exception as e:
            return f"Auto-fix error: {e}"

        return (
            "\n".join(results)
            if results
            else "No auto-fixes available for this language"
        )

    def _run_formatting(self, path: Path, language: str) -> str:
        """Run formatting tools for the specified language"""
        return "Formatting feature not yet implemented"

    def _generate_suggestions(self, path: Path, language: str) -> str:
        """Generate improvement suggestions"""
        return "Suggestions feature not yet implemented"

    def _run_comprehensive_check(self, path: Path, language: str) -> str:
        """Run comprehensive analysis including multiple tools"""
        analysis = self._run_analysis(path, language)
        return f"Comprehensive Check:\n{analysis}"

    async def _arun(
        self,
        directory: str = ".",
        action: str = "analyze",
        language: Optional[str] = None,
        auto_fix: bool = False,
    ) -> str:
        return self._run(directory, action, language, auto_fix)
