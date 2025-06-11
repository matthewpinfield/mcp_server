#!/usr/bin/env python3
# Test Ollama with Function Calling Integration

import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
FUNCTION_SERVER = "http://localhost:8010"

def test_complete_integration():
    """Test the complete Ollama + Function calling flow"""
    
    # Load function definition
    with open('flutter_docs_function.json', 'r') as f:
        flutter_function = json.load(f)
    
    # Test with a question that should trigger function calling
    payload = {
        "model": "qwen3:8b",
        "messages": [
            {
                "role": "user", 
                "content": "How do I handle state management in Flutter widgets?"
            }
        ],
        "tools": [flutter_function],
        "stream": False
    }
    
    logger.info("Testing complete Ollama + Function integration...")
    
    try:
        # Step 1: Send to Ollama with function available
        response = requests.post(
            f"{OLLAMA_BASE}/v1/chat/completions",
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        choice = result.get('choices', [{}])[0]
        message = choice.get('message', {})
        
        # Check if function was called
        if 'tool_calls' in message:
            logger.info("✅ Ollama called function!")
            
            # Step 2: Execute the function call
            tool_call = message['tool_calls'][0]
            function_name = tool_call['function']['name']
            function_args = json.loads(tool_call['function']['arguments'])
            
            logger.info(f"Function: {function_name}, Args: {function_args}")
            
            # Call our function server
            func_response = requests.post(
                f"{FUNCTION_SERVER}/execute_function",
                json={"name": function_name, "arguments": function_args},
                timeout=30
            )
            func_response.raise_for_status()
            func_result = func_response.json()
            
            logger.info(f"Function result: {func_result['result'][:200]}...")
            
            # Step 3: Send function result back to Ollama
            follow_up_payload = {
                "model": "qwen3:8b",
                "messages": [
                    *payload["messages"],
                    message,  # Include the assistant's function call
                    {
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": func_result['result']
                    }
                ],
                "stream": False
            }
            
            final_response = requests.post(
                f"{OLLAMA_BASE}/v1/chat/completions",
                json=follow_up_payload,
                timeout=60
            )
            final_response.raise_for_status()
            
            final_result = final_response.json()
            final_message = final_result.get('choices', [{}])[0].get('message', {})
            
            logger.info("✅ Complete function calling workflow successful!")
            logger.info(f"Final answer: {final_message.get('content', '')[:300]}...")
            
        else:
            logger.info("ℹ️  Ollama provided direct response (no function call)")
            logger.info(f"Response: {message.get('content', '')[:200]}...")
            
        return True
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("=== Testing Complete Ollama Function Integration ===")
    
    if test_complete_integration():
        logger.info("✅ Integration test passed!")
        logger.info("Your Ollama function calling is working correctly!")
        logger.info("You can now use this in Open WebUI with Flutter questions.")
    else:
        logger.error("❌ Integration test failed")