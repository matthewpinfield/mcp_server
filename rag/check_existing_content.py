#!/usr/bin/env python3
"""
Check what content we currently have in our RAG databases
"""

import lancedb
import pandas as pd

def check_lancedb():
    """Check existing LanceDB content"""
    print("🔍 Checking existing LanceDB content...")
    
    try:
        db = lancedb.connect('lancedb_data')
        tables = db.table_names()
        print(f"📊 LanceDB Tables: {tables}")
        
        if 'flutter_dart_docs_comprehensive' in tables:
            table = db.open_table('flutter_dart_docs_comprehensive')
            print(f"📖 Flutter/Dart docs: {len(table)} documents")
            
            # Sample a few documents to see what we have
            sample = table.head(3).to_pandas()
            print("\n📝 Sample content structure:")
            
            for i, row in sample.iterrows():
                print(f"\n  Document {i+1}:")
                for col in row.index:
                    if col != 'vector':  # Skip the embedding vector
                        value = str(row[col])
                        if len(value) > 100:
                            value = value[:100] + "..."
                        print(f"    {col}: {value}")
            
            # Check what columns/metadata we have
            print(f"\n📋 Available columns: {list(sample.columns)}")
            
            return True
        else:
            print("❌ Flutter/Dart table not found")
            return False
            
    except Exception as e:
        print(f"❌ LanceDB access error: {e}")
        return False

def check_chroma():
    """Check existing Chroma content"""
    print("\n🔍 Checking existing Chroma content...")
    
    try:
        import chromadb
        
        # Check production Chroma
        client = chromadb.PersistentClient(path="/mnt/caseSSD/mcp_server_data/vector_db")
        collections = client.list_collections()
        
        if collections:
            print(f"📊 Chroma Collections: {[c.name for c in collections]}")
            
            for collection in collections:
                count = collection.count()
                print(f"📖 Collection '{collection.name}': {count} documents")
                
                if count > 0:
                    # Sample a few documents
                    sample = collection.peek(limit=3)
                    print(f"  Sample documents from {collection.name}:")
                    for i, doc in enumerate(sample['documents']):
                        preview = doc[:100] + "..." if len(doc) > 100 else doc
                        print(f"    {i+1}. {preview}")
                        if i < len(sample.get('metadatas', [])) and sample['metadatas'][i]:
                            print(f"       Metadata: {sample['metadatas'][i]}")
        else:
            print("📊 No Chroma collections found")
            
        return True
        
    except Exception as e:
        print(f"❌ Chroma access error: {e}")
        return False

def analyze_content_gaps():
    """Analyze what content we have vs what we need"""
    print("\n🎯 Content Gap Analysis:")
    
    # What we need for the two-level system
    needed_content = {
        "Official Docs": [
            "PEP 8 Style Guide (Python)",
            "Effective Dart Guide", 
            "MDN JavaScript Best Practices",
            "Flutter Widget Guidelines"
        ],
        "Clean Code Principles": [
            "SOLID principles",
            "DRY/KISS principles", 
            "Code organization patterns",
            "Error handling best practices"
        ],
        "Authority Sources": [
            "Google Style Guides",
            "Airbnb JavaScript Guide",
            "Flutter official examples",
            "High-quality GitHub repositories"
        ]
    }
    
    print("📚 Content we need to build the 'Library' (RAG knowledge base):")
    for category, items in needed_content.items():
        print(f"\n  {category}:")
        for item in items:
            print(f"    • {item}")
    
    print("\n🔧 Personal Rules System (MongoDB 'Law'):")
    print("  • Currently handled by your existing memory system")
    print("  • `/rule` commands store personal coding preferences")
    print("  • These override RAG suggestions when conflicts arise")

if __name__ == "__main__":
    print("🚀 RAG Content Assessment\n")
    
    lance_ok = check_lancedb()
    chroma_ok = check_chroma()
    analyze_content_gaps()
    
    print(f"\n✅ Assessment complete!")
    print(f"   LanceDB: {'✅' if lance_ok else '❌'}")
    print(f"   Chroma: {'✅' if chroma_ok else '❌'}")