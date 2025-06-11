#!/usr/bin/env python3
"""
Performance Benchmarking Script for MCP Server Optimization
Tests various query types against different server implementations
"""

import asyncio
import httpx
import json
import time
import statistics
from typing import List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

@dataclass
class BenchmarkResult:
    query_type: str
    server_type: str
    response_time: float
    success: bool
    first_chunk_time: float
    total_chunks: int
    error_message: str = ""

class TestQuery:
    def __init__(self, name: str, query: str, expected_type: str):
        self.name = name
        self.query = query
        self.expected_type = expected_type

# Test queries for different scenarios
TEST_QUERIES = [
    # Simple queries (should use direct Ollama bypass)
    TestQuery("simple_greeting", "Hello, how are you?", "simple_direct"),
    TestQuery("simple_question", "What is Python?", "simple_direct"),
    TestQuery("basic_explanation", "Explain machine learning in simple terms", "simple_direct"),
    
    # Flutter/Dart queries (should use RAG)
    TestQuery("flutter_widget", "How do I create a custom Flutter widget?", "rag_required"),
    TestQuery("dart_async", "Explain Dart async and await with examples", "rag_required"),
    TestQuery("flutter_state", "What's the difference between StatefulWidget and StatelessWidget?", "rag_required"),
    TestQuery("flutter_navigation", "How to implement navigation in Flutter apps?", "rag_required"),
    
    # Complex queries (might need agent)
    TestQuery("complex_architecture", "Design a complete Flutter app architecture with state management, routing, and API integration", "complex_agent"),
    TestQuery("multi_step", "Create a Flutter todo app with local storage, search, and categories. Include state management and testing.", "complex_agent"),
]

# Server configurations to test
SERVERS = {
    "original": "http://localhost:8009/api/chat",
    "optimized": "http://localhost:8011/api/chat",
    "baseline_ollama": "http://localhost:11434/v1/chat/completions"  # Direct Ollama for comparison
}

