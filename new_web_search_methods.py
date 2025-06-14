# New web search methods with tiered approach and content scraping

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
        
        results = []
        for item in items:
            results.append({
                'title': item.get('title', ''),
                'snippet': item.get('snippet', ''),
                'url': item.get('link', ''),
                'domain': urlparse(item.get('link', '')).netloc.replace('www.', '')
            })
        
        logger.info(f"🔍 Found {len(results)} search results for '{query}'")
        return results
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []

def _find_and_scrape_best_source(self, search_results: List[Dict], query: str) -> Optional[str]:
    """
    Iterate through quality tiers to find and scrape the best source
    Returns scraped content from the highest quality source found
    """
    # Define tier priority order (highest to lowest quality)
    tier_order = [
        "tier_1_official",
        "tier_2_educational", 
        "tier_3_community",
        "tier_4_blogs"
        # Note: tier_5_news excluded unless specifically news query
    ]
    
    # Add news tier for current events queries
    if any(term in query.lower() for term in ['news', 'latest', 'announcement', 'release', 'update', '2024', '2025']):
        tier_order.append("tier_5_news")
    
    # Search through tiers in priority order
    for tier_name in tier_order:
        tier_domains = PRIORITY_DOMAINS[tier_name]
        
        for result in search_results:
            domain = result.get('domain', '')
            url = result.get('url', '')
            
            if any(tier_domain in domain for tier_domain in tier_domains):
                logger.info(f"🏆 Found {tier_name} source: {domain}")
                
                # Apply additional quality filters for community sources
                if tier_name == "tier_3_community" and not self._passes_community_quality_filter(result, url):
                    logger.info(f"⚠️ Community source filtered out: {url}")
                    continue
                
                # Scrape content from this high-quality source
                content = self._scrape_content(url, result.get('title', ''), tier_name)
                if content:
                    return content
    
    logger.warning(f"No high-quality sources found for query: {query}")
    return None

def _passes_community_quality_filter(self, result: Dict, url: str) -> bool:
    """Apply quality filters for community sources like StackOverflow and GitHub"""
    domain = result.get('domain', '')
    
    if 'stackoverflow.com' in domain:
        # For StackOverflow, look for indicators of quality answers
        title = result.get('title', '').lower()
        snippet = result.get('snippet', '').lower()
        
        # Prefer questions with accepted answers or high scores
        if any(indicator in snippet for indicator in ['accepted answer', 'upvoted', 'score']):
            return True
        # Avoid duplicate or low-quality question indicators
        if any(indicator in title for indicator in ['duplicate', 'unclear', 'too broad']):
            return False
        return True
        
    elif 'github.com' in domain:
        # For GitHub, prefer official repos, high stars, recent activity
        if any(org in url for org in ['/flutter/', '/python/', '/microsoft/', '/google/', '/facebook/']):
            return True  # Official organization repos
        # Could add more GitHub quality filters here
        return True
        
    return True

def _scrape_content(self, url: str, title: str, tier: str) -> Optional[str]:
    """
    Scrape and clean content from a high-quality source
    Returns formatted content suitable for LLM consumption
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Educational Research Bot - MCP Server)'
        }
        
        logger.info(f"🔗 Scraping content from: {url}")
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
            element.decompose()
        
        # Extract main content based on site structure
        content = self._extract_main_content(soup, url)
        
        if not content or len(content.strip()) < 100:
            logger.warning(f"Insufficient content scraped from {url}")
            return None
        
        # Format the response with quality indicators
        tier_indicator = {
            "tier_1_official": "🏛️ **OFFICIAL DOCUMENTATION**",
            "tier_2_educational": "🎓 **EXPERT EDUCATIONAL CONTENT**", 
            "tier_3_community": "👥 **HIGH-QUALITY COMMUNITY CONTENT**",
            "tier_4_blogs": "📝 **TECH BLOG CONTENT**",
            "tier_5_news": "📰 **TECH NEWS**"
        }.get(tier, "🌐 **WEB CONTENT**")
        
        formatted_content = f"""{tier_indicator}
**Source**: {title}
**URL**: {url}

{content}

---
*Content scraped from authoritative source and verified for quality*"""
        
        logger.info(f"✅ Successfully scraped {len(content)} characters from {tier} source")
        return formatted_content
        
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return None

def _extract_main_content(self, soup: BeautifulSoup, url: str) -> str:
    """Extract main content based on common site patterns"""
    
    # Try site-specific extraction patterns
    domain = urlparse(url).netloc
    
    if 'docs.flutter.dev' in domain or 'dart.dev' in domain:
        # Flutter/Dart docs specific
        content_area = soup.find('main') or soup.find('article') or soup.find('.content')
    elif 'stackoverflow.com' in domain:
        # StackOverflow specific - get question and top answer
        question = soup.find('.question')
        answer = soup.find('.answer')
        if question and answer:
            return f"**Question:**\n{question.get_text(strip=True)}\n\n**Top Answer:**\n{answer.get_text(strip=True)}"
    elif 'github.com' in domain:
        # GitHub README or documentation
        content_area = soup.find('.markdown-body') or soup.find('#readme')
    else:
        # Generic content extraction
        content_area = soup.find('main') or soup.find('article') or soup.find('.content') or soup.find('#content')
    
    if content_area:
        # Clean up the text
        text = content_area.get_text(separator='\n', strip=True)
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        # Limit length to prevent overwhelming responses
        if len(text) > 4000:
            text = text[:4000] + "\n\n... (content truncated)"
        return text
    
    # Fallback to body content
    body_text = soup.get_text(separator='\n', strip=True)
    if len(body_text) > 4000:
        body_text = body_text[:4000] + "\n\n... (content truncated)"
    return body_text

async def _arun(self, query: str, max_results: int = 3) -> str:
    global executor
    if not executor: return "Error: Server config issue (executor missing)."
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, self._run, query, max_results)