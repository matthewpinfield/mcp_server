# ingest_target_flutter_repos.py (V2 - AST Based)
import hashlib
import json
import logging
import os
import subprocess  # For calling the Dart script
import time
from typing import Dict, List, Optional  # Add Optional too, as we might use it

import requests

# --- CONFIGURATION ---
MCP_ADD_KNOWLEDGE_URL = "http://127.0.0.1:8009/mcp/api/v1/invoke/add_to_my_knowledge"
CLONED_REPOS_BASE_PATH = "/mnt/caseSSD/temp_src_repos/"  # Base dir for cloned repos
DART_PARSER_SCRIPT_PATH = (
    "/mnt/caseSSD/mcp_server_project/dart_ast_parser.dart"  # Path to your Dart parser
)

REPOS_TO_PROCESS = {
    # "riverpod": {
    #    "target_subdirs": [
    #        "packages/riverpod/lib",
    #        "packages/flutter_riverpod/lib",
    #        "packages/hooks_riverpod/lib",
    #        "examples/counter/lib",
    #        "examples/marvel/lib",
    #        "examples/todos/lib"
    #    ],
    #    "base_metadata": {"package_group": "riverpod", "main_topic": "state_management", "language": "dart", "framework": "flutter"}
    # },
    # "flutter_plugins": {
    #    "target_subdirs": [
    #        "packages/shared_preferences/shared_preferences/lib",
    #        "packages/shared_preferences/shared_preferences/example/lib",
    #        "packages/path_provider/path_provider/lib",
    #        "packages/path_provider/path_provider_android/lib",
    #        "packages/path_provider/path_provider/example/lib"
    #    ],
    #    "base_metadata": {"main_topic": "flutter_plugins", "language": "dart", "framework": "flutter"}
    # },
    # For initial V2 testing, flutter_sdk is large. Keep it commented out for faster test runs.
    # Uncomment and adjust target_subdirs when ready for a fuller ingestion.
    "flutter_sdk": {
        "target_subdirs": [
            "examples/api/lib/material",
            "examples/api/lib/widgets",
            "examples/api/lib/cupertino",
            "examples/api/lib/painting",
            "examples/api/lib/animation",
        ],
        "base_metadata": {
            "package_group": "flutter_sdk_examples",
            "language": "dart",
            "framework": "flutter",
        },
    }
}

# Parameters for ingestion
MIN_CHUNK_CODE_LENGTH = 20  # Skip very short code blocks from AST parser
BATCH_SIZE = 20  # Number of CHUNKS to send to MCP in one API call
REQUEST_TIMEOUT = 120  # Seconds for HTTP requests to MCP
DART_SCRIPT_TIMEOUT = 60  # Seconds to allow dart_ast_parser.dart to run per file

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger("RepoIngestorV2-AST")


def generate_chunk_id_from_parsed(
    original_filepath: str,
    element_name: str,
    element_type: str,
    chunk_index_in_file: int,
) -> str:
    """Generates a unique ID for a chunk based on its parsed properties."""
    path_hash = hashlib.md5(original_filepath.encode("utf-8")).hexdigest()
    name_hash = hashlib.md5(element_name.encode("utf-8")).hexdigest()[:8]
    type_hash = hashlib.md5(element_type.encode("utf-8")).hexdigest()[:4]
    return f"{path_hash}_{name_hash}_{type_hash}_c{chunk_index_in_file}"


