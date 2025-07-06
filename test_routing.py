#!/usr/bin/env python3
"""Test the routing logic for simple greetings"""

from core.orchestrator import get_tool_recommendations

# Test what tools are recommended for 'hello'
recommendations = get_tool_recommendations('hello')
print('Tool recommendations for hello:', recommendations)

# Check if any non-memory tools are needed
non_memory_tools = [k for k, v in recommendations.items() if k != 'memory' and v]
print('Non-memory tools needed:', non_memory_tools)

# Check if only memory tools are needed
only_memory_needed = len(non_memory_tools) == 0
print('Only memory tools needed:', only_memory_needed)