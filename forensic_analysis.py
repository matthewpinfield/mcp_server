#!/usr/bin/env python3
"""
Forensic Code Analysis Tool
===========================
Provides exact line numbers, function definitions, and detailed evidence
of redundancy in knowledge.py. Zero assumptions, pure data science.
"""

import ast
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import hashlib

def forensic_analysis(file_path: str) -> Dict:
    """Forensic analysis with exact line numbers and evidence"""
    
    with open(file_path, 'r') as f:
        content = f.read()
    lines = content.split('\n')
    
    tree = ast.parse(content)
    
    analysis = {
        "file_path": file_path,
        "total_lines": len(lines),
        "analysis_timestamp": __import__('datetime').datetime.now().isoformat(),
        "functions": {},
        "async_functions": {},
        "duplicate_code_blocks": [],
        "embedding_calls": [],
        "database_connections": [],
        "import_statements": [],
        "large_functions": [],
        "identical_functions": [],
        "performance_hotspots": []
    }
    
    # Detailed function analysis
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_info = analyze_function_node(node, lines)
            analysis["functions"][node.name] = func_info
            
            if func_info["is_async"]:
                analysis["async_functions"][node.name] = func_info
                
            if func_info["line_count"] > 30:
                analysis["large_functions"].append({
                    "name": node.name,
                    "start_line": func_info["start_line"],
                    "end_line": func_info["end_line"],
                    "line_count": func_info["line_count"],
                    "complexity_score": func_info["complexity_score"]
                })
    
    # Find exact embedding calls with line numbers
    analysis["embedding_calls"] = find_embedding_calls(content, lines)
    
    # Find database connections
    analysis["database_connections"] = find_database_connections(content, lines)
    
    # Find import statements
    analysis["import_statements"] = find_imports(content, lines)
    
    # Find identical function bodies
    analysis["identical_functions"] = find_identical_functions(analysis["functions"])
    
    # Find duplicate code blocks
    analysis["duplicate_code_blocks"] = find_duplicate_blocks(content, lines)
    
    # Performance hotspot analysis
    analysis["performance_hotspots"] = analyze_performance_hotspots(analysis)
    
    return analysis

def analyze_function_node(node: ast.FunctionDef, lines: List[str]) -> Dict:
    """Analyze a single function node with exact details"""
    start_line = node.lineno
    end_line = node.end_lineno or start_line
    
    # Get actual function source
    func_lines = lines[start_line-1:end_line]
    func_source = '\n'.join(func_lines)
    
    # Calculate complexity (simplified cyclomatic complexity)
    complexity = 1  # Base complexity
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    
    # Analyze async patterns
    has_await = 'await ' in func_source
    has_asyncio = 'asyncio.' in func_source
    has_embedding_call = 'ollama.embeddings' in func_source
    has_db_call = any(db in func_source for db in ['lancedb.connect', 'redis.Redis', 'pymongo.MongoClient'])
    
    # Get function signature
    args = [arg.arg for arg in node.args.args]
    signature = f"{'async ' if hasattr(node, 'returns') and str(node.returns) else ''}def {node.name}({', '.join(args)})"
    
    # Hash function body for duplicate detection
    body_lines = func_lines[1:]  # Skip function definition line
    body_content = '\n'.join(line.strip() for line in body_lines if line.strip() and not line.strip().startswith('#'))
    body_hash = hashlib.md5(body_content.encode()).hexdigest()
    
    return {
        "name": node.name,
        "start_line": start_line,
        "end_line": end_line,
        "line_count": end_line - start_line + 1,
        "signature": signature,
        "is_async": isinstance(node, ast.AsyncFunctionDef) or 'async def' in lines[start_line-1],
        "has_await": has_await,
        "has_asyncio": has_asyncio,
        "has_embedding_call": has_embedding_call,
        "has_db_call": has_db_call,
        "complexity_score": complexity,
        "arguments": args,
        "source_code": func_source,
        "body_hash": body_hash,
        "docstring": ast.get_docstring(node) or ""
    }

def find_embedding_calls(content: str, lines: List[str]) -> List[Dict]:
    """Find all embedding calls with exact line numbers and context"""
    embedding_calls = []
    
    patterns = [
        r'ollama\.embeddings\s*\(',
        r'await\s+asyncio\.wait_for\s*\(\s*asyncio\.to_thread\s*\(\s*ollama\.embeddings',
        r'embedding_response\s*=.*ollama\.embeddings'
    ]
    
    for line_num, line in enumerate(lines, 1):
        for pattern in patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                # Get surrounding context
                context_start = max(0, line_num - 3)
                context_end = min(len(lines), line_num + 3)
                context = '\n'.join(f"{i+1:4d}: {lines[i]}" for i in range(context_start, context_end))
                
                embedding_calls.append({
                    "line_number": line_num,
                    "pattern_matched": pattern,
                    "full_line": line.strip(),
                    "context": context,
                    "is_async": 'await' in line or 'asyncio' in line,
                    "model_used": extract_model_from_line(line)
                })
    
    return embedding_calls

