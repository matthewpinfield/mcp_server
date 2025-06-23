#!/usr/bin/env python3
"""
GitHub Tools - GitHub API Integration
====================================

This module contains GitHub API tools for the MCP server.
Provides search, issues, releases, and repository information.
"""

import requests
import logging
import os
from typing import Type, Optional
from pydantic import BaseModel, Field
from .base import AsyncTool

logger = logging.getLogger(__name__)

# Configuration
GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Optional for higher rate limits
GITHUB_SEARCH_MAX_RESULTS = 10  # Limit to prevent API abuse

# ===== SCHEMAS =====

class GitHubRepoSearchSchema(BaseModel):
    query: str = Field(description="Search query for repositories")
    language: Optional[str] = Field(description="Programming language filter", default=None)
    max_results: int = Field(description="Maximum number of results", default=5)

class GitHubIssueSearchSchema(BaseModel):
    repository: str = Field(description="Repository in format 'owner/repo' (e.g., 'facebook/react')")
    state: str = Field(description="Issue state: 'open', 'closed', or 'all'", default="open")
    max_results: int = Field(description="Maximum number of results", default=5)

class GitHubReleaseSchema(BaseModel):
    repository: str = Field(description="Repository in format 'owner/repo' (e.g., 'flutter/flutter')")
    max_results: int = Field(description="Maximum number of results", default=5)

# ===== TOOL CLASSES =====

