#!/usr/bin/env python3
"""
Test script to verify that /rule slash command functionality works
Tests the theory that slash commands work independently of LangchainMemoryRuleTool
"""

import sys
import os

# Add project root to path
sys.path.insert(0, '/mnt/caseSSD/mcp_server_project')

def test_rule_slash_command():
    """Test that /rule slash command processing works"""
    print("Testing /rule slash command functionality...")
    
    try:
        # Import the slash command processor
        from tools.knowledge import process_slash_command
        print("✓ Successfully imported process_slash_command")
        
        # Test the slash command with a sample rule
        test_rule = "I prefer detailed code explanations"
        result = process_slash_command("/rule", test_rule, {})
        
        print(f"✓ Slash command result: {result}")
        
        # Check if it was successful
        if "[PASS]" in result:
            print("✓ /rule slash command appears to work correctly")
            return True
        else:
            print("✗ /rule slash command returned an error")
            return False
            
    except ImportError as e:
        if "LangchainMemoryRuleTool" in str(e):
            print("✗ Import failed due to missing LangchainMemoryRuleTool")
            print("  This confirms the tool class is missing but slash command might still work")
        else:
            print(f"✗ Unexpected import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_memory_system_direct():
    """Test that the underlying memory system works"""
    print("\nTesting direct memory system functionality...")
    
    try:
        from tools.knowledge import get_memory_system
        
        memory_system = get_memory_system()
        print("✓ Successfully got memory system instance")
        
        # Test adding a rule directly
        result = memory_system.add_permanent_rule("Test rule for verification")
        print(f"✓ Direct memory system result: {result}")
        
        if result.get("status") == "success":
            print("✓ Direct memory system works correctly")
            return True
        else:
            print("✗ Direct memory system returned an error")
            return False
            
    except Exception as e:
        print(f"✗ Direct memory system test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Testing /rule functionality ===")
    
    # Test 1: Direct memory system
    memory_works = test_memory_system_direct()
    
    # Test 2: Slash command processing
    slash_works = test_rule_slash_command()
    
    print(f"\n=== Results ===")
    print(f"Memory system: {'✓ WORKS' if memory_works else '✗ BROKEN'}")
    print(f"Slash command: {'✓ WORKS' if slash_works else '✗ BROKEN'}")
    
    if memory_works and slash_works:
        print("\n🎉 Theory confirmed: /rule works without LangchainMemoryRuleTool")
    else:
        print("\n❌ Theory disproven: Something is broken")