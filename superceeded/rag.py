#!/usr/bin/env python3
"""
RAG Tools - Retrieval Augmented Generation
==========================================

This module contains RAG and Flutter documentation tools for the MCP server.
"""

import json
import logging
from typing import Type

from langchain_core.tools import BaseTool as LangchainBaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FlutterDocSchema(BaseModel):
    query: str = Field(description="Flutter/Dart documentation query")
    max_results: int = Field(description="Maximum results", default=5)


class CodeSearchSchema(BaseModel):
    query: str = Field(description="Code example search query")
    max_results: int = Field(description="Maximum results", default=5)


class LangchainFlutterDocTool(LangchainBaseTool):
    name: str = "query_flutter_dart_documentation"
    description: str = (
        "Queries a knowledge base of Flutter/Dart documentation to answer technical questions about Flutter or Dart. Use this for specific Flutter/Dart coding questions, error explanations, or finding documentation."
    )
    args_schema: Type[BaseModel] = FlutterDocSchema

    def _run(self, query: str, max_results: int = 5) -> str:
        logger.info(f" RAG Tool: Received query: '{query}'")
        try:
            import requests

            from config import RAG_SERVER_ENDPOINT, REQUEST_TIMEOUT

            response = requests.post(
                RAG_SERVER_ENDPOINT,
                params={"query": query, "limit": max_results},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            try:
                rag_json = response.json()
                if isinstance(rag_json, dict) and "results" in rag_json:
                    # Handle dual endpoint server response format
                    results = rag_json["results"]
                    if results:
                        result_text = f" **Flutter/Dart Documentation Results** (Database: {rag_json.get('database', 'unknown')})\n\n"
                        for i, result in enumerate(
                            results[:3], 1
                        ):  # Show top 3 results
                            text = result.get("text", "").strip()
                            if len(text) > 800:
                                text = text[:800] + "..."
                            result_text += f"**Result {i}:**\n{text}\n\n"
                    else:
                        result_text = "No relevant documentation found."
                elif isinstance(rag_json, dict):
                    # Fallback for other response formats
                    if "answer" in rag_json:
                        result_text = rag_json["answer"]
                    elif "text" in rag_json:
                        result_text = rag_json["text"]
                    elif "content" in rag_json:
                        result_text = rag_json["content"]
                    else:
                        result_text = json.dumps(rag_json)
                else:
                    result_text = json.dumps(rag_json)
            except ValueError:
                result_text = response.text

            logger.info(
                f" RAG Tool: Successfully retrieved documentation (length: {len(result_text)})."
            )
            return f"Documentation found for query '{query}':\n{result_text}"

        except Exception as e:
            logger.error(f" RAG Tool: Error: {e}")
            return f"Error during RAG tool execution: {str(e)}"

    async def _arun(self, query: str, max_results: int = 5) -> str:
        return self._run(query, max_results)


class LangchainCodeSearchTool(LangchainBaseTool):
    name: str = "search_code_examples"
    description: str = (
        "Search Python and Flutter code examples from the code database using RAG system"
    )
    args_schema: Type[BaseModel] = CodeSearchSchema

    def _run(self, query: str, max_results: int = 5) -> str:
        logger.info(f"Code Search: query='{query}', max_results={max_results}")
        try:
            import requests

            from config import RAG_CODE_ENDPOINT, REQUEST_TIMEOUT

            response = requests.post(
                RAG_CODE_ENDPOINT,
                params={"query": query, "limit": max_results},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            result = response.json()

            # Handle dual endpoint response format
            if result and result.get("results"):
                docs = result.get("results", [])
                if docs:
                    formatted_response = f"Code Examples for '{query}':\n\n"
                    for i, doc in enumerate(docs, 1):
                        title = doc.get("title", "Unknown")
                        content = doc.get("content", "")[:400] + "..."
                        source = doc.get("source", "Unknown")

                        formatted_response += f"{i}. **{title}**\n"
                        formatted_response += f"   Source: {source}\n"
                        formatted_response += f"   {content}\n\n"

                    logger.info(f"Code Search Tool: Found {len(docs)} results")
                    return formatted_response
                else:
                    return f"No code examples found for '{query}'"
            else:
                return f"Code search failed: {result.get('error', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Code Search Tool error: {e}")
            return f"Code search error: {str(e)}"

    async def _arun(self, query: str, max_results: int = 5) -> str:
        return self._run(query, max_results)
