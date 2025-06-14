#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions
from collections import defaultdict

def check_database_metadata(db_path, collection_name):
    print(f"\n=== Checking {db_path}/{collection_name} ===")
    
    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_functions.OllamaEmbeddingFunction(
                model_name="nomic-embed-text:latest", 
                url="http://127.0.0.1:11434"
            )
        )
        
        # Get all metadata
        results = collection.get()
        metadatas = results['metadatas']
        
        print(f"Total chunks: {len(metadatas)}")
        
        # Analyze metadata fields
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
                domain = source.split('/')[2] if len(source.split('/')) > 2 else source
                sources[domain] += 1
            else:
                sources['unknown'] += 1
        
        print(f"\nLanguage distribution:")
        for lang, count in sorted(languages.items()):
            print(f"  {lang}: {count}")
            
        print(f"\nAuthority distribution:")
        for auth, count in sorted(authorities.items()):
            print(f"  {auth}: {count}")
            
        print(f"\nDoc type distribution:")
        for doc_type, count in sorted(doc_types.items()):
            print(f"  {doc_type}: {count}")
            
        print(f"\nSource distribution:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {source}: {count}")
            
        # Check for missing critical metadata
        missing_language = sum(1 for meta in metadatas if not meta.get('language'))
        missing_authority = sum(1 for meta in metadatas if not meta.get('authority'))
        
        print(f"\nMissing metadata:")
        print(f"  Missing language: {missing_language}")
        print(f"  Missing authority: {missing_authority}")
        
        return {
            'total': len(metadatas),
            'languages': dict(languages),
            'authorities': dict(authorities),
            'missing_language': missing_language,
            'missing_authority': missing_authority
        }
        
    except Exception as e:
        print(f"Error checking {db_path}: {e}")
        return None

# Check all databases
databases = [
    ("./flutter_only_db", "flutter_dart_knowledge"),
    # Add other databases if they exist
]

for db_path, collection_name in databases:
    check_database_metadata(db_path, collection_name)