class PerformanceBenchmark:
    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def test_server_response(self, server_url: str, server_name: str, test_query: TestQuery) -> BenchmarkResult:
        """Test a single query against a server"""
        print(f"Testing {server_name}: {test_query.name}")
        
        # Prepare request
        messages = [{"role": "user", "content": test_query.query}]
        payload = {
            "model": "qwen3:8b",
            "messages": messages,
            "stream": True
        }
        
        start_time = time.time()
        first_chunk_time = None
        chunk_count = 0
        success = False
        error_message = ""
        
        try:
            async with self.client.stream('POST', server_url, json=payload) as response:
                if response.status_code != 200:
                    error_message = f"HTTP {response.status_code}"
                    return BenchmarkResult(
                        test_query.expected_type, server_name, 
                        time.time() - start_time, False, 0, 0, error_message
                    )
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk_data = line[6:]
                        
                        if chunk_data == "[DONE]":
                            success = True
                            break
                        
                        try:
                            parsed = json.loads(chunk_data)
                            if parsed.get("choices") and parsed["choices"][0].get("delta"):
                                if first_chunk_time is None:
                                    first_chunk_time = time.time() - start_time
                                chunk_count += 1
                        except json.JSONDecodeError:
                            continue
                
        except asyncio.TimeoutError:
            error_message = "Timeout"
        except Exception as e:
            error_message = str(e)
        
        total_time = time.time() - start_time
        
        return BenchmarkResult(
            test_query.expected_type, 
            server_name, 
            total_time, 
            success, 
            first_chunk_time or total_time, 
            chunk_count, 
            error_message
        )
    
    async def run_benchmark_suite(self) -> Dict[str, List[BenchmarkResult]]:
        """Run comprehensive benchmark suite"""
        print("Starting Performance Benchmark Suite")
        print("=" * 50)
        
        # Test each query against each server
        for test_query in TEST_QUERIES:
            print(f"\nTesting Query: {test_query.name}")
            print(f"Query: {test_query.query[:80]}...")
            print(f"Expected Type: {test_query.expected_type}")
            print("-" * 40)
            
            for server_name, server_url in SERVERS.items():
                try:
                    result = await self.test_server_response(server_url, server_name, test_query)
                    self.results.append(result)
                    
                    status = "✓ SUCCESS" if result.success else f"✗ FAILED ({result.error_message})"
                    print(f"{server_name:15} | {result.response_time:6.2f}s | {result.first_chunk_time:6.2f}s | {result.total_chunks:3d} chunks | {status}")
                    
                    # Small delay between tests
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"{server_name:15} | ERROR: {e}")
                    continue
        
        return self.analyze_results()
    
    def analyze_results(self) -> Dict[str, Dict]:
        """Analyze benchmark results and create summary"""
        analysis = {}
        
        # Group by server
        by_server = {}
        for result in self.results:
            if result.server_type not in by_server:
                by_server[result.server_type] = []
            by_server[result.server_type].append(result)
        
        # Calculate statistics for each server
        for server_name, results in by_server.items():
            successful_results = [r for r in results if r.success]
            
            if not successful_results:
                analysis[server_name] = {
                    "success_rate": 0,
                    "avg_response_time": 0,
                    "avg_first_chunk_time": 0,
                    "total_tests": len(results)
                }
                continue
            
            response_times = [r.response_time for r in successful_results]
            first_chunk_times = [r.first_chunk_time for r in successful_results]
            
            analysis[server_name] = {
                "success_rate": len(successful_results) / len(results) * 100,
                "total_tests": len(results),
                "successful_tests": len(successful_results),
                "avg_response_time": statistics.mean(response_times),
                "median_response_time": statistics.median(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "avg_first_chunk_time": statistics.mean(first_chunk_times),
                "median_first_chunk_time": statistics.median(first_chunk_times),
                "total_chunks": sum(r.total_chunks for r in successful_results)
            }
        
        return analysis
    
    def print_summary(self, analysis: Dict):
        """Print detailed benchmark summary"""
        print("\n" + "=" * 70)
        print("PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 70)
        
        for server_name, stats in analysis.items():
            print(f"\n{server_name.upper()} SERVER:")
            print("-" * 30)
            print(f"Success Rate:           {stats['success_rate']:6.1f}%")
            print(f"Tests:                  {stats['successful_tests']}/{stats['total_tests']}")
            print(f"Avg Response Time:      {stats.get('avg_response_time', 0):6.2f}s")
            print(f"Median Response Time:   {stats.get('median_response_time', 0):6.2f}s")
            print(f"Min Response Time:      {stats.get('min_response_time', 0):6.2f}s")
            print(f"Max Response Time:      {stats.get('max_response_time', 0):6.2f}s")
            print(f"Avg First Chunk Time:   {stats.get('avg_first_chunk_time', 0):6.2f}s")
            print(f"Total Chunks Streamed:  {stats.get('total_chunks', 0):6d}")
        
        # Performance comparison
        if len(analysis) > 1:
            print(f"\n{'PERFORMANCE COMPARISON':^70}")
            print("-" * 70)
            
            servers = list(analysis.keys())
            if "optimized" in analysis and "original" in analysis:
                opt_time = analysis["optimized"].get("avg_response_time", 0)
                orig_time = analysis["original"].get("avg_response_time", 0)
                
                if orig_time > 0:
                    improvement = ((orig_time - opt_time) / orig_time) * 100
                    print(f"Response Time Improvement: {improvement:+.1f}%")
                
                opt_first = analysis["optimized"].get("avg_first_chunk_time", 0)
                orig_first = analysis["original"].get("avg_first_chunk_time", 0)
                
                if orig_first > 0:
                    first_improvement = ((orig_first - opt_first) / orig_first) * 100
                    print(f"First Chunk Improvement:   {first_improvement:+.1f}%")
    
    def save_results(self, filename: str = "benchmark_results.json"):
        """Save detailed results to JSON file"""
        results_data = {
            "timestamp": time.time(),
            "test_queries": [(q.name, q.query, q.expected_type) for q in TEST_QUERIES],
            "results": [
                {
                    "query_type": r.query_type,
                    "server_type": r.server_type,
                    "response_time": r.response_time,
                    "success": r.success,
                    "first_chunk_time": r.first_chunk_time,
                    "total_chunks": r.total_chunks,
                    "error_message": r.error_message
                }
                for r in self.results
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\nDetailed results saved to: {filename}")

async def run_quick_test():
    """Run a quick test with just a few queries"""
    print("Running Quick Performance Test...")
    
    quick_queries = [
        TestQuery("quick_simple", "Hello", "simple_direct"),
        TestQuery("quick_flutter", "How to create a Flutter button?", "rag_required"),
    ]
    
    benchmark = PerformanceBenchmark()
    
    for query in quick_queries:
        print(f"\nTesting: {query.name}")
        for server_name, server_url in SERVERS.items():
            try:
                result = await benchmark.test_server_response(server_url, server_name, query)
                status = "✓" if result.success else "✗"
                print(f"  {server_name:12} | {result.response_time:5.2f}s | {status}")
            except Exception as e:
                print(f"  {server_name:12} | ERROR: {e}")

async def main():
    """Main benchmark execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Server Performance Benchmark")
    parser.add_argument("--quick", action="store_true", help="Run quick test instead of full suite")
    parser.add_argument("--save", type=str, default="benchmark_results.json", help="Save results to file")
    
    args = parser.parse_args()
    
    if args.quick:
        await run_quick_test()
    else:
        benchmark = PerformanceBenchmark()
        analysis = await benchmark.run_benchmark_suite()
        benchmark.print_summary(analysis)
        benchmark.save_results(args.save)

if __name__ == "__main__":
    asyncio.run(main())