class LangchainGitHubRepoSearchTool(AsyncTool):
    name: str = "search_github_repositories"
    description: str = "Searches GitHub for repositories based on query, language, and other criteria. Useful for finding projects, libraries, or examples."
    args_schema: Type[BaseModel] = GitHubRepoSearchSchema

    def _run(self, query: str, language: Optional[str] = None, max_results: int = 5) -> str:
        logger.info(f"GitHub Repo Search: query='{query}', language='{language}', max_results={max_results}")
        try:
            # Limit max_results to prevent abuse
            max_results = min(max_results, GITHUB_SEARCH_MAX_RESULTS)
            
            # Build search query
            search_query = query
            if language:
                search_query += f" language:{language}"
            
            # Prepare headers
            headers = {"Accept": "application/vnd.github.v3+json"}
            if GITHUB_TOKEN:
                headers["Authorization"] = f"token {GITHUB_TOKEN}"
            
            # Make API request
            url = f"{GITHUB_API_BASE}/search/repositories"
            params = {
                "q": search_query,
                "sort": "stars",
                "order": "desc",
                "per_page": max_results
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            repositories = data.get("items", [])
            
            if not repositories:
                return f"No repositories found for query: '{query}'"
            
            # Format results
            results = []
            for i, repo in enumerate(repositories, 1):
                name = repo.get("full_name", "Unknown")
                description = repo.get("description", "No description")
                stars = repo.get("stargazers_count", 0)
                language = repo.get("language", "Unknown")
                url = repo.get("html_url", "")
                updated = repo.get("updated_at", "").split("T")[0] if repo.get("updated_at") else "Unknown"
                
                results.append(
                    f"{i}. **{name}** ⭐ {stars:,}\n"
                    f"   Language: {language} | Updated: {updated}\n"
                    f"   {description}\n"
                    f"   {url}\n"
                )
            
            summary = f"GitHub repository search results for '{query}':\n\n" + "\n".join(results)
            logger.info(f"GitHub Repo Search: Found {len(repositories)} repositories")
            return summary
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub Repo Search API error: {e}")
            return f"GitHub API error: {str(e)}"
        except Exception as e:
            logger.error(f"GitHub Repo Search error: {e}")
            return f"GitHub repository search failed: {str(e)}"


class LangchainGitHubIssuesTool(AsyncTool):
    name: str = "search_github_issues"
    description: str = "Searches for issues in a specific GitHub repository. Useful for finding bugs, feature requests, or project status."
    args_schema: Type[BaseModel] = GitHubIssueSearchSchema

    def _run(self, repository: str, state: str = "open", max_results: int = 5) -> str:
        logger.info(f"GitHub Issues Search: repo='{repository}', state='{state}', max_results={max_results}")
        try:
            # Validate repository format
            if "/" not in repository:
                return "Repository must be in format 'owner/repo' (e.g., 'facebook/react')"
            
            # Limit max_results
            max_results = min(max_results, GITHUB_SEARCH_MAX_RESULTS)
            
            # Prepare headers
            headers = {"Accept": "application/vnd.github.v3+json"}
            if GITHUB_TOKEN:
                headers["Authorization"] = f"token {GITHUB_TOKEN}"
            
            # Make API request
            url = f"{GITHUB_API_BASE}/repos/{repository}/issues"
            params = {
                "state": state,
                "per_page": max_results,
                "sort": "updated",
                "direction": "desc"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            issues = response.json()
            
            if not issues:
                return f"No {state} issues found in repository: {repository}"
            
            # Format results
            results = []
            for i, issue in enumerate(issues, 1):
                number = issue.get("number", "Unknown")
                title = issue.get("title", "No title")
                state_emoji = "🟢" if issue.get("state") == "open" else "🔴"
                labels = [label.get("name", "") for label in issue.get("labels", [])]
                labels_str = f"[{', '.join(labels[:3])}]" if labels else ""
                url = issue.get("html_url", "")
                updated = issue.get("updated_at", "").split("T")[0] if issue.get("updated_at") else "Unknown"
                
                # Check if it's a pull request
                is_pr = issue.get("pull_request") is not None
                type_indicator = "🔀 PR" if is_pr else "📋 Issue"
                
                results.append(
                    f"{i}. {state_emoji} {type_indicator} #{number}: {title}\n"
                    f"   {labels_str} | Updated: {updated}\n"
                    f"   {url}\n"
                )
            
            summary = f"GitHub {state} issues/PRs for {repository}:\n\n" + "\n".join(results)
            logger.info(f"GitHub Issues Search: Found {len(issues)} issues")
            return summary
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub Issues API error: {e}")
            return f"GitHub API error: {str(e)}"
        except Exception as e:
            logger.error(f"GitHub Issues error: {e}")
            return f"GitHub issues search failed: {str(e)}"


class LangchainGitHubReleasesTool(AsyncTool):
    name: str = "get_github_releases"
    description: str = "Gets recent releases and version information for a GitHub repository. Useful for tracking updates and changelog."
    args_schema: Type[BaseModel] = GitHubReleaseSchema

    def _run(self, repository: str, max_results: int = 5) -> str:
        logger.info(f"GitHub Releases: repo='{repository}', max_results={max_results}")
        try:
            # Validate repository format
            if "/" not in repository:
                return "Repository must be in format 'owner/repo' (e.g., 'flutter/flutter')"
            
            # Limit max_results
            max_results = min(max_results, GITHUB_SEARCH_MAX_RESULTS)
            
            # Prepare headers
            headers = {"Accept": "application/vnd.github.v3+json"}
            if GITHUB_TOKEN:
                headers["Authorization"] = f"token {GITHUB_TOKEN}"
            
            # Make API request
            url = f"{GITHUB_API_BASE}/repos/{repository}/releases"
            params = {"per_page": max_results}
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            releases = response.json()
            
            if not releases:
                return f"No releases found for repository: {repository}"
            
            # Format results
            results = []
            for i, release in enumerate(releases, 1):
                tag_name = release.get("tag_name", "Unknown")
                name = release.get("name", tag_name)
                published = release.get("published_at", "").split("T")[0] if release.get("published_at") else "Unknown"
                prerelease = " Pre-release" if release.get("prerelease") else "Stable"
                draft = " (Draft)" if release.get("draft") else ""
                url = release.get("html_url", "")
                
                # Get body preview (first 150 chars)
                body = release.get("body", "No release notes")
                body_preview = body[:150] + "..." if len(body) > 150 else body
                
                results.append(
                    f"{i}. **{name}** ({tag_name}) {prerelease}{draft}\n"
                    f"   Published: {published}\n"
                    f"   {body_preview}\n"
                    f"   {url}\n"
                )
            
            summary = f"GitHub releases for {repository}:\n\n" + "\n".join(results)
            logger.info(f"GitHub Releases: Found {len(releases)} releases")
            return summary
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub Releases API error: {e}")
            return f"GitHub API error: {str(e)}"
        except Exception as e:
            logger.error(f"GitHub Releases error: {e}")
            return f"GitHub releases search failed: {str(e)}"

