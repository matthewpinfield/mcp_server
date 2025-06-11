import requests
import json

# Configuration
RAG_SERVER_URL = "http://localhost:8008/custom_rag_stuff"
# A query you expect to have good results for in your database
TEST_QUERY = "how to use setstate in a statefulwidget"
# Optional: test with a specific model if your RAG server supports it
TEST_MODEL = "qwen3:8b"

def test_rag_retrieval():
    """
    Sends a query to the RAG server and prints the streaming response.
    This bypasses the MCP server entirely to test the RAG component directly.
    """
    print(f"--- Testing RAG Server at {RAG_SERVER_URL} ---")
    print(f"Query: '{TEST_QUERY}'\n")

    payload = {
        "fullInput": TEST_QUERY,
        "model": TEST_MODEL
    }

    try:
        with requests.post(RAG_SERVER_URL, json=payload, stream=True, timeout=60) as response:
            response.raise_for_status()
            print("--- RAG Server Response ---")
            full_response = ""
            # The RAG server streams raw text chunks, not JSON or SSE events
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                print(chunk, end="", flush=True)
                full_response += chunk
            print("\n--- End of RAG Response ---\n")

            if not full_response or "couldn't find any specific information" in full_response:
                print("⚠️  Warning: RAG server returned no specific documents. The DB might not contain relevant info for the query.")
            elif "timeout" in full_response.lower():
                 print("❌ Error: RAG server reported a timeout. Check its logs.")
            else:
                print("✅ Success: RAG server returned a response. Manually verify its relevance.")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAILED to connect to RAG server: {e}")
        print("    Is the RAG server (optimal_server.py) running on port 8008?")

if __name__ == "__main__":
    test_rag_retrieval()
    