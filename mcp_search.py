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

# Import base classes (these need to be available from the main server)
from langchain.tools import BaseTool as LangchainBaseTool

logger = logging.getLogger(__name__)

# Schema for web search parameters
class WebSearchSchema(BaseModel):
    query: str = Field(description="Search query for web search using Google/Bing. Be specific and include relevant keywords.")
    max_results: int = Field(description="Maximum number of search results to return", default=5)
    general_search: bool = Field(description="If True, searches all websites without domain filtering. If False, prioritizes technical/programming sources.", default=False)

# Google Custom Search API configuration
GOOGLE_API_KEY = "***REMOVED-GOOGLE-API-KEY***"
GOOGLE_SEARCH_ENGINE_ID = "948e280aa8f4544c5"

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

class LangchainWebSearchTool(LangchainBaseTool):
    name: str = "search_web"
    description: str = (
        "Searches the web and returns HIGH-QUALITY, AUTHORITATIVE content from trusted sources. "
        "Prioritizes official documentation, expert educational content, and reputable community sources. "
        "Returns actual scraped content, not just search result summaries. "
        "Use for: current information, latest versions, authoritative guides, official best practices."
    )
    args_schema: Type[BaseModel] = WebSearchSchema

    def _run(self, query: str, max_results: int = 3, general_search: bool = False) -> str:
        logger.info(f"🔍 High-Quality Web Search: query='{query}', max_results={max_results}")
        try:
            # Get initial search results
            search_results = self._get_search_results(query, max_results * 3)
            
            if not search_results:
                return f"No search results found for query: '{query}'"
            
            # Auto-detect if this is a coding-related query
            is_coding_query = self._is_coding_related_query(query.lower())
            
            # Use domain filtering only for coding queries, general search for everything else
            if general_search or not is_coding_query:
                best_content = self._find_and_scrape_general_source(search_results, query)
                logger.info(f"🌐 Using general search for query: '{query}'")
            else:
                best_content = self._find_and_scrape_best_source(search_results, query)
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
            response = requests.get(url, params=params, timeout=15)
            
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

    def _find_and_scrape_best_source(self, search_results: List[Dict], query: str) -> Optional[str]:
        """Find and scrape the best source from search results with improved error handling"""
        tier_order = ["tier_1_official", "tier_2_educational", "tier_3_community", "tier_4_blogs"]
        failed_sources = []
        partial_content = []
        
        for tier_name in tier_order:
            tier_domains = PRIORITY_DOMAINS[tier_name]
            for result in search_results:
                href = result.get('href', '')
                if not href:
                    continue
                
                try:
                    domain = urlparse(href).netloc.replace('www.', '')
                    if any(tier_domain in domain for tier_domain in tier_domains):
                        logger.info(f"🏆 Found {tier_name} source: {domain}")
                        content = self._scrape_content(href, result.get('title', ''), tier_name)
                        
                        if content:
                            if content.startswith("❌"):  # Error message from scraping
                                failed_sources.append(f"{domain}: {content}")
                                continue
                            elif len(content.strip()) > 200:  # Good content threshold
                                logger.info(f"✅ Successfully scraped from {tier_name}: {domain}")
                                return content
                            else:
                                partial_content.append(f"{domain}: {content[:100]}...")
                        
                        logger.warning(f"⚠️ No usable content from {domain}")
                        
                except Exception as e:
                    logger.debug(f"Error parsing URL {href}: {e}")
                    failed_sources.append(f"{href}: Parse error")
                    continue
        
        # If no good sources found, return summary of what was tried
        if failed_sources or partial_content:
            summary = f"No high-quality authoritative sources found for: '{query}'. "
            summary += "Connection issues encountered:\n"
            
            for error in failed_sources[:3]:  # Show first 3 failures
                summary += f"• {error}\n"
                
            if partial_content:
                summary += "\nLimited content found:\n"
                for partial in partial_content[:2]:
                    summary += f"• {partial}\n"
            
            summary += "Try refining your search terms or asking about established topics covered in official documentation."
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

    def _find_and_scrape_general_source(self, search_results: List[Dict], query: str) -> Optional[str]:
        """Find and scrape from any source without domain filtering for general queries"""
        # Skip useless sites for general information
        skip_domains = ["youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com", "twitter.com", "x.com"]
        
        for i, result in enumerate(search_results):
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
            
            try:
                logger.info(f"🌐 Trying general source #{i+1}: {href}")
                content = self._scrape_content(href, title, "general")
                
                if content and len(content.strip()) > 200:
                    logger.info(f"✅ Successfully scraped general source: {href}")
                    return content
                    
            except Exception as e:
                logger.debug(f"Failed to scrape {href}: {e}")
                continue
        
        return f"Could not scrape useful content from search results for: '{query}'"

    def _scrape_content(self, url: str, title: str, tier: str) -> Optional[str]:
        """Scrape content from URL with improved error handling"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            logger.info(f"🔗 Scraping content from: {url}")
            
            # Try with SSL verification first, then without if it fails
            for verify_ssl in [True, False]:
                try:
                    response = requests.get(url, headers=headers, timeout=15, verify=verify_ssl)
                    response.raise_for_status()
                    break
                except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                    if verify_ssl:
                        logger.warning(f"SSL error for {url}, retrying without SSL verification")
                        continue
                    else:
                        raise e
            
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
                
                if len(text) > 3000:
                    text = text[:3000] + "\n\n... (content truncated)"
                
                tier_indicator = {
                    "tier_1_official": "🏛️ **OFFICIAL DOCUMENTATION**",
                    "tier_2_educational": "🎓 **EDUCATIONAL CONTENT**", 
                    "tier_3_community": "👥 **COMMUNITY CONTENT**",
                    "tier_4_blogs": "📝 **BLOG CONTENT**",
                    "general": "🌐 **GENERAL WEB SEARCH**"
                }.get(tier, "🌐 **WEB CONTENT**")
                
                return f"{tier_indicator}\n**Source**: {title}\n**URL**: {url}\n\n{text}"
            return None
            
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL error scraping {url}: {e}")
            return f"❌ SSL connection failed for {url}"
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error scraping {url}: {e}")
            return f"❌ Connection failed for {url}"
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout scraping {url}: {e}")
            return f"❌ Request timeout for {url}"
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None

    async def _arun(self, query: str, max_results: int = 5, general_search: bool = False) -> str:
        # For async execution if needed
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run, query, max_results, general_search)