#!/usr/bin/env python3
"""
Package Search Tools - Library and Package Discovery
==================================================

This module contains package search tools for the MCP server.
Provides search across various package ecosystems (npm, PyPI, pub.dev, etc.).
"""

import requests
import logging
from typing import Type, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool as LangchainBaseTool

logger = logging.getLogger(__name__)

# ===== SCHEMAS =====

class PackageSearchSchema(BaseModel):
    ecosystem: str = Field(description="Package ecosystem: 'npm', 'pypi', 'pub', 'crates', 'maven', 'rubygems'")
    query: str = Field(description="Package search query")
    max_results: int = Field(description="Maximum number of results", default=5)

# ===== TOOL CLASS =====

class LangchainPackageSearchTool(LangchainBaseTool):
    name: str = "search_packages"
    description: str = "Search for packages/libraries across different ecosystems (npm, PyPI, pub.dev, crates.io, etc.)"
    args_schema: Type[BaseModel] = PackageSearchSchema

    def _run(self, ecosystem: str, query: str, max_results: int = 5) -> str:
        logger.info(f"Package Search: ecosystem='{ecosystem}', query='{query}', max_results={max_results}")
        try:
            ecosystem = ecosystem.lower()
            max_results = min(max_results, 10)  # Limit results
            
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
                return f"Unsupported ecosystem '{ecosystem}'. Supported: npm, pypi, pub, crates, maven, rubygems"
                
        except Exception as e:
            logger.error(f"Package Search error: {e}")
            return f"Package search failed: {str(e)}"
    
    def _search_npm(self, query: str, max_results: int) -> str:
        """Search npm packages"""
        try:
            url = f"https://registry.npmjs.org/-/v1/search"
            params = {"text": query, "size": max_results}
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            packages = data.get("objects", [])
            
            if not packages:
                return f"No npm packages found for '{query}'"
            
            results = []
            for i, pkg_data in enumerate(packages, 1):
                pkg = pkg_data.get("package", {})
                name = pkg.get("name", "Unknown")
                version = pkg.get("version", "Unknown")
                description = pkg.get("description", "No description")
                keywords = pkg.get("keywords", [])
                
                results.append(
                    f"{i}. **{name}** v{version}\n"
                    f"   {description}\n"
                    f"   Keywords: {', '.join(keywords[:5])}\n"
                    f"   npm install {name}\n"
                )
            
            return f"NPM package search results for '{query}':\n\n" + "\n".join(results)
            
        except Exception as e:
            return f"NPM search failed: {str(e)}"
    
    def _search_pypi(self, query: str, max_results: int) -> str:
        """Search PyPI packages"""
        try:
            url = f"https://pypi.org/pypi/{query}/json"
            
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                info = data.get("info", {})
                
                name = info.get("name", "Unknown")
                version = info.get("version", "Unknown")
                summary = info.get("summary", "No description")
                author = info.get("author", "Unknown")
                
                return f"PyPI package found:\n\n**{name}** v{version}\n{summary}\nAuthor: {author}\npip install {name}"
            else:
                # Try search API
                search_url = f"https://pypi.org/simple/"
                return f"PyPI search for '{query}' - try exact package name"
                
        except Exception as e:
            return f"PyPI search failed: {str(e)}"
    
    def _search_pub(self, query: str, max_results: int) -> str:
        """Search pub.dev packages"""
        try:
            url = f"https://pub.dev/api/search"
            params = {"q": query, "page": 1}
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            packages = data.get("packages", [])
            
            if not packages:
                return f"No pub.dev packages found for '{query}'"
            
            results = []
            for i, pkg in enumerate(packages[:max_results], 1):
                name = pkg.get("package", "Unknown")
                latest = pkg.get("latest", {})
                version = latest.get("version", "Unknown")
                description = latest.get("pubspec", {}).get("description", "No description")
                
                results.append(
                    f"{i}. **{name}** v{version}\n"
                    f"   {description}\n"
                    f"   flutter pub add {name}\n"
                )
            
            return f"Pub.dev package search results for '{query}':\n\n" + "\n".join(results)
            
        except Exception as e:
            return f"Pub.dev search failed: {str(e)}"
    
    def _search_crates(self, query: str, max_results: int) -> str:
        """Search crates.io packages"""
        try:
            url = f"https://crates.io/api/v1/crates"
            params = {"q": query, "per_page": max_results}
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            crates = data.get("crates", [])
            
            if not crates:
                return f"No crates found for '{query}'"
            
            results = []
            for i, crate in enumerate(crates, 1):
                name = crate.get("name", "Unknown")
                newest_version = crate.get("newest_version", "Unknown")
                description = crate.get("description", "No description")
                
                results.append(
                    f"{i}. **{name}** v{newest_version}\n"
                    f"   {description}\n"
                    f"   cargo add {name}\n"
                )
            
            return f"Crates.io search results for '{query}':\n\n" + "\n".join(results)
            
        except Exception as e:
            return f"Crates.io search failed: {str(e)}"
    
    def _search_maven(self, query: str, max_results: int) -> str:
        """Search Maven packages"""
        return f"Maven search not yet implemented for '{query}'"
    
    def _search_rubygems(self, query: str, max_results: int) -> str:
        """Search RubyGems packages"""
        return f"RubyGems search not yet implemented for '{query}'"

    async def _arun(self, ecosystem: str, query: str, max_results: int = 5) -> str:
        return self._run(ecosystem, query, max_results)