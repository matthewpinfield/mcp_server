#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions
from collections import defaultdict

def analyze_short_chunks():
    """Analyze the 488 very short chunks to understand what they contain"""
    
    DATABASE_CONFIG = {
        "path": "./rag_db_final",
        "collection_name": "expert_py_flutter_dart_final",
        "embedding_model": "nomic-embed-text:latest"
    }
    OLLAMA_CONFIG = {"base_url": "http://127.0.0.1:11434"}
    
    print(f"\n=== Analyzing Short Chunks (<50 chars) ===")
    
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
        
        # Get all data
        results = collection.get()
        documents = results['documents']
        metadatas = results['metadatas'] 
        ids = results['ids']
        
        # Find short chunks
        short_chunks = []
        for i, doc in enumerate(documents):
            if len(doc) < 50:
                short_chunks.append({
                    'id': ids[i],
                    'text': doc,
                    'length': len(doc),
                    'metadata': metadatas[i]
                })
        
        print(f"Found {len(short_chunks)} short chunks")
        
        # Analyze patterns in short chunks
        languages = defaultdict(int)
        authorities = defaultdict(int)
        doc_types = defaultdict(int)
        length_distribution = defaultdict(int)
        content_patterns = defaultdict(int)
        
        print(f"\n📊 SHORT CHUNK ANALYSIS")
        
        for chunk in short_chunks:
            languages[chunk['metadata'].get('language', 'MISSING')] += 1
            authorities[chunk['metadata'].get('authority', 'MISSING')] += 1
            doc_types[chunk['metadata'].get('doc_type', 'MISSING')] += 1
            
            # Length buckets
            length = chunk['length']
            if length < 10:
                length_distribution['0-9'] += 1
            elif length < 20:
                length_distribution['10-19'] += 1
            elif length < 30:
                length_distribution['20-29'] += 1
            elif length < 40:
                length_distribution['30-39'] += 1
            elif length < 50:
                length_distribution['40-49'] += 1
            
            # Content pattern analysis
            text = chunk['text'].strip()
            if not text:
                content_patterns['empty_after_strip'] += 1
            elif text.startswith('//'):
                content_patterns['comment_only'] += 1
            elif text.startswith('#'):
                content_patterns['comment_or_header'] += 1
            elif text in ['{', '}', '(', ')', '[', ']']:
                content_patterns['bracket_only'] += 1
            elif len(text.split()) <= 2:
                content_patterns['one_two_words'] += 1
            elif text.startswith('import ') or text.startswith('from '):
                content_patterns['import_statement'] += 1
            elif text.startswith('class ') and text.endswith(':'):
                content_patterns['class_declaration'] += 1
            elif text.startswith('def ') and text.endswith(':'):
                content_patterns['function_declaration'] += 1
            else:
                content_patterns['other_short_content'] += 1
        
        print(f"\nLanguage distribution in short chunks:")
        for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(short_chunks)) * 100
            print(f"  {lang}: {count} ({percentage:.1f}%)")
        
        print(f"\nLength distribution:")
        for length_range, count in sorted(length_distribution.items()):
            percentage = (count / len(short_chunks)) * 100
            print(f"  {length_range} chars: {count} ({percentage:.1f}%)")
        
        print(f"\nContent pattern analysis:")
        for pattern, count in sorted(content_patterns.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(short_chunks)) * 100
            print(f"  {pattern}: {count} ({percentage:.1f}%)")
        
        # Show examples of each pattern
        print(f"\n🔍 EXAMPLES OF SHORT CHUNKS")
        
        pattern_examples = defaultdict(list)
        for chunk in short_chunks[:100]:  # Look at first 100
            text = chunk['text'].strip()
            if not text:
                pattern_examples['empty_after_strip'].append(chunk)
            elif text.startswith('//'):
                pattern_examples['comment_only'].append(chunk)
            elif text.startswith('#'):
                pattern_examples['comment_or_header'].append(chunk)
            elif text in ['{', '}', '(', ')', '[', ']']:
                pattern_examples['bracket_only'].append(chunk)
            elif len(text.split()) <= 2:
                pattern_examples['one_two_words'].append(chunk)
            elif text.startswith('import ') or text.startswith('from '):
                pattern_examples['import_statement'].append(chunk)
            else:
                pattern_examples['other_short_content'].append(chunk)
        
        for pattern, examples in pattern_examples.items():
            if examples:
                print(f"\n--- {pattern.upper()} EXAMPLES ---")
                for i, example in enumerate(examples[:3]):  # Show up to 3 examples
                    print(f"Example {i+1} (length {example['length']}):")
                    print(f"  Text: '{example['text']}'")
                    print(f"  Source: {example['metadata'].get('source', 'N/A')[:60]}...")
                    print(f"  Language: {example['metadata'].get('language', 'N/A')}")
        
        # Recommendation
        print(f"\n💡 RECOMMENDATIONS")
        
        truly_useless = (content_patterns['empty_after_strip'] + 
                        content_patterns['bracket_only'] + 
                        content_patterns['one_two_words'])
        
        potentially_useful = (content_patterns['import_statement'] + 
                             content_patterns['class_declaration'] + 
                             content_patterns['function_declaration'])
        
        print(f"Truly useless chunks (empty/brackets/1-2 words): {truly_useless}")
        print(f"Potentially useful chunks (imports/declarations): {potentially_useful}")
        print(f"Comments and other: {len(short_chunks) - truly_useless - potentially_useful}")
        
        if truly_useless > 100:
            print(f"⚠️  RECOMMENDATION: Consider filtering out {truly_useless} truly useless chunks")
            print(f"   This would improve quality score to {((len(documents) - truly_useless) / len(documents) * 100):.1f}%")
        
        return {
            'total_short': len(short_chunks),
            'truly_useless': truly_useless,
            'potentially_useful': potentially_useful,
            'patterns': dict(content_patterns)
        }
        
    except Exception as e:
        print(f"❌ Error analyzing short chunks: {e}")
        return None

if __name__ == "__main__":
    result = analyze_short_chunks()
    if result:
        print(f"\n✅ Short chunk analysis completed.")
    else:
        print(f"\n❌ Short chunk analysis failed.")