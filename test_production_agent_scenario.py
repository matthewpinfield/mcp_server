#!/usr/bin/env python3
"""
Test production agent scenario to reproduce parsing error loops
"""

import sys
import os
from langchain_community.chat_models import ChatOllama
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub

# Add project root to path
sys.path.insert(0, '/mnt/caseSSD/mcp_server_project')

from tools.knowledge import RAGQueryTool, MemoryManagementTool
from tools.web import WebSearchTool

def test_production_scenario():
    """Test with actual production tools and query that caused the issue"""
    print("🧪 Testing PRODUCTION scenario with actual tools...")
    
    try:
        llm = ChatOllama(model="qwen3:30b-a3b", base_url="http://localhost:11434")
        base_prompt = hub.pull("hwchase17/react")
        
        # Use actual production tools that were causing the issue
        tools = [
            RAGQueryTool(),
            MemoryManagementTool(), 
            WebSearchTool()
        ]
        
        agent = create_react_agent(llm, tools, base_prompt)
        
        print("🔧 Testing with STRING handle_parsing_errors (current production)...")
        agent_executor_string = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=5,  # Limit to prevent infinite loops
            handle_parsing_errors="Check messages and try to recover, or output the parsing error directly to the user."
        )
        
        # Use the exact query that caused the parsing loop
        test_query = "test memory save - what is Flutter?"
        
        print(f"📝 Testing query: '{test_query}'")
        result_string = agent_executor_string.invoke({"input": test_query})
        print(f"✅ STRING result: {result_string.get('output', 'No output')[:100]}...")
        
        print("\n🔧 Testing with BOOLEAN handle_parsing_errors (proposed fix)...")
        agent_executor_bool = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=5,  # Limit to prevent infinite loops  
            handle_parsing_errors=True
        )
        
        result_bool = agent_executor_bool.invoke({"input": test_query})
        print(f"✅ BOOLEAN result: {result_bool.get('output', 'No output')[:100]}...")
        
        return True, True
        
    except Exception as e:
        print(f"❌ Production test failed: {e}")
        return False, False

if __name__ == "__main__":
    print("🚀 Testing PRODUCTION Agent Scenario")
    print("=" * 60)
    
    string_works, bool_works = test_production_scenario()
    
    print("\n" + "=" * 60)
    print("📊 PRODUCTION TEST RESULTS:")
    print(f"String handle_parsing_errors: {'✅ WORKS' if string_works else '❌ FAILS'}")
    print(f"Boolean handle_parsing_errors: {'✅ WORKS' if bool_works else '❌ FAILS'}")
    
    if bool_works and not string_works:
        print("\n🎉 PRODUCTION FIX CONFIRMED!")
    elif bool_works and string_works:
        print("\n🤔 Both work - issue might be elsewhere")
    else:
        print("\n💥 Different issue - not the handle_parsing_errors parameter")