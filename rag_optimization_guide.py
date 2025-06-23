#!/usr/bin/env python3
"""
RAG Server Optimization Guide and Utilities
Provides specific recommendations for optimizing the RAG pipeline
"""

import asyncio
import httpx
import json
import time
from typing import Dict, List, Optional

class RAGOptimizer:
    """Utilities for optimizing RAG server performance"""
    
    def __init__(self, rag_endpoint: str = "http://localhost:8008"):
        self.rag_endpoint = rag_endpoint
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def test_rag_performance(self, test_queries: List[str]) -> Dict:
        """Test current RAG server performance"""
        results = []
        
        for query in test_queries:
            start_time = time.time()
            
            try:
                response = await self.client.post(
                    f"{self.rag_endpoint}/custom_rag_stuff",
                    json={"fullInput": query}
                )
                response.raise_for_status()
                
                response_time = time.time() - start_time
                response_length = len(response.text)
                
                results.append({
                    "query": query[:50] + "...",
                    "response_time": response_time,
                    "response_length": response_length,
                    "success": True
                })
                
            except Exception as e:
                results.append({
                    "query": query[:50] + "...",
                    "response_time": time.time() - start_time,
                    "response_length": 0,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "test_results": results,
            "avg_response_time": sum(r["response_time"] for r in results if r["success"]) / max(1, sum(1 for r in results if r["success"])),
            "success_rate": sum(1 for r in results if r["success"]) / len(results)
        }
    
    async def check_rag_health(self) -> Dict:
        """Check RAG server health and capabilities"""
        try:
            health_response = await self.client.get(f"{self.rag_endpoint}/health")
            health_data = health_response.json()
            
            return {
                "status": "healthy",
                "rag_server_info": health_data,
                "recommendations": self.generate_health_recommendations(health_data)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "recommendations": ["Check if RAG server is running", "Verify endpoint URL", "Check network connectivity"]
            }
    
    def generate_health_recommendations(self, health_data: Dict) -> List[str]:
        """Generate optimization recommendations based on health data"""
        recommendations = []
        
        # Check embedding model
        embedding_model = health_data.get("embedding_model", "")
        if "nomic-embed-text" in embedding_model:
            recommendations.append("✓ Using fast nomic-embed-text model - good choice for speed")
        elif "all-MiniLM-L6-v2" in embedding_model:
            recommendations.append("Consider upgrading to nomic-embed-text for better performance")
        
        # Check default model
        default_model = health_data.get("default_model", "")
        if "llama3.3:70b" in default_model:
            recommendations.append("✓ Using llama3.3:70b - GPT-4 class model with excellent reasoning")
        
        # Check database status
        if health_data.get("database_available"):
            recommendations.append("✓ Database is available")
        else:
            recommendations.append(" Database unavailable - this will cause failures")
        
        return recommendations

def print_optimization_guide():
    """Print comprehensive optimization guide"""
    print("""
 MCP SERVER PERFORMANCE OPTIMIZATION GUIDE
============================================

PROBLEM ANALYSIS:
- Original: 60+ seconds total response time
- Target: <10 seconds for practical use

ROOT CAUSES IDENTIFIED:
1. Qwen-Agent "thinking" overhead: 12 seconds
2. RAG server processing: 23 seconds  
3. Agent framework complexity
4. No caching or optimization

OPTIMIZATION STRATEGY:

 TIER 1: IMMEDIATE GAINS (Target: <5 seconds)
--------------------------------------------
 Smart Query Routing:
   - Simple queries → Direct Ollama (bypass agent)
   - Flutter/Dart queries → Optimized RAG
   - Complex queries → Full agent (when needed)

 Response Caching:
   - Cache common responses in memory
   - 5-minute TTL for development queries
   - Reduces repeated processing

 Connection Pooling:
   - Persistent HTTP connections
   - Reduced connection overhead
   - Async I/O throughout

 TIER 2: RAG OPTIMIZATION (Target: 10-15 seconds)
-------------------------------------------------
⚡ RAG Server Optimizations:
   - Use faster embedding models (nomic-embed-text vs sentence-transformers)
   - Implement query preprocessing/filtering
   - Add semantic similarity thresholds
   - Cache frequent embeddings

 Parallel Processing:
   - Async RAG calls
   - Streaming responses while processing
   - Early acknowledgment to user

 TIER 3: ADVANCED OPTIMIZATION (Target: <3 seconds)
---------------------------------------------------
📊 Intelligent Preprocessing:
   - Query complexity analysis
   - Pre-computed response templates
   - Context-aware routing

🏆 Infrastructure:
   - RAG server on SSD storage
   - Model quantization (GGUF format)
   - Memory-mapped model loading

IMPLEMENTATION PRIORITY:
======================
1.  Deploy fast_mcp_server.py (immediate 3-5x improvement)
2. 🔧 RAG server configuration tuning
3. 📈 Implement advanced caching
4. 🏁 Fine-tune model parameters

EXPECTED IMPROVEMENTS:
====================
- Simple queries: 60s → 2-3s (20x faster)
- Flutter/Dart queries: 60s → 8-12s (5-7x faster)  
- Complex queries: 60s → 15-25s (2-4x faster)

MONITORING:
==========
- Use performance_benchmark.py for testing
- Monitor first-chunk-time (user perception)
- Track cache hit rates
- Measure query routing accuracy
""")

def print_rag_specific_optimizations():
    """Print RAG-specific optimization recommendations"""
    print("""
 RAG SERVER SPECIFIC OPTIMIZATIONS
===================================

CURRENT BOTTLENECKS IN RAG PIPELINE:
1. Embedding Generation: 3-5 seconds
2. Vector Search: 2-3 seconds  
3. Document Retrieval: 1-2 seconds
4. LLM Synthesis: 15-20 seconds

OPTIMIZATION STRATEGIES:

 EMBEDDING OPTIMIZATION:
- Switch to nomic-embed-text (3x faster than sentence-transformers)
- Pre-compute embeddings for common queries
- Use batch embedding for multiple queries
- Implement embedding caching with Redis

⚡ VECTOR SEARCH OPTIMIZATION:
- Optimize LanceDB query parameters
- Use approximate search (ANN) instead of exact
- Implement query filtering before search
- Add similarity score thresholds

 LLM SYNTHESIS OPTIMIZATION:
- Use streaming responses
- Implement response truncation for long docs
- Add query-specific prompt templates
- Use faster models for simple synthesis

📊 CACHING STRATEGY:
- Query result caching (exact matches)
- Embedding caching (partial matches)
- Document chunk caching (frequent docs)
- Response template caching

CONFIGURATION RECOMMENDATIONS:
============================

For LanceDB:
```python
# Optimize search parameters
search_params = {
    "nprobes": 10,  # Reduce from default for speed
    "refine_factor": 1,  # Minimize refinement
    "use_index": True
}
```

For Embeddings:
```python
# Use faster model
embedding_model = "nomic-embed-text:latest"  # vs all-MiniLM-L6-v2
```

For LLM Synthesis:
```python
# Optimize generation parameters
generation_config = {
    "temperature": 0.1,  # Lower for consistent responses
    "max_tokens": 1000,  # Limit response length
    "top_p": 0.9,
    "stop_sequences": ["END_RESPONSE"]
}
```

MONITORING METRICS:
==================
- Embedding time per query
- Vector search latency
- Document retrieval count/time
- LLM synthesis time
- Cache hit/miss ratios
- End-to-end response time
""")

async def main():
    """Main optimization utility"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Optimization Utilities")
    parser.add_argument("--test-rag", action="store_true", help="Test current RAG performance")
    parser.add_argument("--health-check", action="store_true", help="Check RAG server health")
    parser.add_argument("--guide", action="store_true", help="Show optimization guide")
    parser.add_argument("--rag-guide", action="store_true", help="Show RAG-specific optimizations")
    
    args = parser.parse_args()
    
    if args.guide:
        print_optimization_guide()
    
    if args.rag_guide:
        print_rag_specific_optimizations()
    
    if args.test_rag or args.health_check:
        optimizer = RAGOptimizer()
        
        if args.health_check:
            print("Checking RAG server health...")
            health = await optimizer.check_rag_health()
            print(json.dumps(health, indent=2))
        
        if args.test_rag:
            test_queries = [
                "How to create a Flutter widget?",
                "Explain Dart async programming",
                "What is StatefulWidget?",
                "How to handle user input in Flutter?",
                "Dart language basics"
            ]
            
            print("Testing RAG performance...")
            results = await optimizer.test_rag_performance(test_queries)
            print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())