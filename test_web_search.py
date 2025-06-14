#!/usr/bin/env python3
"""Test script for web search functionality with difficult queries"""

import asyncio
import sys
import os
sys.path.append('.')

# Environment variables should be set externally, not hardcoded
# export GOOGLE_CSE_ID=your_cse_id
# export GOOGLE_API_KEY=your_api_key

from advanced_mcp_server import LangchainWebSearchTool

async def test_difficult_searches():
    """Test web search with challenging queries that often fail"""
    
    tool = LangchainWebSearchTool()
    
    # Test cases with expected failure modes
    test_queries = [
        # SSL/Connection issues
        "latest blender version official",
        
        # Rate limiting prone
        "github copilot pricing 2024",
        
        # Often blocked sites
        "reddit flutter state management best practices",
        
        # Very specific/recent queries
        "Flutter 3.19 widget tree performance improvements",
        
        # Queries that might return low-quality results
        "obscure python metaclass debugging techniques",
        
        # Generic queries that get poor results
        "how to code",
        
        # Queries with special characters
        "C++ vs Rust performance 2024",
        
        # Queries likely to hit community sites with SSL issues
        "discord bot development python tutorial"
    ]
    
    print("🧪 Testing Web Search Error Handling")
    print("=" * 50)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📍 Test {i}/8: '{query}'")
        print("-" * 40)
        
        try:
            result = await tool._arun(query, max_results=3)
            
            # Analyze result quality
            if not result or result.strip() == "":
                print("❌ FAIL: Empty result")
            elif result.startswith("Error: Server config"):
                print("⚠️  SKIP: Server config issue (executor missing)")
            elif "No high-quality authoritative sources found" in result:
                print("✅ PASS: Proper error handling - no good sources")
                print(f"   Error details: {result[:200]}...")
            elif "SSL connection failed" in result or "Connection failed" in result:
                print("✅ PASS: Proper SSL/connection error handling")
                print(f"   Error details: {result[:200]}...")
            elif len(result) > 500:  # Good content found
                print("✅ PASS: Successfully retrieved content")
                print(f"   Content length: {len(result)} chars")
                print(f"   Preview: {result[:150]}...")
            else:
                print("⚠️  PARTIAL: Limited content retrieved")
                print(f"   Content: {result[:200]}...")
                
        except Exception as e:
            print(f"❌ FAIL: Exception raised - {type(e).__name__}: {e}")
        
        # Small delay between tests
        await asyncio.sleep(1)
    
    print("\n" + "=" * 50)
    print("🏁 Web Search Error Handling Tests Complete")

if __name__ == "__main__":
    asyncio.run(test_difficult_searches())