def find_database_connections(content: str, lines: List[str]) -> List[Dict]:
    """Find all database connection calls with details"""
    connections = []
    
    db_patterns = {
        'lancedb': r'lancedb\.connect\s*\(',
        'redis': r'redis\.Redis\s*\(',
        'mongodb': r'pymongo\.MongoClient\s*\('
    }
    
    for line_num, line in enumerate(lines, 1):
        for db_type, pattern in db_patterns.items():
            if re.search(pattern, line):
                connections.append({
                    "line_number": line_num,
                    "database_type": db_type,
                    "full_line": line.strip(),
                    "pattern": pattern,
                    "in_function": find_containing_function(line_num, lines)
                })
    
    return connections

def find_imports(content: str, lines: List[str]) -> List[Dict]:
    """Catalog all import statements with usage analysis"""
    imports = []
    
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if line.startswith('import ') or line.startswith('from '):
            # Count how many times this import is used in the file
            if line.startswith('import '):
                module = line.replace('import ', '').split(' as ')[0].split(',')[0].strip()
            else:  # from X import Y
                parts = line.split(' import ')
                if len(parts) > 1:
                    module = parts[1].split(',')[0].split(' as ')[0].strip()
                else:
                    module = parts[0].replace('from ', '').strip()
            
            usage_count = content.count(module) - 1  # -1 for the import statement itself
            
            imports.append({
                "line_number": line_num,
                "import_statement": line,
                "module": module,
                "usage_count": usage_count,
                "is_used": usage_count > 0
            })
    
    return imports

def find_containing_function(line_num: int, lines: List[str]) -> str:
    """Find which function contains a given line number"""
    for i in range(line_num - 1, -1, -1):
        line = lines[i].strip()
        if line.startswith('def ') or line.startswith('async def '):
            return line.split('(')[0].replace('def ', '').replace('async ', '').strip()
    return "global_scope"

def extract_model_from_line(line: str) -> str:
    """Extract model name from embedding call"""
    model_match = re.search(r'model\s*=\s*["\']([^"\']+)["\']', line)
    return model_match.group(1) if model_match else "unknown"

def find_identical_functions(functions: Dict) -> List[Dict]:
    """Find functions with identical bodies"""
    hash_groups = defaultdict(list)
    
    for func_name, func_info in functions.items():
        hash_groups[func_info["body_hash"]].append(func_name)
    
    identical = []
    for body_hash, func_names in hash_groups.items():
        if len(func_names) > 1:
            # Get the actual function details
            func_details = []
            for name in func_names:
                func_details.append({
                    "name": name,
                    "start_line": functions[name]["start_line"],
                    "line_count": functions[name]["line_count"],
                    "signature": functions[name]["signature"]
                })
            
            identical.append({
                "body_hash": body_hash,
                "identical_functions": func_details,
                "evidence": functions[func_names[0]]["source_code"][:200] + "..."
            })
    
    return identical

def find_duplicate_blocks(content: str, lines: List[str]) -> List[Dict]:
    """Find duplicate code blocks (not just functions)"""
    duplicates = []
    
    # Look for repeated patterns of 5+ lines
    for i in range(len(lines) - 5):
        block = '\n'.join(lines[i:i+5])
        block_hash = hashlib.md5(block.encode()).hexdigest()
        
        # Find other occurrences
        matches = []
        for j in range(i + 5, len(lines) - 5):
            compare_block = '\n'.join(lines[j:j+5])
            if hashlib.md5(compare_block.encode()).hexdigest() == block_hash:
                matches.append(j + 1)  # Convert to 1-based line numbers
        
        if matches:
            duplicates.append({
                "original_line": i + 1,
                "duplicate_lines": matches,
                "block_content": block,
                "block_hash": block_hash
            })
    
    return duplicates[:10]  # Limit to first 10 for readability

