#!/usr/bin/env python3
"""
Test file to validate Qwen3 thinking implementation approaches
Tests different methods to see what actually works with Ollama
"""

import asyncio
import requests
import json
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

OLLAMA_API_BASE = "http://localhost:11434"
MODEL = "qwen3:30b-a3b"

def test_direct_ollama_api():
    """Test 1: Direct Ollama API with /think and /no_think tags"""
    print("=== Test 1: Direct Ollama API ===")
    
    # Test with /think
    think_payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "/think What is 2+2? Think step by step."}
        ],
        "stream": False
    }
    
    print("Testing /think mode...")
    response = requests.post(f"{OLLAMA_API_BASE}/api/chat", json=think_payload)
    think_result = response.json()
    print(f"Response: {think_result['message']['content'][:200]}...")
    print(f"Has <think> tags: {'<think>' in think_result['message']['content']}")
    print()
    
    # Test with /no_think
    no_think_payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "/no_think What is 2+2?"}
        ],
        "stream": False
    }
    
    print("Testing /no_think mode...")
    response = requests.post(f"{OLLAMA_API_BASE}/api/chat", json=no_think_payload)
    no_think_result = response.json()
    print(f"Response: {no_think_result['message']['content'][:200]}...")
    print(f"Has <think> tags: {'<think>' in no_think_result['message']['content']}")
    print()

async def test_langchain_ollama():
    """Test 2: LangChain ChatOllama with /think and /no_think tags"""
    print("=== Test 2: LangChain ChatOllama ===")
    
    llm = ChatOllama(
        model=MODEL,
        base_url=OLLAMA_API_BASE,
        temperature=0.7
    )
    
    # Test with /think
    print("Testing /think mode with LangChain...")
    think_response = await llm.ainvoke([HumanMessage(content="/think What is 2+2? Think step by step.")])
    print(f"Response: {think_response.content[:200]}...")
    print(f"Has <think> tags: {'<think>' in think_response.content}")
    print()
    
    # Test with /no_think
    print("Testing /no_think mode with LangChain...")
    no_think_response = await llm.ainvoke([HumanMessage(content="/no_think What is 2+2?")])
    print(f"Response: {no_think_response.content[:200]}...")
    print(f"Has <think> tags: {'<think>' in no_think_response.content}")
    print()

def test_ollama_parameters():
    """Test 3: Check if Ollama exposes thinking-related parameters"""
    print("=== Test 3: Ollama Parameters ===")
    
    # Test with additional parameters
    think_payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "What is 2+2? Think step by step."}
        ],
        "stream": False,
        "options": {
            "enable_thinking": True  # Test if this parameter exists
        }
    }
    
    print("Testing enable_thinking parameter...")
    try:
        response = requests.post(f"{OLLAMA_API_BASE}/api/chat", json=think_payload)
        result = response.json()
        if 'error' in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Response: {result['message']['content'][:200]}...")
            print(f"Has <think> tags: {'<think>' in result['message']['content']}")
    except Exception as e:
        print(f"Exception: {e}")
    print()

def test_system_message_approach():
    """Test 4: Using system messages to control thinking"""
    print("=== Test 4: System Message Approach ===")
    
    # Test with system message
    system_payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You should use <think></think> tags for internal reasoning."},
            {"role": "user", "content": "What is 2+2? Think step by step."}
        ],
        "stream": False
    }
    
    print("Testing system message approach...")
    response = requests.post(f"{OLLAMA_API_BASE}/api/chat", json=system_payload)
    result = response.json()
    print(f"Response: {result['message']['content'][:200]}...")
    print(f"Has <think> tags: {'<think>' in result['message']['content']}")
    print()

def test_baseline_behavior():
    """Test 5: Baseline - no thinking instructions"""
    print("=== Test 5: Baseline Behavior ===")
    
    baseline_payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "What is 2+2?"}
        ],
        "stream": False
    }
    
    print("Testing baseline (no thinking instructions)...")
    response = requests.post(f"{OLLAMA_API_BASE}/api/chat", json=baseline_payload)
    result = response.json()
    print(f"Response: {result['message']['content'][:200]}...")
    print(f"Has <think> tags: {'<think>' in result['message']['content']}")
    print()

async def run_all_tests():
    """Run all tests and compare results"""
    print("🧪 Testing Qwen3 Thinking Implementation Approaches")
    print("=" * 60)
    
    test_direct_ollama_api()
    await test_langchain_ollama()
    test_ollama_parameters()
    test_system_message_approach()
    test_baseline_behavior()
    
    print("=" * 60)
    print("✅ All tests completed. Review results to determine best approach.")

if __name__ == "__main__":
    asyncio.run(run_all_tests())