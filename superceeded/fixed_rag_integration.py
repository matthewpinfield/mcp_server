#!/usr/bin/env python3
"""
Fixed RAG Integration - Handles both JSON and text responses
"""

import requests
import json
import logging
from typing import Dict, Any, Union

def call_rag_server_robust(query: str, endpoint: str = "http://localhost:8008/custom_rag_stuff") -> Dict[str, Any]:
    """
    Robustly call RAG server, handling both JSON and text responses.
    
    Args:
        query: The query to send to RAG server
        endpoint: RAG server endpoint URL
        
    Returns:
        Dict containing the result or error information
    """
    try:
        logging.info(f"Calling RAG server with query: {query}")
        
        response = requests.post(
            endpoint,
            json={"fullInput": query},
            timeout=120
        )
        response.raise_for_status()
        
        # Check content type to determine how to parse response
        content_type = response.headers.get('content-type', '').lower()
        
        if 'application/json' in content_type:
            # Try JSON parsing for JSON content type
            try:
                rag_result = response.json()
                logging.info(f"RAG server returned JSON: {type(rag_result)}")
                return rag_result
            except json.JSONDecodeError as e:
                logging.warning(f"JSON parsing failed despite JSON content-type: {e}")
                # Fallback to text
                return {'retrieved_documentation': response.text}
                
        elif 'text/' in content_type or 'text/event-stream' in content_type:
            # Handle text responses (your current case)
            text_content = response.text.strip()
            logging.info(f"RAG server returned text (length: {len(text_content)})")
            
            if not text_content:
                return {'error': 'RAG server returned empty response'}
                
            # Try to parse as JSON first (in case content-type is wrong)
            if text_content.startswith(('{', '[')):
                try:
                    parsed = json.loads(text_content)
                    logging.info("Text response was actually valid JSON")
                    return parsed
                except json.JSONDecodeError:
                    pass  # Fall through to text handling
            
            # Return as text content
            return {'retrieved_documentation': text_content}
            
        else:
            # Unknown content type, try both approaches
            logging.warning(f"Unknown content type: {content_type}")
            
            # Try JSON first
            try:
                return response.json()
            except json.JSONDecodeError:
                # Fallback to text
                return {'retrieved_documentation': response.text}
                
    except requests.exceptions.HTTPError as e:
        error_text = getattr(e.response, 'text', 'N/A') if hasattr(e, 'response') else 'N/A'
        logging.error(f"HTTP error calling RAG server: {e} - Response: {error_text}")
        return {'error': f'HTTP error calling RAG server: {str(e)}'}
        
    except requests.exceptions.ConnectionError:
        logging.error("Could not connect to RAG server")
        return {'error': 'Could not connect to RAG server - check if it is running'}
        
    except requests.exceptions.Timeout:
        logging.error("RAG server request timed out")
        return {'error': 'RAG server request timed out'}
        
    except Exception as e:
        logging.error(f"Unexpected error calling RAG server: {e}", exc_info=True)
        return {'error': f'Unexpected error calling RAG server: {str(e)}'}


# Example usage for your FlutterDocTool
class FixedFlutterDocTool:
    """Example of how to integrate the robust RAG calling into your tool."""
    
    def call(self, params: Union[str, Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        try:
            if isinstance(params, str):
                try:
                    params_dict = json.loads(params)
                except json.JSONDecodeError:
                    logging.error(f"Could not parse params string: {params}")
                    return {'error': 'Invalid JSON format for parameters.'}
            else:
                params_dict = params
            
            query = params_dict.get('query')
            if not query:
                logging.error("'query' parameter is missing.")
                return {'error': 'The "query" parameter is missing.'}
            
            # Use the robust RAG caller
            return call_rag_server_robust(query)
            
        except Exception as e:
            logging.error(f"Error in FlutterDocTool: {e}", exc_info=True)
            return {'error': f'Unexpected error in RAG tool: {str(e)}'}


if __name__ == "__main__":
    # Test the robust caller
    logging.basicConfig(level=logging.INFO)
    
    test_queries = [
        "What is Flutter?",
        "How to create a widget?",
        "test query"
    ]
    
    for query in test_queries:
        print(f"\n🧪 Testing query: {query}")
        result = call_rag_server_robust(query)
        print(f"Result type: {type(result)}")
        print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        if 'error' in result:
            print(f" Error: {result['error']}")
        else:
            content = result.get('retrieved_documentation', str(result))
            print(f" Content preview: {content[:100]}...")