#!/usr/bin/env python3
"""
MCP Web Search Tool - Agent-Driven Search and Scraping
======================================================

Provides web search that returns URLs for the agent to choose from,
plus targeted scraping of agent-selected URLs.
"""

import os
import logging
import requests
from typing import Dict, List, Optional, Type
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup

from .base import AsyncTool
from config import DEFAULT_MODEL, get_cached_llm

logger = logging.getLogger(__name__)

# Google Custom Search API configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

if not GOOGLE_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
    logger.error("Google API key or Search Engine ID not found in environment variables.")


class WebSearchSchema(BaseModel):
    query: str = Field(description="Search terms to find relevant websites")
    extract_info: str = Field(
        description="What specific information to extract (e.g. 'current temperature', 'store hours', 'product price')")
    max_results: int = Field(description="Maximum number of search results to return", default=3)


class WebScrapeSchema(BaseModel):
    url: str = Field(description="Specific URL to scrape content from")
    timeout: int = Field(description="Timeout in seconds for scraping", default=10)


class LangchainWebSearchTool(AsyncTool):
    name: str = "search_web"
    description: str = (
        "Search the web and return a list of URLs with titles and descriptions. "
        "The agent can then choose which specific URLs to scrape using the scrape_url tool."
    )
    args_schema: Type[BaseModel] = WebSearchSchema

    def _run(self, query: str, extract_info: str, max_results: int = 3) -> str:
        """Search web and extract specific information"""
        logger.info(f"Web search: '{query}', extracting: '{extract_info}', max_results={max_results}")

        try:
            search_results = self._get_search_results(query, max_results)

            if not search_results:
                return f"No search results found for: '{query}'"

            # Combine search snippets and top result content
            context_parts = ["--- Web Search Summaries ---"]
            for idx, res in enumerate(search_results):
                context_parts.append(f"Source {idx+1}: {res['title']} ({res['href']})\nSynopsis: {res['body']}")
            
            # Scrape the first result
            best_url = search_results[0]['href']
            content = self._scrape_content(best_url, 10)
            
            if content:
                context_parts.append(f"\n--- Full Text from Top Result ({best_url}) ---\n{content[:1500]}")
            else:
                context_parts.append(f"\n--- Note: Could not extract full text from {best_url} ---")
                
            full_context = "\n\n".join(context_parts)

            # Use same cached model instance as the rest of the app
            llm = get_cached_llm(DEFAULT_MODEL)

            extraction_prompt = f"""Extract only: {extract_info}

Search Context:
{full_context[:3000]}

Output format: Provide a clear answer using the context. If the exact answer isn't available, provide the most relevant information from the snippets."""

            response = llm.invoke(extraction_prompt)
            extracted = response.content.strip()

            # Return with source attribution
            return f"{extracted}\n\n**Primary Source**: {best_url}"

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Web search failed: {str(e)}"

    def _scrape_content(self, url: str, timeout: int) -> Optional[str]:
        """Scrape content from URL"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
            }

            response = requests.get(url, headers=headers, timeout=timeout, verify=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                element.decompose()

            # Try multiple content selectors
            content_selectors = [
                "main", "article", ".content", ".post-content",
                ".entry-content", ".article-content", "#content",
                ".page-content", "body"
            ]

            content_area = None
            for selector in content_selectors:
                content_area = soup.select_one(selector)
                if content_area:
                    break

            if content_area:
                text = content_area.get_text(separator="\n", strip=True)
                # Clean up excessive whitespace
                text = "\n".join(line.strip() for line in text.split("\n") if line.strip())

                # Limit content length
                if len(text) > 1500:
                    text = text[:1500] + f"\n\n... (content truncated - showing first 1500 of {len(text)} characters)"

                return text

            return None

        except requests.exceptions.Timeout:
            return f"Timeout after {timeout} seconds"
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception as e:
            return f"Search error: {str(e)}"

    def _get_search_results(self, query: str, max_results: int) -> List[Dict]:
        """Get search results from DuckDuckGo (fallback) or Google"""
        results = []
        try:
            if GOOGLE_API_KEY:
                logger.debug("Attempting Google Custom Search API")
                url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    "key": GOOGLE_API_KEY,
                    "cx": GOOGLE_SEARCH_ENGINE_ID,
                    "q": query,
                    "num": min(max_results, 10),
                    "safe": "medium",
                }

                response = requests.get(url, params=params, timeout=15)
                # If Google succeeds, use its results
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    for item in items:
                        results.append({
                            "title": item.get("title", ""),
                            "body": item.get("snippet", ""),
                            "href": item.get("link", ""),
                        })
                    logger.info(f"Found {len(results)} search results for '{query}' via Google")
                    return results
                else:
                    logger.warning(f"Google Search failed with status {response.status_code}, falling back to DuckDuckGo")
            
        except Exception as e:
            logger.warning(f"Google Custom Search encountered error: {e}, falling back to DuckDuckGo")
            
        # Fallback to robust direct scraping of DuckDuckGo Lite
        try:
            from bs4 import BeautifulSoup
            
            url = "https://lite.duckduckgo.com/lite/"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
            response = requests.post(url, data={"q": query}, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            for tr in soup.find_all('tr'):
                result_snippet = tr.find('td', class_='result-snippet')
                if result_snippet:
                    prev_tr = tr.find_previous_sibling('tr')
                    if prev_tr:
                        a_tag = prev_tr.find('a')
                        if a_tag:
                            results.append({
                                "title": a_tag.text.strip(),
                                "body": result_snippet.text.strip(),
                                "href": a_tag.get('href', "")
                            })
                if len(results) >= max_results:
                    break
            
            logger.info(f"Found {len(results)} search results for '{query}' via DDG Direct Scrape")
            return results

        except Exception as e:
            logger.error(f"Fallback direct scraper failed: {e}")
            return []


class LangchainWebScrapeTool(AsyncTool):
    name: str = "scrape_url"
    description: str = (
        "Scrape content from a specific URL chosen by the agent. "
        "Use this after getting URLs from the search_web tool."
    )
    args_schema: Type[BaseModel] = WebScrapeSchema

    def _run(self, url: str, timeout: int = 10) -> str:
        """Scrape content from specific URL"""
        logger.info(f"Scraping URL: {url}")

        try:
            content = self._scrape_content(url, timeout)

            if content:
                return f"**Content from {url}:**\n\n{content}"
            else:
                return f"Failed to scrape content from: {url}"

        except Exception as e:
            logger.error(f"URL scraping failed: {e}")
            return f"Scraping failed: {str(e)}"

    def _scrape_content(self, url: str, timeout: int) -> Optional[str]:
        """Scrape content from URL"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
            }

            response = requests.get(url, headers=headers, timeout=timeout, verify=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                element.decompose()

            # Try multiple content selectors
            content_selectors = [
                "main", "article", ".content", ".post-content",
                ".entry-content", ".article-content", "#content",
                ".page-content", "body"
            ]

            content_area = None
            for selector in content_selectors:
                content_area = soup.select_one(selector)
                if content_area:
                    break

            if content_area:
                text = content_area.get_text(separator="\n", strip=True)
                # Clean up excessive whitespace
                text = "\n".join(line.strip() for line in text.split("\n") if line.strip())

                # Limit content length
                if len(text) > 1500:
                    text = text[:1500] + f"\n\n... (content truncated - showing first 1500 of {len(text)} characters)"

                return text

            return None

        except requests.exceptions.Timeout:
            return f"Timeout after {timeout} seconds"
        except requests.exceptions.RequestException as e:
            return f"Request failed: {str(e)}"
        except Exception as e:
            return f"Scraping error: {str(e)}"
