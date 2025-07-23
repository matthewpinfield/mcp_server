#!/usr/bin/env python3
"""
Code Redundancy Analysis Tool
============================
Analyzes knowledge.py for duplicate functions, redundant code, and optimization opportunities.
Designed to be used by the MCP agent to identify refactoring targets.
"""

import ast
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple

def analyze_knowledge_file(file_path: str) -> Dict:
    """Analyze knowledge.py for redundancy and optimization opportunities"""
    
    with open(file_path, 'r') as f:
        content = f.read()
        
    # Parse AST
    tree = ast.parse(content)
    
    analysis = {
        "file_stats": {
            "total_lines": len(content.split('\n')),
            "total_functions": 0,
            "total_classes": 0,
            "total_imports": 0
        },
        "duplicate_functions": [],
        "similar_functions": [],
        "redundant_imports": [],
        "performance_issues": [],
        "refactoring_suggestions": []
    }
    
    # Track function signatures and bodies
    functions = {}
    function_bodies = defaultdict(list)
    imports = set()
    
    # Walk AST
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            analysis["file_stats"]["total_functions"] += 1
            
            # Get function signature
            args = [arg.arg for arg in node.args.args]
            signature = f"{node.name}({', '.join(args)})"
            
            # Get function body as string (simplified)
            body_lines = []
            for stmt in node.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                    continue  # Skip docstrings
                body_lines.append(ast.unparse(stmt) if hasattr(ast, 'unparse') else str(stmt))
            
            body_hash = hash('\n'.join(body_lines))
            functions[node.name] = {
                "signature": signature,
                "args": args,
                "body_hash": body_hash,
                "line_count": len(body_lines),
                "docstring": ast.get_docstring(node) or ""
            }
            
            function_bodies[body_hash].append(node.name)
            
        elif isinstance(node, ast.ClassDef):
            analysis["file_stats"]["total_classes"] += 1
            
        elif isinstance(node, ast.Import):
            analysis["file_stats"]["total_imports"] += 1
            for alias in node.names:
                imports.add(alias.name)
                
        elif isinstance(node, ast.ImportFrom):
            analysis["file_stats"]["total_imports"] += 1
            if node.module:
                imports.add(node.module)
    
    # Find duplicate function bodies
    for body_hash, func_names in function_bodies.items():
        if len(func_names) > 1:
            analysis["duplicate_functions"].append({
                "functions": func_names,
                "reason": "Identical function bodies"
            })
    
    # Find similar function names (possible duplicates)
    func_names = list(functions.keys())
    for i, name1 in enumerate(func_names):
        for name2 in func_names[i+1:]:
            # Check for similar names
            if similarity_score(name1, name2) > 0.7:
                analysis["similar_functions"].append({
                    "function1": name1,
                    "function2": name2,
                    "similarity": similarity_score(name1, name2),
                    "suggestion": f"Check if {name1} and {name2} do the same thing"
                })
    
    # Find redundant patterns
    redundant_patterns = find_redundant_patterns(content)
    analysis["performance_issues"].extend(redundant_patterns)
    
    # Check for redundant imports
    import_usage = check_import_usage(content, imports)
    analysis["redundant_imports"] = import_usage["unused"]
    
    # Generate refactoring suggestions
    analysis["refactoring_suggestions"] = generate_refactoring_suggestions(analysis, functions)
    
    return analysis

def similarity_score(str1: str, str2: str) -> float:
    """Calculate similarity between two strings"""
    # Simple Levenshtein-based similarity
    import difflib
    return difflib.SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def find_redundant_patterns(content: str) -> List[Dict]:
    """Find redundant code patterns"""
    issues = []
    
    # Check for repeated ollama.embeddings calls
    embedding_calls = re.findall(r'ollama\.embeddings\([^)]+\)', content)
    if len(embedding_calls) > 3:
        issues.append({
            "issue": "Multiple ollama.embeddings calls",
            "count": len(embedding_calls),
            "suggestion": "Create a single async embedding function",
            "severity": "high"
        })
    
    # Check for repeated asyncio patterns
    asyncio_patterns = re.findall(r'await asyncio\.wait_for\(\s*asyncio\.to_thread\(ollama\.embeddings', content)
    if len(asyncio_patterns) > 2:
        issues.append({
            "issue": "Repeated async embedding patterns",
            "count": len(asyncio_patterns),
            "suggestion": "Create a centralized async_embedding() helper function",
            "severity": "high"
        })
    
    # Check for repeated database connections
    lancedb_connects = re.findall(r'lancedb\.connect\([^)]+\)', content)
    if len(lancedb_connects) > 3:
        issues.append({
            "issue": "Multiple LanceDB connections",
            "count": len(lancedb_connects),
            "suggestion": "Use connection pooling or singleton pattern",
            "severity": "medium"
        })
    
    # Check for large functions (potential bloat)
    function_sizes = re.findall(r'def [^:]+:.*?(?=\n\s*def|\n\s*class|\Z)', content, re.DOTALL)
    large_functions = [f for f in function_sizes if len(f.split('\n')) > 50]
    if large_functions:
        issues.append({
            "issue": "Large functions detected",
            "count": len(large_functions),
            "suggestion": "Break down large functions into smaller, focused functions",
            "severity": "medium"
        })
    
    return issues

