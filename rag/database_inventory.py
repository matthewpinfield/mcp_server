#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions
from collections import defaultdict
import os

def analyze_database(db_path, collection_name, description):
    """Analyze a specific database and return its stats"""
    
    print(f"\n{'='*60}")
    print(f"📊 {description}")
    print(f"{'='*60}")
    print(f"Path: {db_path}")
    print(f"Collection: {collection_name}")
    
    if not os.path.exists(db_path):
        print("❌ Database does not exist")
        return None
    
    try:
        client = chromadb.PersistentClient(path=db_path)
        
        # List all collections
        collections = client.list_collections()
        print(f"Collections found: {[c.name for c in collections]}")
        
        # Check if target collection exists
        target_collection = None
        for c in collections:
            if c.name == collection_name:
                target_collection = c
                break
        
        if not target_collection:
            print(f"❌ Collection '{collection_name}' not found")
            return None
        
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_functions.OllamaEmbeddingFunction(
                model_name="nomic-embed-text:latest",
                url="http://127.0.0.1:11434"
            )
        )
        
        # Get basic stats
        total_count = collection.count()
        print(f"Total chunks: {total_count}")
        
        if total_count == 0:
            print("⚠️  Database is empty")
            return {'total': 0}
        
        # Sample some data for analysis
        sample_size = min(1000, total_count)
        results = collection.get(limit=sample_size)
        
        # Analyze metadata
        metadatas = results['metadatas']
        documents = results['documents']
        
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
        
        # Content analysis
        text_lengths = [len(doc) for doc in documents]
        avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
        
        print(f"Average text length: {avg_length:.0f} characters")
        print(f"Sample size analyzed: {len(metadatas)}")
        
        print(f"\nLanguage distribution:")
        for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metadatas)) * 100
            print(f"  {lang}: {count} ({percentage:.1f}%)")
        
        print(f"\nAuthority distribution:")
        for auth, count in sorted(authorities.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metadatas)) * 100
            print(f"  {auth}: {count} ({percentage:.1f}%)")
        
        print(f"\nDoc type distribution:")
        for doc_type, count in sorted(doc_types.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metadatas)) * 100
            print(f"  {doc_type}: {count} ({percentage:.1f}%)")
        
        print(f"\nTop source distribution:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True)[:5]:
            percentage = (count / len(metadatas)) * 100
            print(f"  {source}: {count} ({percentage:.1f}%)")
        
        return {
            'total': total_count,
            'avg_length': avg_length,
            'languages': dict(languages),
            'authorities': dict(authorities),
            'doc_types': dict(doc_types),
            'sources': dict(sources)
        }
        
    except Exception as e:
        print(f"❌ Error analyzing database: {e}")
        return None

def main():
    """Inventory all RAG databases"""
    
    print("🗂️  RAG DATABASE INVENTORY")
    print("=" * 80)
    
    databases = [
        {
            'path': './flutter_only_db',
            'collection': 'flutter_dart_knowledge',
            'description': 'FLUTTER-ONLY DATABASE (Basic Flutter Docs)'
        },
        {
            'path': './rag_db_final',
            'collection': 'expert_py_flutter_dart_final',
            'description': 'MIXED PYTHON + FLUTTER DATABASE (Comprehensive)'
        },
        {
            'path': './test_rag_db',
            'collection': 'test_collection',
            'description': 'TEST DATABASE'
        }
    ]
    
    results = {}
    
    for db_config in databases:
        result = analyze_database(
            db_config['path'],
            db_config['collection'],
            db_config['description']
        )
        results[db_config['description']] = result
    
    # Summary comparison
    print(f"\n{'='*80}")
    print(f"📋 DATABASE COMPARISON SUMMARY")
    print(f"{'='*80}")
    
    for desc, stats in results.items():
        if stats:
            print(f"\n{desc}:")
            print(f"  Total chunks: {stats['total']:,}")
            if stats['total'] > 0:
                print(f"  Avg chunk length: {stats.get('avg_length', 0):.0f} chars")
                
                # Top language
                languages = stats.get('languages', {})
                if languages:
                    top_lang = max(languages.items(), key=lambda x: x[1])
                    print(f"  Primary language: {top_lang[0]} ({top_lang[1]} chunks)")
                
                # Authority mix
                authorities = stats.get('authorities', {})
                if authorities:
                    elite_count = authorities.get('T2_Elite', 0)
                    official_count = authorities.get('T1_Official', 0)
                    print(f"  Elite code: {elite_count}, Official docs: {official_count}")
    
    print(f"\n🎯 RECOMMENDATION:")
    
    # Find the best database
    best_db = None
    max_total = 0
    
    for desc, stats in results.items():
        if stats and stats['total'] > max_total:
            max_total = stats['total']
            best_db = desc
    
    if best_db:
        print(f"  Primary database for production: {best_db}")
        print(f"  Largest and most comprehensive with {max_total:,} chunks")
    
    print(f"\n💡 USAGE GUIDELINES:")
    print(f"  • Use MIXED database for general Python/Flutter queries")
    print(f"  • Use FLUTTER-ONLY database for Flutter-specific applications")
    print(f"  • TEST database can be used for experimentation")

if __name__ == "__main__":
    main()