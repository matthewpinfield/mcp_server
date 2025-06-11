#!/usr/bin/env python3
# Ollama Function Execution Server - The RIGHT Way

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import logging
import os

# Configuration
RAG_SERVER_ENDPOINT = os.getenv("RAG_SERVER_ENDPOINT", "http://localhost:8008/custom_rag_stuff")
FUNCTION_SERVER_PORT = int(os.getenv("FUNCTION_SERVER_PORT", "8010"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ollama Function Execution Server")

class FunctionCall(BaseModel):
    name: str
    arguments: dict

@app.post("/execute_function")
async def execute_function(function_call: FunctionCall):
    """Execute function calls from Ollama"""
    try:
        if function_call.name == "query_flutter_docs":
            query = function_call.arguments.get("query")
            if not query:
                return {"error": "Query parameter required"}
            
            logger.info(f"Executing Flutter docs query: {query}")
            
            # Call your RAG server
            response = requests.post(
                RAG_SERVER_ENDPOINT,
                json={"fullInput": query},
                timeout=30
            )
            response.raise_for_status()
            
            # Return the documentation
            return {
                "result": response.text,
                "source": "Flutter/Dart Documentation"
            }
        else:
            return {"error": f"Unknown function: {function_call.name}"}
            
    except Exception as e:
        logger.error(f"Function execution error: {e}")
        return {"error": str(e)}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    logger.info(f"Starting Ollama Function Server on port {FUNCTION_SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=FUNCTION_SERVER_PORT)