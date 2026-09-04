#!/usr/bin/env python3
"""
MCP Web Search Tool - High-Quality Web Search with Domain Prioritization
=======================================================================

Provides intelligent web search functionality with tiered source prioritization.
"""

import os
import logging
import asyncio
import requests
from typing import Dict, List, Optional, Type
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from .base import AsyncTool

logger = logging.getLogger(__name__)

# Schema for web search parameters
class WebSearchSchema(BaseModel):
    query: str = Field(description="Search query for web search using Google/Bing. Be specific and include relevant keywords.")
    max_results: int = Field(description="Maximum number of search results to return", default=5)
    general_search: bool = Field(description="If True, searches all websites without domain filtering. If False, prioritizes technical/programming sources.", default=False)
    extended_timeout: bool = Field(description="If True, allows up to 60 seconds total time budget instead of 30 seconds. Use when normal search times out.", default=False)

# Google Custom Search API configuration
from config import GOOGLE_API_KEY, GOOGLE_SEARCH_ENGINE_ID

# Domain prioritization for reputable sources
PRIORITY_DOMAINS = {
    # Tier 1: Official Documentation & Style Guides (The Source of Truth)
    "tier_1_official": [
        "docs.flutter.dev", "flutter.dev", "dart.dev", "api.flutter.dev", "api.dart.dev",
        "docs.python.org", "python.org", "peps.python.org",
        "developer.mozilla.org", "nodejs.org", "web.dev",
        "react.dev", "reactjs.org", "vuejs.org", "angular.dev", "svelte.dev",
        "docs.microsoft.com", "developer.apple.com", "developers.google.com",
        "aws.amazon.com", "cloud.google.com", "azure.microsoft.com",
        "kubernetes.io", "docker.com", "golang.org", "rust-lang.org",
        "typescriptlang.org", "postgresql.org", "mongodb.com/docs"
    ],
    # Tier 2: Curated Educational Platforms & Expert Blogs (High-Quality Learning)
    "tier_2_educational": [
        "freecodecamp.org", "realpython.com", "digitalocean.com",
        "web.dev", "smashingmagazine.com", "martinfowler.com",
        "css-tricks.com", "a11yproject.com", "webhint.io"
    ],
    # Tier 3: Reputable Q&A and Official Repositories (High-Quality Community Content)
    "tier_3_community": [
        "stackoverflow.com", "github.com"
    ],
    # Tier 4: General Tech Blogs (Variable Quality - Use with Caution)
    "tier_4_blogs": [
        "medium.com", "dev.to", "hashnode.com", "codecademy.com"
    ],
    # Tier 5: News & Updates (For Current Events Only)
    "tier_5_news": [
        "techcrunch.com", "arstechnica.com", "theverge.com",
        "9to5google.com", "androidcentral.com", "engadget.com"
    ]
}

