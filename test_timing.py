#!/usr/bin/env python3
"""
Test script to check lancedb timing with detailed logging
"""

import requests
import time
import json


def test_request(prompt, timeout=30):
    url = "http://localhost:8013/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "qwen3:30b-a3b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    print(f"\n=== Testing: {prompt} ===")
    start_time = time.time()
    print(f"Start time: {time.strftime('%H:%M:%S', time.localtime(start_time))}")

    try:
        response = requests.post(url, headers=headers, json=data, timeout=timeout)
        end_time = time.time()
        duration = end_time - start_time

        print(f"End time: {time.strftime('%H:%M:%S', time.localtime(end_time))}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            content = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "No content")
            )
            print(f"Response length: {len(content)} chars")
            print(f"First 100 chars: {content[:100]}")
        else:
            print(f"Error: {response.text}")

    except requests.exceptions.Timeout:
        end_time = time.time()
        duration = end_time - start_time
        print(f"TIMEOUT after {duration:.2f} seconds")

    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"ERROR after {duration:.2f} seconds: {e}")


if __name__ == "__main__":
    print("MCP Server Timing Test")
    print("=" * 50)

    # Test simple request
    test_request("hello", 15)

    # Test memory search (LanceDB)
    test_request("recall our previous conversation about Flutter widgets", 20)

    # Test complex memory search
    test_request(
        "search my memories for any discussions about state management and API calls",
        30,
    )
