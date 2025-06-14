#!/usr/bin/env python3
"""Test MCP server web search via HTTP requests"""

import requests
import json
import time

def test_mcp_web_search():
    """Test web search through the running MCP server"""
    
    # MCP server endpoint
    mcp_url = "http://localhost:8013"
    
    # Test queries that often cause issues
    test_queries = [
        "latest blender version official",
        "Flutter 3.19 new features",
        "reddit flutter best practices", 
        "github copilot pricing 2024",
        "discord bot python tutorial"
    ]
    
    print("🧪 Testing MCP Web Search via HTTP")
    print("=" * 50)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📍 Test {i}/5: '{query}'")
        print("-" * 40)
        
        # Create MCP request payload
        payload = {
            "method": "call_tool",
            "params": {
                "name": "web_search",
                "arguments": {
                    "query": query,
                    "max_results": 3
                }
            }
        }
        
        try:
            # Send request to MCP server
            response = requests.post(
                f"{mcp_url}/mcp",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("result", {}).get("content", "")
                
                # Analyze response
                if not content:
                    print("❌ FAIL: Empty response")
                elif "No high-quality authoritative sources found" in content:
                    print("✅ PASS: Proper error handling")
                    print(f"   Details: {content[:200]}...")
                elif "SSL connection failed" in content or "Connection failed" in content:
                    print("✅ PASS: Connection error handled")
                    print(f"   Error: {content[:200]}...")
                elif len(content) > 500:
                    print("✅ PASS: Content retrieved successfully")
                    print(f"   Length: {len(content)} chars")
                    print(f"   Preview: {content[:150]}...")
                else:
                    print("⚠️  PARTIAL: Limited content")
                    print(f"   Content: {content[:200]}...")
                    
            else:
                print(f"❌ FAIL: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
        except requests.exceptions.ConnectionError:
            print("❌ FAIL: Cannot connect to MCP server on port 8013")
            print("   Make sure the MCP server is running")
            break
        except requests.exceptions.Timeout:
            print("⚠️  TIMEOUT: Request took longer than 30s")
        except Exception as e:
            print(f"❌ FAIL: {type(e).__name__}: {e}")
        
        # Delay between requests
        time.sleep(2)
    
    print("\n" + "=" * 50)
    print("🏁 MCP Web Search Tests Complete")

if __name__ == "__main__":
    test_mcp_web_search()