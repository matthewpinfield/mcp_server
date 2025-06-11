#!/usr/bin/env python3
# Debug script to see exactly what the RAG server returns

import requests
import json

RAG_SERVER_ENDPOINT = "http://localhost:8008/custom_rag_stuff"

def debug_rag_response():
    query = "What is Flutter?"
    
    print("=== Debugging RAG Server Response ===")
    print(f"Endpoint: {RAG_SERVER_ENDPOINT}")
    print(f"Query: {query}")
    print()
    
    try:
        response = requests.post(
            RAG_SERVER_ENDPOINT,
            json={"fullInput": query},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'Not specified')}")
        print(f"Content-Length: {len(response.content)} bytes")
        print()
        
        print("=== Raw Response Headers ===")
        for key, value in response.headers.items():
            print(f"{key}: {value}")
        print()
        
        print("=== Raw Response Content (first 500 chars) ===")
        print(repr(response.text[:500]))
        print()
        
        print("=== Attempting JSON Parse ===")
        try:
            json_data = response.json()
            print("✅ Successfully parsed as JSON!")
            print(f"JSON type: {type(json_data)}")
            print(f"JSON keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'Not a dict'}")
            print(f"JSON preview: {str(json_data)[:200]}...")
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode failed: {e}")
            print(f"Failed at position: {e.pos}")
            if hasattr(e, 'lineno'):
                print(f"Line: {e.lineno}, Column: {e.colno}")
                
        print("\n=== Full Response Text ===")
        print(response.text)
        
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    debug_rag_response()