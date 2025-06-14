#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions
from collections import defaultdict
import hashlib

def analyze_database_content(db_path, collection_name, db_name):
    """Analyze the content of a database in detail"""
    
    print(f"\n{'='*60}")
    print(f"📊 ANALYZING {db_name}")
    print(f"{'='*60}")
    
    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_functions.OllamaEmbeddingFunction(
                model_name="nomic-embed-text:latest",
                url="http://127.0.0.1:11434"
            )
        )
        
        # Get all data
        results = collection.get()
        documents = results['documents']
        metadatas = results['metadatas']
        
        print(f"Total documents: {len(documents)}")
        
        # Analyze metadata patterns
        sources = defaultdict(int)
        authorities = defaultdict(int)
        doc_types = defaultdict(int)
        languages = defaultdict(int)
        
        # Content analysis
        source_samples = defaultdict(list)
        doc_type_samples = defaultdict(list)
        
        for i, meta in enumerate(metadatas):
            source = meta.get('source', 'unknown')
            authority = meta.get('authority', 'unknown')
            doc_type = meta.get('doc_type', 'unknown')
            language = meta.get('language', 'unknown')
            
            languages[language] += 1
            authorities[authority] += 1
            doc_types[doc_type] += 1
            
            # Categorize sources
            if source.startswith('git://'):
                repo_name = source.split('/')[1] + '/' + source.split('/')[2] if len(source.split('/')) > 2 else 'unknown_repo'
                sources[f"git: {repo_name}"] += 1
            elif source.startswith('http'):
                domain = source.split('/')[2] if len(source.split('/')) > 2 else 'unknown_domain'
                sources[f"web: {domain}"] += 1
            else:
                sources['other'] += 1
            
            # Collect samples for analysis
            if len(source_samples[source.split('/')[2] if source.startswith('http') else source.split(':')[1] if ':' in source else 'git']) < 3:
                source_samples[source.split('/')[2] if source.startswith('http') else source.split(':')[1] if ':' in source else 'git'].append({
                    'text': documents[i][:300] + "..." if len(documents[i]) > 300 else documents[i],
                    'source': source,
                    'doc_type': doc_type,
                    'authority': authority
                })
            
            if len(doc_type_samples[doc_type]) < 3:
                doc_type_samples[doc_type].append({
                    'text': documents[i][:300] + "..." if len(documents[i]) > 300 else documents[i],
                    'source': source,
                    'authority': authority
                })
        
        # Print analysis
        print(f"\nLanguage Distribution:")
        for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metadatas)) * 100
            print(f"  {lang}: {count} ({percentage:.1f}%)")
        
        print(f"\nAuthority Distribution:")
        for auth, count in sorted(authorities.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metadatas)) * 100
            print(f"  {auth}: {count} ({percentage:.1f}%)")
        
        print(f"\nDocument Type Distribution:")
        for doc_type, count in sorted(doc_types.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metadatas)) * 100
            print(f"  {doc_type}: {count} ({percentage:.1f}%)")
        
        print(f"\nTop Source Distribution:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / len(metadatas)) * 100
            print(f"  {source}: {count} ({percentage:.1f}%)")
        
        # Show sample content by document type
        print(f"\n🔍 SAMPLE CONTENT BY TYPE:")
        for doc_type, samples in doc_type_samples.items():
            print(f"\n--- {doc_type.upper()} SAMPLES ---")
            for i, sample in enumerate(samples[:2]):
                print(f"Sample {i+1}:")
                print(f"  Authority: {sample['authority']}")
                print(f"  Source: {sample['source'][:80]}...")
                print(f"  Content: {sample['text'][:200]}...")
                print()
        
        return {
            'total': len(documents),
            'languages': dict(languages),
            'authorities': dict(authorities),
            'doc_types': dict(doc_types),
            'sources': dict(sources),
            'documents': documents,
            'metadatas': metadatas
        }
        
    except Exception as e:
        print(f"❌ Error analyzing {db_name}: {e}")
        return None

def find_content_overlap(db1_data, db2_data, db1_name, db2_name):
    """Find overlapping content between two databases"""
    
    print(f"\n{'='*60}")
    print(f"🔍 CONTENT OVERLAP ANALYSIS")
    print(f"Comparing {db1_name} vs {db2_name}")
    print(f"{'='*60}")
    
    # Create content hashes for comparison
    db1_hashes = set()
    db2_hashes = set()
    
    db1_flutter_docs = []
    db2_flutter_docs = []
    
    # Analyze DB1 (flutter_only)
    for i, (doc, meta) in enumerate(zip(db1_data['documents'], db1_data['metadatas'])):
        content_hash = hashlib.md5(doc.encode()).hexdigest()
        db1_hashes.add(content_hash)
        
        if meta.get('language') == 'flutter':
            db1_flutter_docs.append({
                'hash': content_hash,
                'text': doc,
                'source': meta.get('source', 'unknown'),
                'doc_type': meta.get('doc_type', 'unknown'),
                'authority': meta.get('authority', 'unknown')
            })
    
    # Analyze DB2 (mixed) - only Flutter content
    for i, (doc, meta) in enumerate(zip(db2_data['documents'], db2_data['metadatas'])):
        if meta.get('language') == 'flutter':
            content_hash = hashlib.md5(doc.encode()).hexdigest()
            db2_hashes.add(content_hash)
            
            db2_flutter_docs.append({
                'hash': content_hash,
                'text': doc,
                'source': meta.get('source', 'unknown'),
                'doc_type': meta.get('doc_type', 'unknown'),
                'authority': meta.get('authority', 'unknown')
            })
    
    # Find overlaps
    overlapping_hashes = db1_hashes.intersection(db2_hashes)
    db1_unique_hashes = db1_hashes - db2_hashes
    db2_unique_hashes = db2_hashes - db1_hashes
    
    print(f"📊 OVERLAP STATISTICS:")
    print(f"  {db1_name} Flutter docs: {len(db1_flutter_docs)}")
    print(f"  {db2_name} Flutter docs: {len(db2_flutter_docs)}")
    print(f"  Exact content overlaps: {len(overlapping_hashes)}")
    print(f"  {db1_name} unique content: {len(db1_unique_hashes)}")
    print(f"  {db2_name} unique content: {len(db2_unique_hashes)}")
    
    if len(db1_flutter_docs) > 0:
        overlap_percentage = (len(overlapping_hashes) / len(db1_flutter_docs)) * 100
        print(f"  Overlap percentage: {overlap_percentage:.1f}%")
    
    # Analyze unique content in flutter_only_db
    print(f"\n🔍 UNIQUE CONTENT IN {db1_name}:")
    
    unique_sources = defaultdict(int)
    unique_doc_types = defaultdict(int)
    unique_authorities = defaultdict(int)
    
    unique_samples = []
    
    for doc in db1_flutter_docs:
        if doc['hash'] in db1_unique_hashes:
            unique_sources[doc['source'].split('/')[2] if doc['source'].startswith('http') else 'git_repo'] += 1
            unique_doc_types[doc['doc_type']] += 1
            unique_authorities[doc['authority']] += 1
            
            if len(unique_samples) < 5:
                unique_samples.append(doc)
    
    print(f"Unique content breakdown:")
    print(f"  Sources: {dict(unique_sources)}")
    print(f"  Doc types: {dict(unique_doc_types)}")
    print(f"  Authorities: {dict(unique_authorities)}")
    
    print(f"\n📋 SAMPLE UNIQUE CONTENT IN {db1_name}:")
    for i, sample in enumerate(unique_samples[:3]):
        print(f"\nUnique Sample {i+1}:")
        print(f"  Doc Type: {sample['doc_type']}")
        print(f"  Authority: {sample['authority']}")
        print(f"  Source: {sample['source'][:80]}...")
        print(f"  Content: {sample['text'][:250]}...")
    
    return {
        'overlap_count': len(overlapping_hashes),
        'db1_unique': len(db1_unique_hashes),
        'db2_unique': len(db2_unique_hashes),
        'overlap_percentage': overlap_percentage if len(db1_flutter_docs) > 0 else 0,
        'unique_sources': dict(unique_sources),
        'unique_doc_types': dict(unique_doc_types)
    }

def determine_flutter_db_value(flutter_data, mixed_data, overlap_analysis):
    """Determine if flutter_only_db still has unique value"""
    
    print(f"\n{'='*60}")
    print(f"💡 FLUTTER_ONLY_DB VALUE ASSESSMENT")
    print(f"{'='*60}")
    
    # Analyze content types
    flutter_doc_types = flutter_data['doc_types']
    mixed_flutter_doc_types = {}
    
    for doc, meta in zip(mixed_data['documents'], mixed_data['metadatas']):
        if meta.get('language') == 'flutter':
            doc_type = meta.get('doc_type', 'unknown')
            mixed_flutter_doc_types[doc_type] = mixed_flutter_doc_types.get(doc_type, 0) + 1
    
    print(f"📊 CONTENT TYPE COMPARISON:")
    print(f"Flutter-only DB types: {flutter_doc_types}")
    print(f"Mixed DB Flutter types: {mixed_flutter_doc_types}")
    
    # Value assessment
    unique_percentage = (overlap_analysis['db1_unique'] / flutter_data['total']) * 100
    
    print(f"\n🎯 VALUE ASSESSMENT:")
    print(f"  Unique content: {overlap_analysis['db1_unique']}/{flutter_data['total']} ({unique_percentage:.1f}%)")
    
    if unique_percentage >= 70:
        value_rating = "HIGH VALUE"
        recommendation = "Keep as specialized Flutter documentation database"
    elif unique_percentage >= 40:
        value_rating = "MODERATE VALUE" 
        recommendation = "Consider keeping for specialized Flutter use cases"
    elif unique_percentage >= 20:
        value_rating = "LIMITED VALUE"
        recommendation = "May be redundant, consider archiving"
    else:
        value_rating = "LOW VALUE"
        recommendation = "Likely redundant with mixed database"
    
    print(f"  Value Rating: {value_rating}")
    print(f"  Recommendation: {recommendation}")
    
    # Check for unique documentation sources
    has_unique_docs = any('docs.' in source or 'api.' in source for source in overlap_analysis['unique_sources'])
    has_unique_official = 'T1_Official' in overlap_analysis.get('unique_authorities', {})
    
    if has_unique_docs or has_unique_official:
        print(f"  ✅ Contains unique official documentation sources")
    else:
        print(f"  ⚠️  No unique official documentation detected")
    
    return {
        'value_rating': value_rating,
        'unique_percentage': unique_percentage,
        'recommendation': recommendation,
        'has_unique_docs': has_unique_docs
    }

def main():
    """Main comparison function"""
    
    print("🔍 FLUTTER DATABASE COMPARISON ANALYSIS")
    print("=" * 80)
    
    # Analyze both databases
    flutter_only_data = analyze_database_content(
        "./flutter_only_db", 
        "flutter_dart_knowledge", 
        "FLUTTER-ONLY DATABASE"
    )
    
    mixed_data = analyze_database_content(
        "./rag_db_final", 
        "expert_py_flutter_dart_final", 
        "MIXED PYTHON + FLUTTER DATABASE"
    )
    
    if not flutter_only_data or not mixed_data:
        print("❌ Failed to analyze one or both databases")
        return
    
    # Compare content overlap
    overlap_analysis = find_content_overlap(
        flutter_only_data, mixed_data,
        "FLUTTER-ONLY DB", "MIXED DB"
    )
    
    # Determine value
    value_assessment = determine_flutter_db_value(
        flutter_only_data, mixed_data, overlap_analysis
    )
    
    print(f"\n🏁 FINAL CONCLUSIONS:")
    print(f"  Flutter-only DB: {flutter_only_data['total']} documents")
    print(f"  Mixed DB Flutter content: {sum(1 for m in mixed_data['metadatas'] if m.get('language') == 'flutter')} documents")
    print(f"  Content overlap: {overlap_analysis['overlap_percentage']:.1f}%")
    print(f"  Flutter-only DB value: {value_assessment['value_rating']}")
    print(f"  Recommendation: {value_assessment['recommendation']}")

if __name__ == "__main__":
    main()