def analyze_performance_hotspots(analysis: Dict) -> List[Dict]:
    """Identify specific performance bottlenecks with evidence"""
    hotspots = []
    
    # Analyze async embedding patterns
    async_embedding_funcs = []
    for name, func in analysis["async_functions"].items():
        if func["has_embedding_call"]:
            async_embedding_funcs.append({
                "function": name,
                "line": func["start_line"],
                "evidence": func["source_code"][:150] + "..."
            })
    
    if len(async_embedding_funcs) > 2:
        hotspots.append({
            "issue": "Multiple async embedding implementations",
            "severity": "HIGH",
            "count": len(async_embedding_funcs),
            "functions": async_embedding_funcs,
            "recommendation": "Consolidate into single async_embedding_call() helper"
        })
    
    # Analyze database connection patterns
    db_connection_funcs = set()
    for conn in analysis["database_connections"]:
        db_connection_funcs.add(conn["in_function"])
    
    if len(db_connection_funcs) > 3:
        hotspots.append({
            "issue": "Database connections scattered across functions",
            "severity": "MEDIUM", 
            "count": len(analysis["database_connections"]),
            "functions": list(db_connection_funcs),
            "recommendation": "Implement connection pooling/singleton pattern"
        })
    
    return hotspots

def generate_forensic_report(analysis: Dict) -> str:
    """Generate detailed forensic report"""
    report = []
    report.append("=" * 100)
    report.append("FORENSIC CODE ANALYSIS REPORT")
    report.append("=" * 100)
    report.append(f"File: {analysis['file_path']}")
    report.append(f"Total Lines: {analysis['total_lines']}")
    report.append(f"Analysis Time: {analysis['analysis_timestamp']}")
    report.append("")
    
    # Function breakdown
    report.append("📊 FUNCTION ANALYSIS")
    report.append("-" * 50)
    report.append(f"Total Functions: {len(analysis['functions'])}")
    report.append(f"Async Functions: {len(analysis['async_functions'])}")
    report.append("")
    
    for name, func in analysis["async_functions"].items():
        report.append(f"ASYNC FUNCTION: {name}")
        report.append(f"  Lines: {func['start_line']}-{func['end_line']} ({func['line_count']} lines)")
        report.append(f"  Signature: {func['signature']}")
        report.append(f"  Has Await: {func['has_await']}")
        report.append(f"  Has Asyncio: {func['has_asyncio']}")
        report.append(f"  Has Embedding: {func['has_embedding_call']}")
        report.append(f"  Complexity: {func['complexity_score']}")
        report.append("")
    
    # Embedding calls
    report.append("🔍 EMBEDDING CALLS ANALYSIS")
    report.append("-" * 50)
    for call in analysis["embedding_calls"]:
        report.append(f"Line {call['line_number']}: {call['full_line']}")
        report.append(f"  Pattern: {call['pattern_matched']}")
        report.append(f"  Async: {call['is_async']}")
        report.append(f"  Model: {call['model_used']}")
        report.append("")
    
    # Database connections
    report.append("🗄️ DATABASE CONNECTIONS")
    report.append("-" * 50)
    for conn in analysis["database_connections"]:
        report.append(f"Line {conn['line_number']}: {conn['database_type'].upper()}")
        report.append(f"  Code: {conn['full_line']}")
        report.append(f"  Function: {conn['in_function']}")
        report.append("")
    
    # Identical functions
    if analysis["identical_functions"]:
        report.append("🔄 IDENTICAL FUNCTIONS (EXACT DUPLICATES)")
        report.append("-" * 50)
        for dup in analysis["identical_functions"]:
            report.append(f"Duplicate Set (Hash: {dup['body_hash'][:8]}):")
            for func in dup["identical_functions"]:
                report.append(f"  - {func['name']} (Line {func['start_line']}, {func['line_count']} lines)")
            report.append(f"Evidence: {dup['evidence']}")
            report.append("")
    
    # Performance hotspots
    if analysis["performance_hotspots"]:
        report.append("🔥 PERFORMANCE HOTSPOTS")
        report.append("-" * 50)
        for hotspot in analysis["performance_hotspots"]:
            report.append(f"ISSUE: {hotspot['issue']} ({hotspot['severity']})")
            report.append(f"Count: {hotspot['count']}")
            report.append(f"Functions: {', '.join(hotspot['functions'])}")
            report.append(f"Fix: {hotspot['recommendation']}")
            report.append("")
    
    return "\n".join(report)

if __name__ == "__main__":
    file_path = "/mnt/caseSSD/mcp_server_project/tools/knowledge.py"
    
    print("🔬 Starting forensic analysis...")
    analysis = forensic_analysis(file_path)
    
    report = generate_forensic_report(analysis)
    print(report)
    
    # Save detailed report
    with open("forensic_report.txt", "w") as f:
        f.write(report)
    
    print(f"\n💾 Detailed report saved to: forensic_report.txt")
    print(f"📈 Analysis complete. Found {len(analysis['performance_hotspots'])} performance hotspots.")