def call_dart_parser(dart_file_path: str) -> List[Dict]:
    """Calls the dart_ast_parser.dart script and returns a list of parsed element dictionaries."""
    parsed_elements = []
    try:
        logger.debug(f"Calling Dart AST parser for: {dart_file_path}")
        process = subprocess.run(
            ["dart", DART_PARSER_SCRIPT_PATH, dart_file_path],
            capture_output=True,
            text=True,
            timeout=DART_SCRIPT_TIMEOUT,
            check=False,  # Don't raise exception for non-zero exit, we'll check stderr
        )

        if process.returncode != 0:
            logger.error(
                f"Dart parser script failed for {dart_file_path}. Return code: {process.returncode}"
            )
            logger.error(
                f"Dart parser stderr: {process.stderr.strip() if process.stderr else 'N/A'}"
            )
            return parsed_elements  # Empty list

        if process.stdout:
            for line in process.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        element_data = json.loads(line)
                        parsed_elements.append(element_data)
                    except json.JSONDecodeError as je:
                        logger.error(
                            f"Failed to decode JSON from Dart parser for file {dart_file_path}: {je} - Line: '{line}'"
                        )
            logger.debug(
                f"Dart parser returned {len(parsed_elements)} elements for {dart_file_path}"
            )
        else:
            logger.warning(
                f"Dart parser returned no stdout for {dart_file_path}. Stderr: {process.stderr.strip() if process.stderr else 'N/A'}"
            )

    except subprocess.TimeoutExpired:
        logger.error(
            f"Dart parser script timed out for {dart_file_path} after {DART_SCRIPT_TIMEOUT} seconds."
        )
    except Exception as e:
        logger.error(
            f"Error calling Dart AST parser for {dart_file_path}: {e}", exc_info=True
        )

    return parsed_elements


def prepare_documents_from_parsed_elements(
    parsed_elements: List[Dict],
    original_dart_filepath: str,  # Full path to the original .dart file
    base_repo_path: str,  # Full path to the root of the cloned repo
    common_repo_metadata: Dict,
) -> List[Dict]:
    """
    Converts the JSON output from dart_ast_parser.dart into documents for ChromaDB.
    """
    chroma_docs = []
    relative_path_in_repo = os.path.relpath(
        original_dart_filepath, start=base_repo_path
    )

    for i, element_data in enumerate(parsed_elements):
        code_block = element_data.get("code_block", "")
        element_name = element_data.get("element_name", "unknown_element")
        element_type = element_data.get("element_type", "unknown_type")
        doc_comment = element_data.get("doc_comment", "")

        if not code_block.strip() or len(code_block.strip()) < MIN_CHUNK_CODE_LENGTH:
            logger.debug(
                f"Skipping very short or empty code block for {element_name} in {relative_path_in_repo}"
            )
            continue

        metadata = {
            **common_repo_metadata,
            "original_filepath": relative_path_in_repo,
            "filename": os.path.basename(original_dart_filepath),
            "source_script": "ingest_target_flutter_repos_v2_ast",
            "ingestion_strategy": "ast_chunk_v2",
            "element_type": element_type,
            "element_name": element_name,
            "doc_comment_summary": doc_comment[:200]
            + ("..." if len(doc_comment) > 200 else ""),  # Store a summary
            "start_line_in_file": element_data.get("start_line"),
            "end_line_in_file": element_data.get("end_line"),
            "chunk_index_in_file": i,  # Index of this chunk as returned by parser for this file
        }

        # Ensure all metadata values are basic types
        for key, value in metadata.items():
            if not isinstance(value, (str, int, float, bool, type(None))):
                metadata[key] = str(value)

        # Use a more robust ID based on multiple factors
        doc_id = generate_chunk_id_from_parsed(
            original_dart_filepath, element_name, element_type, i
        )

        chroma_docs.append(
            {
                "document": code_block,  # The 'document' for ChromaDB is the code block
                "metadata": metadata,
                "id": doc_id,
            }
        )
    return chroma_docs


