#!/usr/bin/env python3
"""
Test script to verify agent parsing error fix
Tests the handle_parsing_errors parameter change
"""

import sys
import os
from langchain_community.chat_models import ChatOllama
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub
from langchain_core.messages import HumanMessage

# Add project root to path
sys.path.insert(0, '/mnt/caseSSD/mcp_server_project')

def test_agent_parsing_with_string():
    """Test agent with string handle_parsing_errors (current broken behavior)"""
    print("🧪 Testing agent with STRING handle_parsing_errors...")
    
    try:
        llm = ChatOllama(model="qwen3:30b-a3b", base_url="http://localhost:11434")
        base_prompt = hub.pull("hwchase17/react")
        
        # Create a simple mock tool
        from langchain.tools import Tool
        
        def mock_tool(query: str) -> str:
            return f"Mock result for: {query}"
        
        tools = [Tool(
            name="mock_tool",
            description="A mock tool for testing",
            func=mock_tool
        )]
        
        agent = create_react_agent(llm, tools, base_prompt)
        
        # Test with STRING (current broken config)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=3,  # Limit iterations to prevent infinite loops
            handle_parsing_errors="Check messages and try to recover, or output the parsing error directly to the user."
        )
        
        result = agent_executor.invoke({"input": "test query"})
        print(f"✅ STRING config result: {result}")
        return True
        
    except Exception as e:
        print(f"❌ STRING config failed: {e}")
        return False

def test_agent_parsing_with_boolean():
    """Test agent with boolean handle_parsing_errors (proposed fix)"""
    print("\n🧪 Testing agent with BOOLEAN handle_parsing_errors...")
    
    try:
        llm = ChatOllama(model="qwen3:30b-a3b", base_url="http://localhost:11434")
        base_prompt = hub.pull("hwchase17/react")
        
        # Create a simple mock tool
        from langchain.tools import Tool
        
        def mock_tool(query: str) -> str:
            return f"Mock result for: {query}"
        
        tools = [Tool(
            name="mock_tool",
            description="A mock tool for testing",
            func=mock_tool
        )]
        
        agent = create_react_agent(llm, tools, base_prompt)
        
        # Test with BOOLEAN (proposed fix)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=3,  # Limit iterations to prevent infinite loops
            handle_parsing_errors=True
        )
        
        result = agent_executor.invoke({"input": "test query"})
        print(f"✅ BOOLEAN config result: {result}")
        return True
        
    except Exception as e:
        print(f"❌ BOOLEAN config failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Agent Parsing Error Fix Tests")
    print("=" * 60)
    
    # Test current broken config
    string_works = test_agent_parsing_with_string()
    
    # Test proposed fix
    boolean_works = test_agent_parsing_with_boolean()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS:")
    print(f"String handle_parsing_errors: {'✅ WORKS' if string_works else '❌ FAILS (as expected)'}")
    print(f"Boolean handle_parsing_errors: {'✅ WORKS' if boolean_works else '❌ FAILS'}")
    
    if boolean_works and not string_works:
        print("\n🎉 FIX CONFIRMED! Boolean config works, string config fails.")
        print("💡 Safe to apply fix: change string to True in orchestrator.py line 609")
    elif boolean_works and string_works:
        print("\n🤔 Both configs work - need deeper investigation")
    else:
        print("\n💥 Neither config works - different problem")