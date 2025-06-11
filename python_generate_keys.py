import secrets

def generate_api_key(length=32):
    return secrets.token_urlsafe(length)

rag_api_key_value = generate_api_key()
memory_api_key_value = generate_api_key()

print(f"Generated RAG API Key: {rag_api_key_value}")
print(f"Generated Memory API Key: {memory_api_key_value}")