def check_import_usage(content: str, imports: Set[str]) -> Dict:
    """Check which imports are actually used"""
    used_imports = set()
    unused_imports = set()
    
    for imp in imports:
        # Simple usage check (not perfect but good enough)
        if imp in content:
            used_imports.add(imp)
        else:
            unused_imports.add(imp)
    
    return {
        "used": list(used_imports),
        "unused": list(unused_imports)
    }

def generate_refactoring_suggestions(analysis: Dict, functions: Dict) -> List[str]:
    """Generate specific refactoring suggestions"""
    suggestions = []
    
    # Based on analysis results
    if analysis["duplicate_functions"]:
        suggestions.append("🔄 CRITICAL: Remove duplicate functions - they're slowing down imports and execution")
    
    if len([p for p in analysis["performance_issues"] if p["severity"] == "high"]) > 0:
        suggestions.append("⚡ HIGH PRIORITY: Consolidate repeated async patterns into helper functions")
    
    # Function count based suggestions
    func_count = analysis["file_stats"]["total_functions"]
    if func_count > 50:
        suggestions.append(f"📦 Consider splitting {func_count} functions across multiple modules")
    
    # Line count based suggestions  
    line_count = analysis["file_stats"]["total_lines"]
    if line_count > 2000:
        suggestions.append(f"📄 File is {line_count} lines - consider breaking into smaller modules")
    
    # Specific 2025 best practices
    suggestions.extend([
        "🚀 2025 Best Practice: Use dependency injection for database connections",
        "🎯 2025 Best Practice: Implement async connection pooling for external services",
        "🔧 2025 Best Practice: Use factory pattern for tool creation",
        "📊 2025 Best Practice: Add performance monitoring/metrics to slow operations"
    ])
    
    return suggestions

if __name__ == "__main__":
    # Can be run directly or imported by agent
    file_path = "/mnt/caseSSD/mcp_server_project/tools/knowledge.py"
    
    print("🔍 Analyzing knowledge.py for redundancy and optimization opportunities...")
    print("=" * 80)
    
    try:
        analysis = analyze_knowledge_file(file_path)
        
        print(f"📊 FILE STATISTICS:")
        for key, value in analysis["file_stats"].items():
            print(f"   {key}: {value}")
        
        print(f"\n🔄 DUPLICATE FUNCTIONS ({len(analysis['duplicate_functions'])}):")
        for dup in analysis["duplicate_functions"]:
            print(f"   - {', '.join(dup['functions'])} - {dup['reason']}")
        
        print(f"\n👯 SIMILAR FUNCTIONS ({len(analysis['similar_functions'])}):")
        for sim in analysis["similar_functions"][:5]:  # Top 5
            print(f"   - {sim['function1']} ↔ {sim['function2']} ({sim['similarity']:.2f} similarity)")
        
        print(f"\n⚡ PERFORMANCE ISSUES ({len(analysis['performance_issues'])}):")
        for issue in analysis["performance_issues"]:
            severity_emoji = "🔥" if issue["severity"] == "high" else "⚠️"
            print(f"   {severity_emoji} {issue['issue']} (x{issue['count']}) - {issue['suggestion']}")
        
        print(f"\n🗑️ UNUSED IMPORTS ({len(analysis['redundant_imports'])}):")
        for imp in analysis["redundant_imports"][:10]:  # Top 10
            print(f"   - {imp}")
        
        print(f"\n💡 REFACTORING SUGGESTIONS:")
        for suggestion in analysis["refactoring_suggestions"]:
            print(f"   {suggestion}")
            
        # Summary score
        total_issues = (len(analysis["duplicate_functions"]) + 
                       len(analysis["performance_issues"]) + 
                       len(analysis["redundant_imports"]))
        
        print(f"\n🎯 REFACTORING PRIORITY SCORE: {total_issues}/100")
        if total_issues > 20:
            print("   🚨 HIGH PRIORITY - Significant performance impact expected")
        elif total_issues > 10:
            print("   ⚠️ MEDIUM PRIORITY - Moderate cleanup needed")
        else:
            print("   ✅ LOW PRIORITY - Code is relatively clean")
            
    except Exception as e:
        print(f"❌ Analysis failed: {e}")