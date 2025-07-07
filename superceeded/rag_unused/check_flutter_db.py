#!/usr/bin/env python3

import chromadb
from chromadb.utils import embedding_functions

# Connect to the Flutter database
client = chromadb.PersistentClient(path="./flutter_only_db")
collection = client.get_collection(
    name="flutter_dart_knowledge",
    embedding_function=embedding_functions.OllamaEmbeddingFunction(
        model_name="nomic-embed-text:latest", 
        url="http://127.0.0.1:11434"
    )
)

# Get basic stats
count = collection.count()
print(f"Total chunks in database: {count}")

# Sample a few chunks to see what we have
results = collection.peek(limit=5)
print(f"\nSample chunks:")
for i, (doc, metadata) in enumerate(zip(results['documents'], results['metadatas'])):
    print(f"\n--- Chunk {i+1} ---")
    print(f"Source: {metadata.get('source', 'Unknown')}")
    print(f"Language: {metadata.get('language', 'Unknown')}")
    print(f"Authority: {metadata.get('authority', 'Unknown')}")
    print(f"Content preview: {doc[:200]}...")

# Check language distribution
all_results = collection.get()
languages = {}
authorities = {}
for metadata in all_results['metadatas']:
    lang = metadata.get('language', 'unknown')
    auth = metadata.get('authority', 'unknown')
    languages[lang] = languages.get(lang, 0) + 1
    authorities[auth] = authorities.get(auth, 0) + 1

print(f"\nLanguage distribution:")
for lang, count in languages.items():
    print(f"  {lang}: {count}")

print(f"\nAuthority distribution:")
for auth, count in authorities.items():
    print(f"  {auth}: {count}")