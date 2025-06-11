#!/usr/bin/env python3
# Configure Ollama with Function Calling

import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"

def test_ollama_function_calling():
    """Test function calling with qwen3:8b"""
    
    # Load function definition
    with open('flutter_docs_function.json', 'r') as f:
        flutter_function = json.load(f)
    
    # Test message with function
    payload = {
        "model": "qwen3:8b",
        "messages": [
            {
                "role": "user", 
                "content": "How do I create a custom StatefulWidget in Flutter?"
            }
        ],
        "tools": [flutter_function],
        "stream": False
    }
    
    logger.info("Testing Ollama function calling...")
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE}/v1/chat/completions",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        logger.info("Function calling test successful!")
        
        # Check if function was called
        choice = result.get('choices', [{}])[0]
        message = choice.get('message', {})
        
        if 'tool_calls' in message:
            logger.info("✅ Function calling is working!")
            logger.info(f"Tool calls: {message['tool_calls']}")
        else:
            logger.info("ℹ️  Direct response (no function call needed)")
            logger.info(f"Response: {message.get('content', '')[:200]}...")
            
        return True
        
    except Exception as e:
        logger.error(f"Function calling test failed: {e}")
        return False

def setup_ollama_function_endpoint():
    """Set up Ollama to handle function execution"""
    
    # For now, we'll use a simple test
    # In production, you'd configure Ollama to call your function server
    
    logger.info("Setting up Ollama function calling...")
    
    # Test basic connectivity
    try:
        response = requests.get(f"{OLLAMA_BASE}/api/version")
        response.raise_for_status()
        logger.info(f"✅ Ollama is running: {response.json()}")
        
        # Test if qwen3:8b is available
        tags_response = requests.get(f"{OLLAMA_BASE}/api/tags")
        tags_response.raise_for_status()
        models = [model['name'] for model in tags_response.json().get('models', [])]
        
        if 'qwen3:8b' in models:
            logger.info("✅ qwen3:8b is available")
        else:
            logger.warning("⚠️  qwen3:8b not found. Available models:", models)
            
        return True
        
    except Exception as e:
        logger.error(f"Ollama setup failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("=== Setting up Ollama Function Calling ===")
    
    if setup_ollama_function_endpoint():
        logger.info("✅ Ollama setup complete")
        
        if test_ollama_function_calling():
            logger.info("✅ Function calling is ready!")
            logger.info("Next steps:")
            logger.info("1. Start function server: python ollama_function_server.py")
            logger.info("2. Test in Open WebUI with Flutter questions")
        else:
            logger.error("❌ Function calling test failed")
    else:
        logger.error("❌ Ollama setup failed")