def send_batch_to_mcp(batch: List[Dict]):
    # ... (send_batch_to_mcp function remains the same as your working V1 ingestion script)
    if not batch:
        return
    documents_to_send = [item["document"] for item in batch]
    metadatas_to_send = [item["metadata"] for item in batch]
    ids_to_send = [item["id"] for item in batch]
    payload = {
        "documents": documents_to_send,
        "metadatas": metadatas_to_send,
        "ids": ids_to_send,
    }
    try:
        logger.info(
            f"Sending batch of {len(batch)} AST-parsed chunks to MCP... First ID: {ids_to_send[0] if ids_to_send else 'N/A'}"
        )
        response = requests.post(
            MCP_ADD_KNOWLEDGE_URL, json=payload, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        response_json = response.json()
        if response_json.get("status") == "success":
            res_result = response_json.get("result", {})
            logger.info(
                f"MCP Add Knowledge Response: {res_result.get('message', 'Success')}"
            )
        else:
            err_msg = response_json.get("error_message", "Unknown error from MCP")
            logger.error(f"MCP Add Knowledge Failed: {err_msg}")
            if (
                response_json.get("result")
                and isinstance(response_json.get("result"), dict)
                and response_json["result"].get("error")
            ):
                logger.error(f"  Detail: {response_json['result']['error']}")
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request failed sending batch to MCP: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error sending batch to MCP: {e}", exc_info=True)


def main():
    logger.info("Starting V2 AST-based ingestion process...")
    total_files_scanned = 0
    total_chunks_prepared = 0
    document_batch = []

    if not os.path.isfile(DART_PARSER_SCRIPT_PATH):
        logger.critical(
            f"Dart AST parser script not found at: {DART_PARSER_SCRIPT_PATH}. Exiting."
        )
        return
    if not os.path.isdir(CLONED_REPOS_BASE_PATH):
        logger.critical(
            f"Base path for cloned repos not found: {CLONED_REPOS_BASE_PATH}. Exiting."
        )
        return

    for repo_folder_name, repo_config in REPOS_TO_PROCESS.items():
        repo_full_path = os.path.join(CLONED_REPOS_BASE_PATH, repo_folder_name)
        if not os.path.isdir(repo_full_path):
            logger.warning(
                f"Repository directory not found, skipping: {repo_full_path}"
            )
            continue

        logger.info(f"Processing repository: {repo_full_path}")
        base_repo_metadata = repo_config.get("base_metadata", {})
        base_repo_metadata["repository_name"] = repo_folder_name

        for target_subdir in repo_config.get("target_subdirs", []):
            current_processing_path = os.path.join(repo_full_path, target_subdir)
            if not os.path.isdir(current_processing_path):
                logger.warning(
                    f"Target subdirectory not found in '{repo_folder_name}', skipping: {current_processing_path}"
                )
                continue

            logger.info(f"  Walking directory: {current_processing_path}")
            for root, _, files in os.walk(current_processing_path):
                for filename in files:
                    if not filename.endswith(".dart"):
                        continue

                    total_files_scanned += 1
                    filepath = os.path.join(root, filename)

                    parsed_elements_from_file = call_dart_parser(filepath)

                    if parsed_elements_from_file:
                        docs_for_chroma = prepare_documents_from_parsed_elements(
                            parsed_elements_from_file,
                            filepath,  # Full path to original .dart file
                            repo_full_path,  # Root of the specific repo being processed
                            base_repo_metadata.copy(),
                        )

                        if docs_for_chroma:
                            document_batch.extend(docs_for_chroma)
                            total_chunks_prepared += len(docs_for_chroma)

                        if len(document_batch) >= BATCH_SIZE:
                            send_batch_to_mcp(document_batch)
                            document_batch = []
                            logger.info("Batch sent. Pausing briefly...")
                            time.sleep(0.5)

            if document_batch:
                logger.info(
                    f"Sending remaining batch for subdir '{target_subdir}' in '{repo_folder_name}'..."
                )
                send_batch_to_mcp(document_batch)
                document_batch = []
                time.sleep(0.5)

    if document_batch:
        logger.info("Sending final batch of documents...")
        send_batch_to_mcp(document_batch)

    logger.info("V2 AST-based Ingestion process finished.")
    logger.info(f"Total .dart files scanned: {total_files_scanned}")
    logger.info(f"Total CHUNKS prepared for ingestion: {total_chunks_prepared}")


if __name__ == "__main__":
    logger.info(
        "This script (V2 AST-based) will use dart_ast_parser.dart to chunk .dart files"
    )
    logger.info("and ingest them into your MCP Server's Knowledge Base.")
    logger.info(f"Ensure your MCP Server is running at {MCP_ADD_KNOWLEDGE_URL}")
    logger.info(f"Dart parser script expected at: {DART_PARSER_SCRIPT_PATH}")
    logger.info(f"Cloned repositories are expected in: {CLONED_REPOS_BASE_PATH}")
    logger.info("Press Ctrl+C to stop the script.")
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Ingestion process interrupted by user.")
    except Exception as e:
        logger.critical(
            f"An unhandled error occurred in the main V2 ingestion script: {e}",
            exc_info=True,
        )
