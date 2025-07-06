#!/usr/bin/env python3
"""
Test script to verify memory architecture fix
Tests that save_interaction only writes to Redis (Tier 1) as per specification
"""

import sys
import os
import json
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/mnt/caseSSD/mcp_server_project')

from tools.knowledge import mcp_save_interaction
import redis

def test_redis_only_memory_save():
    """Test that memory saving only writes to Redis and doesn't overload it"""
    print("🧪 Testing memory architecture fix...")
    
    # Test messages
    test_messages = [
        {"role": "user", "content": "Test message for memory architecture fix"},
        {"role": "assistant", "content": "This is a test response to verify Redis-only saving"}
    ]
    
    test_tags = {"test": "architecture_fix", "purpose": "verify_redis_only"}
    
    # Connect to Redis to monitor
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    try:
        # Check Redis connection
        redis_client.ping()
        print("✅ Redis connection successful")
        
        # Get initial key count
        initial_keys = len(redis_client.keys("interaction:*"))
        print(f"📊 Initial Redis interaction keys: {initial_keys}")
        
        # Test memory save
        print("💾 Testing memory save...")
        start_time = time.time()
        
        result = mcp_save_interaction(test_messages, test_tags)
        
        save_time = time.time() - start_time
        print(f"⏱️  Save operation took: {save_time:.3f} seconds")
        
        # Check result
        if result.get("status") == "success":
            print("✅ Memory save succeeded")
            interaction_id = result.get("interaction_id")
            print(f"📝 Interaction ID: {interaction_id}")
            
            # Verify only Redis was used
            if result.get("tier") == "redis":
                print("✅ Confirmed: Only Redis (Tier 1) was used")
            else:
                print(f"❌ ERROR: Expected tier='redis', got tier='{result.get('tier')}'")
                return False
            
            # Check Redis keys increased by exactly 1
            final_keys = len(redis_client.keys("interaction:*"))
            print(f"📊 Final Redis interaction keys: {final_keys}")
            
            if final_keys == initial_keys + 1:
                print("✅ Confirmed: Exactly 1 new Redis key created")
            else:
                print(f"❌ ERROR: Expected {initial_keys + 1} keys, got {final_keys}")
                return False
            
            # Verify the saved data
            saved_data = redis_client.get(f"interaction:{interaction_id}")
            if saved_data:
                data = json.loads(saved_data)
                if "messages" in data and "metadata" in data:
                    print("✅ Confirmed: Saved data structure is correct")
                else:
                    print("❌ ERROR: Saved data missing required fields")
                    return False
            else:
                print("❌ ERROR: Could not retrieve saved data from Redis")
                return False
                
        else:
            print(f"❌ Memory save failed: {result.get('error')}")
            return False
            
        print("✅ All tests passed! Memory architecture fix is working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    finally:
        redis_client.close()

def test_redis_bgsave():
    """Test that Redis can perform BGSAVE without errors"""
    print("\n🔧 Testing Redis BGSAVE capability...")
    
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    try:
        # Test BGSAVE
        result = redis_client.bgsave()
        print(f"✅ BGSAVE command successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ BGSAVE failed: {e}")
        return False
    finally:
        redis_client.close()

if __name__ == "__main__":
    print("🚀 Starting Memory Architecture Fix Tests")
    print("=" * 50)
    
    # Test 1: Memory save only uses Redis
    test1_passed = test_redis_only_memory_save()
    
    # Test 2: Redis BGSAVE works
    test2_passed = test_redis_bgsave()
    
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS:")
    print(f"Memory Save (Redis Only): {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Redis BGSAVE: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED! Memory architecture fix is successful.")
        sys.exit(0)
    else:
        print("\n💥 SOME TESTS FAILED! Fix needs more work.")
        sys.exit(1)