class LangchainWebSearchTool(AsyncTool):
    name: str = "search_web"
    description: str = (
        "Searches the web and returns HIGH-QUALITY, AUTHORITATIVE content from trusted sources. "
        "Use this tool for ANY request that needs current, real-time, or up-to-date information including: "
        "weather forecasts, current events, news, stock prices, sports scores, travel conditions, "
        "current information about places, latest software versions, recent developments, "
        "or any information that changes frequently. Always use this for weather queries."
    )
    args_schema: Type[BaseModel] = WebSearchSchema

    def _run(self, query: str, max_results: int = 3, general_search: bool = False, extended_timeout: bool = False) -> str:
        # Handle case where LangChain passes parameters via JSON string (same issue as sandbox tool)
        if isinstance(query, str) and query.startswith('{'):
            try:
                import json
                parsed = json.loads(query)
                query = parsed.get('query', query)
                max_results = parsed.get('max_results', max_results)
                general_search = parsed.get('general_search', general_search)
                extended_timeout = parsed.get('extended_timeout', extended_timeout)
            except json.JSONDecodeError:
                pass  # If parsing fails, use original values
        
        logger.info(f"🔍 High-Quality Web Search: query='{query}', max_results={max_results}, extended_timeout={extended_timeout}")
        try:
            # Get initial search results
            search_results = self._get_search_results(query, max_results * 3)
            
            if not search_results:
                return f"No search results found for query: '{query}'"
            
            # Auto-detect if this is a coding-related query
            is_coding_query = self._is_coding_related_query(query.lower())
            
            # Use domain filtering only for coding queries, general search for everything else
            if general_search or not is_coding_query:
                best_content = self._find_and_scrape_general_source(search_results, query, extended_timeout)
                logger.info(f" Using general search for query: '{query}'")
            else:
                best_content = self._find_and_scrape_best_source(search_results, query, extended_timeout)
                logger.info(f"🔧 Using technical search for coding query: '{query}'")
            
            if best_content:
                return best_content
            else:
                return f"No high-quality authoritative sources found for: '{query}'. Try refining your search terms or asking about established topics covered in official documentation."
            
        except Exception as e:
            logger.error(f"🔍 Web Search Tool error: {e}")
            return f"Web search failed: {str(e)}"
    
    def _get_search_results(self, query: str, max_results: int) -> List[Dict]:
        """Get search results from Google Custom Search API"""
        try:
            if not GOOGLE_API_KEY:
                logger.warning("Google Custom Search API key not configured")
                return []
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': GOOGLE_API_KEY,
                'cx': GOOGLE_SEARCH_ENGINE_ID,
                'q': query,
                'num': min(max_results, 10),  # Google allows max 10 per request
                'safe': 'medium'
            }
            
            logger.debug(f"🔍 Google Custom Search API call: {query}")
            
            # Progressive timeout for API calls: 15s, 30s
            for attempt, timeout_value in enumerate([15, 30], 1):
                try:
                    if attempt > 1:
                        logger.info(f"⏱️ Google API retry {attempt}/2 with {timeout_value}s timeout")
                    
                    response = requests.get(url, params=params, timeout=timeout_value)
                    break
                    
                except requests.exceptions.Timeout as e:
                    if attempt < 2:
                        logger.warning(f"⏱️ Google API timeout after {timeout_value}s, retrying...")
                        continue
                    else:
                        logger.error(f"⏱️ Google API taking too long to respond after {timeout_value}s")
                        return []
            
            if response.status_code == 403:
                logger.error("Google Custom Search API: Quota exceeded or invalid API key")
                return []
            elif response.status_code == 429:
                logger.error("Google Custom Search API: Rate limit exceeded")
                return []
            
            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                logger.info(f"🔍 Google Custom Search: No results found for '{query}'")
                return []
            
            results = []
            for item in items:
                results.append({
                    'title': item.get('title', ''),
                    'body': item.get('snippet', ''),
                    'href': item.get('link', ''),
                    'display_link': item.get('displayLink', '')
                })
            
            logger.info(f"🔍 Google Custom Search: Found {len(results)} results for '{query}'")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Custom Search API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Google Custom Search failed: {e}")
            return []

    def _find_and_scrape_best_source(self, search_results: List[Dict], query: str, extended_timeout: bool = False) -> Optional[str]:
        """Find and scrape the best source from search results with time budget allocation"""
        tier_order = ["tier_1_official", "tier_2_educational", "tier_3_community", "tier_4_blogs"]
        failed_sources = []
        partial_content = []
        
        # Time budget allocation: 30 or 60 seconds total, split between promising URLs
        total_budget = 60.0 if extended_timeout else 30.0
        logger.info(f"⏱️ Using {'extended' if extended_timeout else 'standard'} time budget: {total_budget}s")
        urls_to_try = []
        
        # Collect promising URLs in tier order
        for tier_name in tier_order:
            tier_domains = PRIORITY_DOMAINS[tier_name]
            for result in search_results:
                href = result.get('href', '')
                if not href:
                    continue
                
                try:
                    domain = urlparse(href).netloc.replace('www.', '')
                    if any(tier_domain in domain for tier_domain in tier_domains):
                        urls_to_try.append((href, result.get('title', ''), tier_name, domain))
                        if len(urls_to_try) >= 3:  # Limit to top 3 promising URLs
                            break
                except Exception as e:
                    logger.debug(f"Error parsing URL {href}: {e}")
                    continue
            if len(urls_to_try) >= 3:
                break
        
        if not urls_to_try:
            return None
            
        # Allocate time budget: start with equal split, faster URLs leave more time for slower ones
        time_per_url = total_budget / len(urls_to_try)
        remaining_budget = total_budget
        
        import time
        for i, (href, title, tier_name, domain) in enumerate(urls_to_try):
            logger.info(f"🏆 Found {tier_name} source: {domain}")
            
            # Use remaining budget divided by remaining URLs
            remaining_urls = len(urls_to_try) - i
            current_budget = min(time_per_url, remaining_budget / remaining_urls)
            
            start_time = time.time()
            content = self._scrape_content(href, title, tier_name, current_budget)
            elapsed = time.time() - start_time
            remaining_budget -= elapsed
            
            if content:
                if content.startswith("🕐 TIMEOUT"):  # Timeout message
                    failed_sources.append(f"{domain}: {content}")
                    continue
                elif len(content.strip()) > 200:  # Good content threshold
                    logger.info(f" Successfully scraped from {tier_name}: {domain} in {elapsed:.1f}s")
                    return content
                else:
                    partial_content.append(f"{domain}: {content[:100]}...")
            
            logger.warning(f" No usable content from {domain}")
            
            # If we're out of time budget, stop trying
            if remaining_budget <= 1.0:
                logger.info(f"⏱️ Time budget exhausted, stopping search")
                break
        
        # If no good sources found, return summary of what was tried
        if failed_sources or partial_content:
            summary = f"❌ **WEB SEARCH INCOMPLETE** for query: '{query}'\n\n"
            
            # Check if any timeouts occurred
            timeout_sources = [fs for fs in failed_sources if "TIMEOUT" in fs]
            other_failures = [fs for fs in failed_sources if "TIMEOUT" not in fs]
            
            if timeout_sources:
                summary += "🕐 **TIMEOUTS OCCURRED:**\n"
                for timeout in timeout_sources[:3]:
                    summary += f"• {timeout}\n"
                summary += "\n💡 **Ask me to retry with more time if you need content from these specific sources.**\n\n"
            
            if other_failures:
                summary += "⚠️ **OTHER ISSUES:**\n"
                for error in other_failures[:3]:
                    summary += f"• {error}\n"
                summary += "\n"
                
            if partial_content:
                summary += "📄 **LIMITED CONTENT FOUND:**\n"
                for partial in partial_content[:2]:
                    summary += f"• {partial}\n"
                summary += "\n"
            
            summary += "🔄 **SUGGESTIONS:** Try refining your search terms, or ask me to search with more time for specific sources."
            return summary
        
        return None

    def _is_coding_related_query(self, query_lower: str) -> bool:
        """Detect if query is coding/programming related with context"""
        import re
        
        # Strong programming indicators - these alone indicate coding
        strong_coding_keywords = [
            "javascript", "typescript", "c++", "kotlin", "flutter", "react", "vue", "angular",
            "coding", "programming", "function", "method", "class", "variable", "array", "object",
            "algorithm", "debug", "syntax", "compile", "runtime", "framework", "library", 
            "github", "docker", "kubernetes", "npm", "pip", "cargo", "maven", "gradle",
            "webpack", "babel", "eslint", "pytest", "junit", "cmake", "json", "xml", "html",
            "css", "graphql", "async", "await", "regex", "orm", "mvc", "crud", "oauth", "jwt"
        ]
        
        for keyword in strong_coding_keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, query_lower):
                return True
        
        # Context-dependent keywords - need programming context
        ambiguous_keywords = {
            "python": ["tutorial", "code", "programming", "script", "import", "def", "class"],
            "java": ["tutorial", "code", "programming", "class", "public", "static", "void"],
            "rust": ["programming", "cargo", "crate", "ownership", "borrowing"],
            "go": ["golang", "programming", "goroutine", "channel"],
            "api": ["rest", "endpoint", "request", "response", "json"],
            "database": ["sql", "query", "table", "schema", "mysql", "postgres"],
            "error": ["exception", "bug", "debug", "traceback", "stack"]
        }
        
        for keyword, contexts in ambiguous_keywords.items():
            keyword_pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(keyword_pattern, query_lower):
                # Check if any programming context words are present
                for context in contexts:
                    context_pattern = r'\b' + re.escape(context) + r'\b'
                    if re.search(context_pattern, query_lower):
                        return True
        
        return False

    def _find_and_scrape_general_source(self, search_results: List[Dict], query: str, extended_timeout: bool = False) -> Optional[str]:
        """Find and scrape from any source without domain filtering for general queries"""
        # Skip useless sites for general information
        skip_domains = ["youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com", "twitter.com", "x.com"]
        
        # Time budget allocation: 30 or 60 seconds total for general search
        total_budget = 60.0 if extended_timeout else 30.0
        logger.info(f"⏱️ Using {'extended' if extended_timeout else 'standard'} time budget: {total_budget}s")
        valid_results = []
        
        # Filter out skip domains first
        for result in search_results:
            href = result.get('href', '')
            title = result.get('title', '')
            if not href:
                continue
            
            # Skip video/social media sites
            from urllib.parse import urlparse
            domain = urlparse(href).netloc.replace('www.', '')
            if any(skip_domain in domain for skip_domain in skip_domains):
                logger.debug(f"🚫 Skipping {domain} (video/social media site)")
                continue
                
            valid_results.append((href, title, domain))
            if len(valid_results) >= 3:  # Limit to top 3 valid URLs
                break
        
        if not valid_results:
            return f"No valid sources found for: '{query}'"
        
        # Allocate time budget equally, faster responses leave more time for slower ones
        remaining_budget = total_budget
        
        import time
        for i, (href, title, domain) in enumerate(valid_results):
            # Use remaining budget divided by remaining URLs
            remaining_urls = len(valid_results) - i
            current_budget = remaining_budget / remaining_urls
            
            logger.info(f" Trying general source #{i+1}: {href}")
            
            start_time = time.time()
            content = self._scrape_content(href, title, "general", current_budget)
            elapsed = time.time() - start_time
            remaining_budget -= elapsed
            
            if content and not content.startswith("🕐 TIMEOUT") and len(content.strip()) > 200:
                logger.info(f" Successfully scraped general source: {href} in {elapsed:.1f}s")
                return content
            
            # If we're out of time budget, stop trying
            if remaining_budget <= 1.0:
                logger.info(f"⏱️ Time budget exhausted for general search")
                break
        
        return f"Could not scrape useful content from search results for: '{query}'"

    def _scrape_content(self, url: str, title: str, tier: str, time_budget: float = 30.0) -> Optional[str]:
        """Scrape content from URL with time budget strategy"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            logger.info(f"🔗 Scraping content from: {url}")
            
            # Use the allocated time budget for this URL
            logger.info(f"⏱️ Using {time_budget:.1f}s timeout budget for: {url}")
            
            # Try with SSL verification first, then without if it fails
            for verify_ssl in [True, False]:
                try:
                    response = requests.get(url, headers=headers, timeout=time_budget, verify=verify_ssl)
                    response.raise_for_status()
                    break
                    
                except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                    if verify_ssl:
                        logger.warning(f"SSL error for {url}, retrying without SSL verification")
                        continue
                    else:
                        raise e
                except requests.exceptions.Timeout as e:
                    logger.warning(f"⏱️ Timeout after {time_budget:.1f}s for {url}")
                    return f"🕐 TIMEOUT: {url} did not respond within {time_budget:.1f} seconds. The website may be slow or experiencing issues. If you need this specific content, please ask me to try again with more time."
            
            soup = BeautifulSoup(response.text, 'html.parser')
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Try multiple content selectors
            content_selectors = [
                'main', 'article', '.content', '.post-content', '.entry-content', 
                '.article-content', '#content', '.page-content', 'body'
            ]
            
            content_area = None
            for selector in content_selectors:
                content_area = soup.select_one(selector)
                if content_area:
                    break
            
            if content_area:
                text = content_area.get_text(separator='\n', strip=True)
                # Clean up excessive whitespace
                text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
                
                if len(text) > 800:
                    text = text[:800] + f"\n\n... (content truncated - showing first 800 of {len(text)} characters)"
                
                tier_indicator = {
                    "tier_1_official": "🏛 **OFFICIAL DOCUMENTATION**",
                    "tier_2_educational": "🎓 **EDUCATIONAL CONTENT**", 
                    "tier_3_community": "👥 **COMMUNITY CONTENT**",
                    "tier_4_blogs": "📝 **BLOG CONTENT**",
                    "general": " **GENERAL WEB SEARCH**"
                }.get(tier, " **WEB CONTENT**")
                
                return f"{tier_indicator}\n**Source**: {title}\n**URL**: {url}\n\n{text}"
            return None
            
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL error scraping {url}: {e}")
            return f" SSL connection failed for {url}"
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error scraping {url}: {e}")
            return f" Connection failed for {url}"
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout scraping {url}: {e}")
            return f" Request timeout for {url}"
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None

