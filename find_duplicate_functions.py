#!/usr/bin/env python3
"""
Test script to find duplicate function definitions in knowledge.py
Helps identify redundant code that can be cleaned up for MVP
"""

import re
import ast
from collections import defaultdict
from typing import Dict, List, Tuple

def extract_functions_ast(file_path: str) -> Dict[str, List[Tuple[int, str]]]:
    """Extract function definitions using AST parsing"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Syntax error parsing {file_path}: {e}")
        return {}
    
    functions = defaultdict(list)
    
    class FunctionVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            # Get line number and basic signature
            line_num = node.lineno
            func_name = node.name
            
            # Get function arguments for better signature matching
            args = []
            for arg in node.args.args:
                args.append(arg.arg)
            
            signature = f"{func_name}({', '.join(args)})"
            functions[func_name].append((line_num, signature))
            
            self.generic_visit(node)
    
    visitor = FunctionVisitor()
    visitor.visit(tree)
    
    return dict(functions)

def extract_functions_regex(file_path: str) -> Dict[str, List[Tuple[int, str]]]:
    """Extract function definitions using regex (backup method)"""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    functions = defaultdict(list)
    func_pattern = re.compile(r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\):')
    
    for i, line in enumerate(lines, 1):
        match = func_pattern.match(line)
        if match:
            func_name = match.group(1)
            params = match.group(2).strip()
            signature = f"{func_name}({params})"
            functions[func_name].append((i, signature))
    
    return dict(functions)

def find_similar_functions(functions: Dict[str, List[Tuple[int, str]]]) -> List[Dict]:
    """Find functions with similar names that might be duplicates"""
    similar_groups = []
    
    func_names = list(functions.keys())
    
    for i, name1 in enumerate(func_names):
        for name2 in func_names[i+1:]:
            # Check for similar names (might indicate duplicates)
            if (name1.replace('_', '').lower() == name2.replace('_', '').lower() or
                name1 in name2 or name2 in name1):
                similar_groups.append({
                    'type': 'similar_names',
                    'functions': [name1, name2],
                    'details': {
                        name1: functions[name1],
                        name2: functions[name2]
                    }
                })
    
    return similar_groups

def analyze_file(file_path: str):
    """Main analysis function"""
    print(f"Analyzing {file_path} for duplicate functions...\n")
    
    # Try AST first, fall back to regex
    try:
        functions = extract_functions_ast(file_path)
        print("✅ Used AST parsing")
    except Exception as e:
        print(f"⚠️  AST parsing failed: {e}")
        print("🔄 Falling back to regex parsing")
        functions = extract_functions_regex(file_path)
    
    print(f"📊 Found {len(functions)} unique function names")
    print(f"📊 Total function definitions: {sum(len(defs) for defs in functions.values())}")
    
    # Find exact duplicates (same name, multiple definitions)
    duplicates = {name: defs for name, defs in functions.items() if len(defs) > 1}
    
    if duplicates:
        print(f"\n🚨 EXACT DUPLICATES FOUND: {len(duplicates)} function names")
        for func_name, definitions in duplicates.items():
            print(f"\n  Function: {func_name}")
            for line_num, signature in definitions:
                print(f"    Line {line_num}: {signature}")
    else:
        print("\n✅ No exact duplicate function names found")
    
    # Find similar function names
    similar = find_similar_functions(functions)
    
    if similar:
        print(f"\n⚠️  SIMILAR FUNCTION NAMES: {len(similar)} potential duplicates")
        for group in similar:
            print(f"\n  Similar functions: {group['functions']}")
            for func_name, definitions in group['details'].items():
                for line_num, signature in definitions:
                    print(f"    {func_name} - Line {line_num}: {signature}")
    else:
        print("\n✅ No similar function names found")
    
    # Show function count summary
    print(f"\n📈 FUNCTION COUNT SUMMARY:")
    multiple_defs = [(name, len(defs)) for name, defs in functions.items() if len(defs) > 1]
    if multiple_defs:
        multiple_defs.sort(key=lambda x: x[1], reverse=True)
        for name, count in multiple_defs:
            print(f"  {name}: {count} definitions")
    
    # Large file warning
    total_functions = sum(len(defs) for defs in functions.values())
    if total_functions > 50:
        print(f"\n⚠️  LARGE FILE WARNING: {total_functions} functions")
        print("   Consider breaking this into smaller modules for MVP")
    
    return duplicates, similar

if __name__ == "__main__":
    file_path = "/mnt/caseSSD/mcp_server_project/tools/knowledge.py"
    duplicates, similar = analyze_file(file_path)
    
    if duplicates or similar:
        print(f"\n🔧 RECOMMENDATIONS:")
        print("  1. Review duplicate functions - keep the best implementation")
        print("  2. Check if similar-named functions can be consolidated")  
        print("  3. Consider refactoring large functions into smaller ones")
    else:
        print(f"\n✅ FILE LOOKS CLEAN - no obvious duplicates found")