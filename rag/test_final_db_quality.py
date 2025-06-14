#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions
from collections import defaultdict
import json

def test_database_quality():
    """Test the quality of the final ingested database"""
    
    DATABASE_CONFIG = {
        "path": "./rag_db_final",
        "collection_name": "expert_py_flutter_dart_final",
        "embedding_model": "nomic-embed-text:latest"
    }
    OLLAMA_CONFIG = {"base_url": "http://127.0.0.1:11434"}
    
    print(f"\n=== Testing Database Quality ===")
    print(f"Database: {DATABASE_CONFIG['path']}")
    print(f"Collection: {DATABASE_CONFIG['collection_name']}")
    
    try:
        # Connect to database
        client = chromadb.PersistentClient(path=DATABASE_CONFIG["path"])
        collection = client.get_collection(
            name=DATABASE_CONFIG["collection_name"],
            embedding_function=embedding_functions.OllamaEmbeddingFunction(
                model_name=DATABASE_CONFIG["embedding_model"], 
                url=OLLAMA_CONFIG["base_url"]
            )
        )
        
        # Get all data for analysis
        results = collection.get()
        documents = results['documents']
        metadatas = results['metadatas'] 
        ids = results['ids']
        
        print(f"\n📊 DATABASE OVERVIEW")
        print(f"Total chunks: {len(documents)}")
        print(f"Total IDs: {len(ids)}")
        print(f"Total metadata records: {len(metadatas)}")
        
        # Analyze content quality
        print(f"\n📝 CONTENT QUALITY ANALYSIS")
        
        # Text length distribution
        text_lengths = [len(doc) for doc in documents]
        avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
        min_length = min(text_lengths) if text_lengths else 0
        max_length = max(text_lengths) if text_lengths else 0
        
        print(f"Average text length: {avg_length:.0f} characters")
        print(f"Min text length: {min_length}")
        print(f"Max text length: {max_length}")
        
        # Check for empty or very short content
        very_short = sum(1 for length in text_lengths if length < 50)
        empty_docs = sum(1 for doc in documents if not doc.strip())
        
        print(f"Very short chunks (<50 chars): {very_short}")
        print(f"Empty documents: {empty_docs}")
        
        # Analyze metadata distribution
        print(f"\n🏷️  METADATA ANALYSIS")
        
        # Language distribution
        languages = defaultdict(int)
        authorities = defaultdict(int)
        doc_types = defaultdict(int)
        sources = defaultdict(int)
        
        for meta in metadatas:
            languages[meta.get('language', 'MISSING')] += 1
            authorities[meta.get('authority', 'MISSING')] += 1
            doc_types[meta.get('doc_type', 'MISSING')] += 1
            
            source = meta.get('source', 'MISSING')
            if source.startswith('git://'):
                sources['git_repos'] += 1
            elif source.startswith('http'):
                try:
                    domain = source.split('/')[2] if len(source.split('/')) > 2 else source
                    sources[domain] += 1
                except:
                    sources['malformed_url'] += 1
            else:
                sources['unknown_source'] += 1
        
        print(f"\nLanguage distribution:")
        for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metadatas)) * 100
            print(f"  {lang}: {count} ({percentage:.1f}%)")
            
        print(f"\nAuthority distribution:")
        for auth, count in sorted(authorities.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metadatas)) * 100
            print(f"  {auth}: {count} ({percentage:.1f}%)")
            
        print(f"\nDocument type distribution:")
        for doc_type, count in sorted(doc_types.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metadatas)) * 100
            print(f"  {doc_type}: {count} ({percentage:.1f}%)")
            
        print(f"\nTop 10 source distribution:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / len(metadatas)) * 100
            print(f"  {source}: {count} ({percentage:.1f}%)")
        
        # Check data quality issues
        print(f"\n⚠️  DATA QUALITY ISSUES")
        
        missing_language = sum(1 for meta in metadatas if not meta.get('language'))
        missing_authority = sum(1 for meta in metadatas if not meta.get('authority'))
        missing_source = sum(1 for meta in metadatas if not meta.get('source'))
        
        print(f"Missing language: {missing_language}")
        print(f"Missing authority: {missing_authority}")
        print(f"Missing source: {missing_source}")
        
        # Sample content inspection
        print(f"\n🔍 SAMPLE CONTENT INSPECTION")
        
        # Show sample from each authority level
        authority_samples = {}
        for i, meta in enumerate(metadatas[:50]):  # Check first 50
            auth = meta.get('authority', 'MISSING')
            if auth not in authority_samples:
                authority_samples[auth] = {
                    'metadata': meta,
                    'text_preview': documents[i][:200] + "..." if len(documents[i]) > 200 else documents[i],
                    'length': len(documents[i])
                }
        
        for auth, sample in authority_samples.items():
            print(f"\n--- {auth} Sample ---")
            print(f"Language: {sample['metadata'].get('language', 'N/A')}")
            print(f"Doc Type: {sample['metadata'].get('doc_type', 'N/A')}")
            print(f"Source: {sample['metadata'].get('source', 'N/A')[:80]}...")
            print(f"Length: {sample['length']} chars")
            print(f"Preview: {sample['text_preview']}")
        
        # Test search functionality
        print(f"\n🔍 SEARCH FUNCTIONALITY TEST")
        
        test_queries = [
            "Flutter widget StatefulWidget",
            "Python async await function",
            "FastAPI dependency injection",
            "Dart class constructor"
        ]
        
        for query in test_queries:
            try:
                search_results = collection.query(
                    query_texts=[query],
                    n_results=3
                )
                print(f"\nQuery: '{query}'")
                print(f"Results found: {len(search_results['documents'][0])}")
                
                if search_results['documents'][0]:
                    best_result = search_results['documents'][0][0]
                    best_meta = search_results['metadatas'][0][0]
                    print(f"Best result language: {best_meta.get('language', 'N/A')}")
                    print(f"Best result authority: {best_meta.get('authority', 'N/A')}")
                    print(f"Preview: {best_result[:150]}...")
                    
            except Exception as e:
                print(f"Search failed for '{query}': {e}")
        
        # Summary
        print(f"\n📋 QUALITY SUMMARY")
        total_issues = empty_docs + very_short + missing_language + missing_authority + missing_source
        quality_score = max(0, 100 - (total_issues / len(metadatas) * 100))
        
        print(f"Total quality issues: {total_issues}")
        print(f"Quality score: {quality_score:.1f}%")
        
        if quality_score >= 90:
            print("✅ Database quality: EXCELLENT")
        elif quality_score >= 75:
            print("✅ Database quality: GOOD")
        elif quality_score >= 60:
            print("⚠️  Database quality: ACCEPTABLE")
        else:
            print("❌ Database quality: POOR - needs improvement")
            
        return {
            'total_chunks': len(documents),
            'quality_score': quality_score,
            'languages': dict(languages),
            'authorities': dict(authorities),
            'doc_types': dict(doc_types),
            'issues': {
                'empty_docs': empty_docs,
                'very_short': very_short,
                'missing_language': missing_language,
                'missing_authority': missing_authority,
                'missing_source': missing_source
            }
        }
        
    except Exception as e:
        print(f"❌ Error testing database: {e}")
        return None

if __name__ == "__main__":
    result = test_database_quality()
    if result:
        print(f"\n✅ Database testing completed.")
    else:
        print(f"\n❌ Database testing failed.")