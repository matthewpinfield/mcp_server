#!/usr/bin/env python3
"""
Comprehensive RAG Document Processor for Dart & Flutter.
# ... (rest of the docstring)
"""
import os
import glob
import time
import logging
from typing import List, Union, Dict, Any, Set
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

import lancedb
import ollama
import requests
from bs4 import BeautifulSoup, Tag # Keep Tag for potential type hints
import git
import pyarrow

# --- Configuration for logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("git").setLevel(logging.INFO) # Allow git INFO for cloning/fetching visibility

# --- Configuration ---
FLUTTER_SDK_PATH = "/mnt/caseSSD/dev_docs/flutter"
DART_SITE_PATH = "/mnt/my_nas_dev_docs/dart_site_www"
DART_SDK_PATH = "/mnt/caseSSD/dev_docs/sdk"

FLUTTER_SAMPLES_REPO_URL = "https://github.com/flutter/samples.git"
FLUTTER_SAMPLES_CLONE_PATH = "/mnt/caseSSD/dev_docs/flutter_samples"

FLUTTER_DOCS_SITES = {
    "flutter_docs_flutter_dev": [
        "https://docs.flutter.dev/", "https://docs.flutter.dev/ui",
        "https://docs.flutter.dev/ui/widgets", "https://docs.flutter.dev/ui/widgets/basics",
        "https://docs.flutter.dev/ui/widgets/material", "https://docs.flutter.dev/cookbook",
        "https://docs.flutter.dev/cookbook/navigation", "https://docs.flutter.dev/cookbook/forms",
        "https://docs.flutter.dev/cookbook/gestures", "https://docs.flutter.dev/cookbook/images",
        "https://docs.flutter.dev/cookbook/lists", "https://docs.flutter.dev/cookbook/networking",
        "https://docs.flutter.dev/cookbook/persistence",
        "https://docs.flutter.dev/development/data-and-backend/state-mgmt/options",
        "https://docs.flutter.dev/development/data-and-backend/state-mgmt/simple",
        "https://docs.flutter.dev/development/ui/layout",
        "https://docs.flutter.dev/development/ui/layout/constraints",
        "https://docs.flutter.dev/development/accessibility-and-localization/accessibility",
        "https://docs.flutter.dev/performance/overview", "https://docs.flutter.dev/performance/best-practices",
        "https://docs.flutter.dev/testing", "https://docs.flutter.dev/deployment/android",
        "https://docs.flutter.dev/deployment/ios", "https://docs.flutter.dev/get-started/install",
        "https://docs.flutter.dev/tools/vs-code", "https://docs.flutter.dev/tools/android-studio",
        "https://docs.flutter.dev/tools/flutter-fix",
        "https://docs.flutter.dev/development/tools/devtools/overview"
    ],
    "flutter_api_flutter_dev": [
        "https://api.flutter.dev/flutter/widgets/Widget-class.html",
        "https://api.flutter.dev/flutter/widgets/StatelessWidget-class.html",
        "https://api.flutter.dev/flutter/widgets/StatefulWidget-class.html",
        "https://api.flutter.dev/flutter/widgets/State-class.html",
        "https://api.flutter.dev/flutter/widgets/BuildContext-class.html",
        "https://api.flutter.dev/flutter/widgets/Key-class.html",
        "https://api.flutter.dev/flutter/foundation/ChangeNotifier-class.html",
        "https://api.flutter.dev/flutter/material/MaterialApp-class.html",
        "https://api.flutter.dev/flutter/material/Scaffold-class.html",
        "https://api.flutter.dev/flutter/material/AppBar-class.html",
        "https://api.flutter.dev/flutter/widgets/Text-class.html",
        "https://api.flutter.dev/flutter/widgets/Container-class.html",
        "https://api.flutter.dev/flutter/widgets/Row-class.html",
        "https://api.flutter.dev/flutter/widgets/Column-class.html",
        "https://api.flutter.dev/flutter/widgets/Stack-class.html",
        "https://api.flutter.dev/flutter/widgets/Expanded-class.html",
        "https://api.flutter.dev/flutter/widgets/ListView-class.html",
        "https://api.flutter.dev/flutter/widgets/GridView-class.html",
        "https://api.flutter.dev/flutter/material/ElevatedButton-class.html",
        "https://api.flutter.dev/flutter/material/TextButton-class.html",
        "https://api.flutter.dev/flutter/material/IconButton-class.html",
        "https://api.flutter.dev/flutter/material/Card-class.html",
        "https://api.flutter.dev/flutter/widgets/Image-class.html",
        "https://api.flutter.dev/flutter/material/TextField-class.html",
        "https://api.flutter.dev/flutter/widgets/Form-class.html",
        "https://api.flutter.dev/flutter/widgets/Navigator-class.html",
        "https://api.flutter.dev/flutter/widgets/PageRouteBuilder-class.html",
        "https://api.flutter.dev/flutter/animation/AnimationController-class.html",
        "https://api.flutter.dev/flutter/animation/Tween-class.html",
        "https://api.flutter.dev/flutter/animation/AnimatedWidget-class.html",
        "https://api.flutter.dev/flutter/dart-ui/Canvas-class.html",
        "https://api.flutter.dev/flutter/rendering/CustomPaint-class.html",
        "https://api.flutter.dev/flutter/painting/TextStyle-class.html",
        "https://api.flutter.dev/flutter/services/AssetBundle-class.html",
        "https://api.flutter.dev/flutter/gestures/GestureDetector-class.html",
    ],
    "dart_api_dart_dev": [
        "https://api.dart.dev/stable/dart-core/Object-class.html",
        "https://api.dart.dev/stable/dart-core/String-class.html",
        "https://api.dart.dev/stable/dart-core/int-class.html",
        "https://api.dart.dev/stable/dart-core/double-class.html",
        "https://api.dart.dev/stable/dart-core/bool-class.html",
        "https://api.dart.dev/stable/dart-core/List-class.html",
        "https://api.dart.dev/stable/dart-core/Map-class.html",
        "https://api.dart.dev/stable/dart-core/Set-class.html",
        "https://api.dart.dev/stable/dart-core/Iterable-class.html",
        "https://api.dart.dev/stable/dart-core/DateTime-class.html",
        "https://api.dart.dev/stable/dart-core/Duration-class.html",
        "https://api.dart.dev/stable/dart-core/Uri-class.html",
        "https://api.dart.dev/stable/dart-core/RegExp-class.html",
        "https://api.dart.dev/stable/dart-core/Error-class.html",
        "https://api.dart.dev/stable/dart-async/Future-class.html",
        "https://api.dart.dev/stable/dart-async/Stream-class.html",
        "https://api.dart.dev/stable/dart-convert/JsonEncoder-class.html",
        "https://api.dart.dev/stable/dart-convert/JsonDecoder-class.html",
        "https://api.dart.dev/stable/dart-convert/utf8-constant.html",
        "https://api.dart.dev/stable/dart-math/Random-class.html",
        "https://api.dart.dev/stable/dart-math/Point-class.html",
        "https://api.dart.dev/stable/dart-io/File-class.html",
        "https://api.dart.dev/stable/dart-io/Directory-class.html",
        "https://api.dart.dev/stable/dart-io/HttpClient-class.html",
        "https://api.dart.dev/stable/dart-io/Process-class.html",
        "https://api.dart.dev/stable/dart-typed_data/ByteBuffer-class.html",
        "https://api.dart.dev/stable/dart-collection/HashMap-class.html",
        "https://api.dart.dev/stable/dart-developer/log.html",
    ]
}
MAX_SCRAPE_DEPTH = 0
MAX_PAGES_PER_SITE = 75 # Adjust as needed, more pages = longer processing

DB_PATH = "/mnt/caseSSD/continue_custom_rag/lancedb_data/"
TABLE_NAME = "flutter_dart_docs_comprehensive"
EMBEDDING_MODEL = "nomic-embed-text:latest" # Ensure this model is pulled in Ollama

Path(DB_PATH).mkdir(parents=True, exist_ok=True)
if FLUTTER_SAMPLES_CLONE_PATH:
    Path(os.path.dirname(FLUTTER_SAMPLES_CLONE_PATH)).mkdir(parents=True, exist_ok=True)

logger.info(f"DB_PATH: {DB_PATH}")
logger.info(f"FLUTTER_SDK_PATH: {FLUTTER_SDK_PATH}")
logger.info(f"DART_SITE_PATH: {DART_SITE_PATH}")
logger.info(f"DART_SDK_PATH: {DART_SDK_PATH}")
logger.info(f"FLUTTER_SAMPLES_CLONE_PATH: {FLUTTER_SAMPLES_CLONE_PATH}")

def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def get_text_chunks(text: str, chunk_size: int, chunk_overlap: int, source_type: str = "text") -> List[str]:
    if not text or not text.strip(): return []
    if len(text) <= chunk_size: return [clean_text(text)]
    chunks = []
    start_index = 0
    while start_index < len(text):
        end_index = min(start_index + chunk_size, len(text))
        chunk = text[start_index:end_index]
        cleaned_chunk = clean_text(chunk)
        if cleaned_chunk: chunks.append(cleaned_chunk)
        if end_index == len(text): break
        start_index += (chunk_size - chunk_overlap)
        if start_index >= end_index and chunk_size > chunk_overlap and chunk_overlap > 0:
            logger.warning(f"Chunking progression issue for {source_type}: start_index {start_index}, end_index {end_index}. Breaking.")
            break
        if start_index >= len(text): break
    return [c for c in chunks if c]

def process_local_markdown_folder(folder_path: str, repo_name: str) -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []
    logger.info(f"Processing LOCAL MARKDOWN folder: {folder_path} for repo: {repo_name}")
    file_extension = ".md"
    top_level_files_to_check = ["README.md", "CONTRIBUTING.md", "CHANGELOG.md"]
    if repo_name.lower() == "dart_sdk": top_level_files_to_check.append("README.dart-sdk")
    path_prefix_map = {"flutter_sdk": FLUTTER_SDK_PATH, "dart_site": DART_SITE_PATH, "dart_sdk": DART_SDK_PATH}
    base_path_for_repo = path_prefix_map.get(repo_name.lower(), folder_path)
    specific_repo_patterns = []
    if repo_name.lower() == "flutter_sdk":
        specific_repo_patterns = [
            os.path.join(folder_path, "dev/docs", "**", f"*{file_extension}"),
            os.path.join(folder_path, "packages", "*", "README.md"),
            os.path.join(folder_path, "packages", "*", "**/README.md"),
            os.path.join(folder_path, "packages/flutter_tools/doc", "**", f"*{file_extension}"),
            os.path.join(folder_path, "docs", "**", f"*{file_extension}"),
            os.path.join(folder_path, "examples", "**", "README.md"),
        ]
    elif repo_name.lower() == "dart_site":
        specific_repo_patterns = [os.path.join(folder_path, "src", "**", f"*{file_extension}")]
    elif repo_name.lower() == "dart_sdk":
        specific_repo_patterns = [
            os.path.join(folder_path, "pkg", "**", f"*{file_extension}"),
            os.path.join(folder_path, "runtime", "docs", "**", f"*{file_extension}"),
            os.path.join(folder_path, "sdk", "lib", "**", f"*{file_extension}"),
            os.path.join(folder_path, "tools", "**", f"*{file_extension}"),
            os.path.join(folder_path, "tests", "**", f"*{file_extension}"),
        ]
    else: specific_repo_patterns = [os.path.join(folder_path, "**", f"*{file_extension}")]
    md_files_to_process_set: Set[str] = set()
    for pattern in specific_repo_patterns:
        try:
            found_files = glob.glob(pattern, recursive=True)
            for f_path in found_files:
                if os.path.isfile(f_path) and "third_party/txt/src/unicode" not in f_path: # Example exclusion
                    md_files_to_process_set.add(os.path.abspath(f_path))
        except Exception as e: logger.warning(f"Glob pattern error {pattern}: {e}")
    for top_file in top_level_files_to_check:
        full_path = os.path.abspath(os.path.join(folder_path, top_file))
        if os.path.isfile(full_path): md_files_to_process_set.add(full_path)
    md_files_to_process = sorted(list(md_files_to_process_set))
    logger.info(f"  Found {len(md_files_to_process)} unique markdown files for {repo_name}.")
    for file_idx, filepath in enumerate(md_files_to_process):
        if (file_idx + 1) % 100 == 0: logger.info(f"    MD {repo_name}: Processing file {file_idx + 1}/{len(md_files_to_process)}: {os.path.basename(filepath)}")
        try:
            with open(filepath, "r", encoding="utf-8", errors='ignore') as f: content = f.read()
            if not content.strip(): continue
            chunks = get_text_chunks(content, 1000, 150, f"markdown_doc:{repo_name}")
            try: rel_path = os.path.relpath(filepath, base_path_for_repo)
            except ValueError: rel_path = os.path.basename(filepath)
            safe_rel_path = rel_path.replace(os.sep, "_").replace("-","_").replace(".","_") # Sanitize for DB
            for i, chunk_text in enumerate(chunks):
                documents.append({
                    "text": chunk_text, "source_type": "markdown_doc", "repo_source": repo_name,
                    "source_path": rel_path, "chunk_id": f"{repo_name}_md_{safe_rel_path}_{i}"
                })
        except Exception as e: logger.warning(f"Error processing MD file {filepath}: {e}")
    logger.info(f"  Finished MD processing for {repo_name}. Chunks created: {len(documents)}")
    return documents

def scrape_website(site_key: str, start_urls: List[str], max_depth: int, max_pages: int) -> List[Dict[str, Any]]:
    logger.info(f"Scraping website: {site_key}. Max depth: {max_depth}, Max pages: {max_pages}. Initial URLs: {len(start_urls)}")
    documents: List[Dict[str, Any]] = []
    visited_urls: Set[str] = set()
    urls_to_visit: List[tuple[str, int]] = []
    for url in start_urls:
        if isinstance(url, str) and url not in visited_urls and len(urls_to_visit) < max_pages * 2:
             urls_to_visit.append((url, 0))
        elif not isinstance(url, str): logger.warning(f"  Invalid URL found for {site_key}: {url}. Skipping.")
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; RAGBuilderBot/1.0; +https://your-contact-page.com)'} # Polite bot
    processed_pages_count = 0
    while urls_to_visit and processed_pages_count < max_pages:
        current_url, current_depth = urls_to_visit.pop(0)
        if current_url in visited_urls: continue
        logger.info(f"  Scraping URL (depth {current_depth}, {processed_pages_count+1}/{max_pages}): {current_url}")
        visited_urls.add(current_url)
        processed_pages_count += 1
        try:
            time.sleep(0.75) # Be nice
            response = requests.get(current_url, headers=headers, timeout=20)
            response.raise_for_status()
            if 'text/html' not in response.headers.get('Content-Type', '').lower():
                logger.debug(f"    Skipping non-HTML: {current_url} (Content-Type: {response.headers.get('Content-Type')})")
                continue
            soup = BeautifulSoup(response.content, 'html.parser')
            title_tag = soup.find('title')
            title = title_tag.string.strip() if title_tag and title_tag.string else current_url # Robust access
            main_content_area = None
            selectors = ['article', 'main', 'div[role="main"]', 'div.main-content', 'div.content', 'div.body', 'td.content', '.article-content', '.post-content', '.entry-content', '#main-content', '#content', '#article']
            for selector in selectors:
                main_content_area = soup.select_one(selector)
                if main_content_area: logger.debug(f"    Found main content via '{selector}' for {current_url}"); break
            if not main_content_area: main_content_area = soup.body; logger.debug(f"    Using body for {current_url}")
            if main_content_area:
                for unwanted_selector in ['nav', 'header', 'footer', 'aside', '.toc', '.sidebar', 'script', 'style', '.breadcrumb', '.skip-link', 'form', 'button.copylink', '.related-links', '.page-nav', 'div[aria-hidden="true"]']:
                    for tag_to_remove in main_content_area.select(unwanted_selector): tag_to_remove.decompose()
                text_content = main_content_area.get_text(separator='\n', strip=True)
                if text_content.strip():
                    chunks = get_text_chunks(text_content, 1200, 200, f"html_doc:{site_key}")
                    safe_url_path = current_url.replace('https://','').replace('http://','').replace('/','_').replace('?','_').replace('=','_').replace('&','_').replace(':','_').replace('.','_')
                    for i, chunk_text in enumerate(chunks):
                        documents.append({"text": chunk_text, "source_type": "html_doc", "repo_source": site_key, "source_path": current_url, "document_title": title, "chunk_id": f"{site_key}_html_{safe_url_path}_{i}"})
            if current_depth < max_depth:
                base_url_parsed = urlparse(current_url)
                for link_tag in soup.find_all('a', href=True):
                    href_value = link_tag.get('href')
                    if not isinstance(href_value, str):
                        if href_value is not None: logger.debug(f"    Skipping non-string href: {href_value} from {link_tag} at {current_url}")
                        continue
                    if not href_value or href_value.startswith('#') or href_value.lower().startswith('mailto:') or href_value.lower().startswith('javascript:'): continue
                    next_url = urljoin(current_url, href_value)
                    next_url_parsed = urlparse(next_url)
                    if (base_url_parsed.netloc == next_url_parsed.netloc or (next_url_parsed.netloc.endswith('.flutter.dev') and base_url_parsed.netloc.endswith('.flutter.dev')) or (next_url_parsed.netloc.endswith('.dart.dev') and base_url_parsed.netloc.endswith('.dart.dev'))):
                        if next_url not in visited_urls and len(urls_to_visit) < max_pages * 2.5 : urls_to_visit.append((next_url, current_depth + 1))
        except requests.RequestException as e: logger.warning(f"    Request error for {current_url}: {e}")
        except Exception as e: logger.error(f"    HTML processing error for {current_url}: {e}", exc_info=False)
    logger.info(f"  Finished scraping for {site_key}. Visited: {processed_pages_count}. Chunks: {len(documents)}")
    return documents

def process_code_samples_repo(repo_url: str, clone_path: str, repo_name: str) -> List[Dict[str, Any]]:
    logger.info(f"Processing CODE SAMPLES repo: {repo_url} into {clone_path}")
    documents: List[Dict[str, Any]] = []
    try:
        if os.path.exists(os.path.join(clone_path, ".git")):
            logger.info(f"  Repository {repo_name} exists. Attempting fetch and reset.")
            repo = git.Repo(clone_path)
            try:
                repo.remotes.origin.fetch(prune=True)
                default_branch = 'main'
                try: repo.remotes.origin.refs.main
                except AttributeError: default_branch = 'master' # Fallback for older repos
                logger.info(f"  Checking out and resetting to origin/{default_branch}")
                repo.git.checkout(f'origin/{default_branch}', '-f')
                repo.git.reset('--hard', f'origin/{default_branch}')
                repo.git.clean('-fdx') # Remove untracked files/dirs
                logger.info(f"  Repo {repo_name} updated to origin/{default_branch}.")
            except git.GitCommandError as fetch_err: logger.warning(f"  Could not update repo {repo_name}: {fetch_err}. Using local.")
        else:
            logger.info(f"  Cloning repo {repo_name} from {repo_url}...")
            repo = git.Repo.clone_from(repo_url, clone_path, depth=1, single_branch=True) # Shallow clone
        logger.info(f"  Repo {repo_name} ready at {clone_path}")
    except git.GitCommandError as e: logger.error(f"Git error for {repo_name}: {e}"); return documents
    except Exception as e: logger.error(f"Error with repo {repo_name}: {e}"); return documents
    dart_files_count, readme_files_count = 0, 0
    for root, _, files in os.walk(clone_path):
        if ".git" in root: continue # Skip .git folder
        for file in files:
            filepath = os.path.join(root, file)
            rel_filepath = os.path.relpath(filepath, clone_path)
            try:
                if file.endswith(".dart"):
                    dart_files_count +=1
                    with open(filepath, "r", encoding="utf-8", errors='ignore') as f: content = f.read()
                    if content.strip():
                        chunks = get_text_chunks(content, 2000, 300, f"dart_code:{repo_name}")
                        safe_rel_path = rel_filepath.replace(os.sep,'_').replace("-","_").replace(".","_")
                        for i, chunk_text in enumerate(chunks): documents.append({"text": chunk_text, "source_type": "dart_code", "repo_source": repo_name, "source_path": rel_filepath, "chunk_id": f"{repo_name}_code_{safe_rel_path}_{i}"})
                elif file.lower() == "readme.md": # Be specific for READMEs
                    readme_files_count +=1
                    with open(filepath, "r", encoding="utf-8", errors='ignore') as f: content = f.read()
                    if content.strip():
                        chunks = get_text_chunks(content, 1000, 150, f"readme_doc:{repo_name}")
                        safe_rel_path = rel_filepath.replace(os.sep,'_').replace("-","_").replace(".","_")
                        for i, chunk_text in enumerate(chunks): documents.append({"text": chunk_text, "source_type": "markdown_doc", "repo_source": repo_name, "source_path": rel_filepath, "associated_code_dir": os.path.dirname(rel_filepath), "chunk_id": f"{repo_name}_readme_{safe_rel_path}_{i}"})
            except Exception as e: logger.warning(f"    Error processing file {filepath} in {repo_name}: {e}")
    logger.info(f"  Finished code samples for {repo_name}. Dart files: {dart_files_count}, READMEs: {readme_files_count}. Chunks: {len(documents)}")
    return documents

def get_embeddings_batch(texts: List[str], model_name: str = EMBEDDING_MODEL, batch_size: int = 15) -> List[Union[List[float], None]]:
    all_embeddings_results: List[Union[List[float], None]] = [None] * len(texts)
    num_batches = (len(texts) + batch_size - 1) // batch_size
    logger.info(f"Starting embedding generation for {len(texts)} chunks in {num_batches} batches of size {batch_size}.")
    for batch_num in range(num_batches):
        start_idx, end_idx = batch_num * batch_size, min((batch_num + 1) * batch_size, len(texts))
        batch_texts = texts[start_idx:end_idx]
        logger.info(f"  Embedding batch {batch_num + 1}/{num_batches} (indices {start_idx}-{end_idx-1}, {len(batch_texts)} chunks)")
        for i, text_chunk in enumerate(batch_texts):
            actual_original_index = start_idx + i
            if not text_chunk or not text_chunk.strip(): logger.debug(f"    Skipping empty chunk at original index {actual_original_index}."); continue
            try:
                response = ollama.embeddings(model=model_name, prompt=text_chunk)
                all_embeddings_results[actual_original_index] = response["embedding"]
            except Exception as e: logger.error(f"    Error embedding chunk at original index {actual_original_index}: {e}")
        if batch_num < num_batches -1 : time.sleep(0.25) # Small delay
    logger.info("Finished embedding generation for all batches.")
    return all_embeddings_results

def main():
    logger.info("--- Comprehensive RAG Document Processor Starting ---")
    try:
        logger.info("Connecting to Ollama to verify model availability...")
        ollama_list_response = ollama.list()
        available_models = []
        if ollama_list_response and 'models' in ollama_list_response and isinstance(ollama_list_response['models'], list):
            for model_object in ollama_list_response['models']:
                if hasattr(model_object, 'model') and isinstance(model_object.model, str):
                    available_models.append(model_object.model)
                elif hasattr(model_object, 'name') and isinstance(model_object.name, str):
                    available_models.append(model_object.name)
        else:
            logger.warning(f"Ollama list response was not in the expected format or empty. Response: {ollama_list_response}")
        logger.info(f"Available Ollama models (from attributes): {available_models}")
        if EMBEDDING_MODEL not in available_models:
            logger.error(f"CRITICAL: Embedding model '{EMBEDDING_MODEL}' not found. Available: {available_models}")
            logger.error(f"Please pull the model: ollama pull {EMBEDDING_MODEL}"); return
        logger.info(f"Embedding model '{EMBEDDING_MODEL}' is available. Ollama connection successful.")
    except Exception as e: logger.error(f"CRITICAL: Ollama connection error or model check failed: {e}", exc_info=True); return

    all_docs_unembedded: List[Dict[str, Any]] = []
    logger.info("\n--- Processing Local Markdown Repositories ---")
    if FLUTTER_SDK_PATH and os.path.isdir(FLUTTER_SDK_PATH): all_docs_unembedded.extend(process_local_markdown_folder(FLUTTER_SDK_PATH, "flutter_sdk"))
    else: logger.warning(f"Skipping Flutter SDK: path not found at {FLUTTER_SDK_PATH}")
    if DART_SITE_PATH and os.path.isdir(DART_SITE_PATH): all_docs_unembedded.extend(process_local_markdown_folder(DART_SITE_PATH, "dart_site"))
    else: logger.warning(f"Skipping Dart Site source: path not found at {DART_SITE_PATH}")
    if DART_SDK_PATH and os.path.isdir(DART_SDK_PATH): all_docs_unembedded.extend(process_local_markdown_folder(DART_SDK_PATH, "dart_sdk"))
    else: logger.warning(f"Skipping Dart SDK source: path not found at {DART_SDK_PATH}")

    logger.info("\n--- Processing Official Code Samples (Git) ---")
    if FLUTTER_SAMPLES_REPO_URL and FLUTTER_SAMPLES_CLONE_PATH: all_docs_unembedded.extend(process_code_samples_repo(FLUTTER_SAMPLES_REPO_URL, FLUTTER_SAMPLES_CLONE_PATH, "flutter_samples"))
    else: logger.warning("Skipping Flutter Samples: URL or clone path not configured.")

    logger.info("\n--- Scraping Official Documentation Websites (HTML) ---")
    for site_key, start_urls in FLUTTER_DOCS_SITES.items():
        if start_urls: all_docs_unembedded.extend(scrape_website(site_key, start_urls, MAX_SCRAPE_DEPTH, MAX_PAGES_PER_SITE))
        else: logger.info(f"No start URLs for site '{site_key}', skipping scraping.")

    if not all_docs_unembedded: logger.critical("CRITICAL: No documents collected. Exiting."); return
    logger.info(f"\nTOTAL document chunks before embedding: {len(all_docs_unembedded)}")

    logger.info("\n--- Starting Embedding Generation Phase ---")
    texts_to_embed = [doc["text"] for doc in all_docs_unembedded]
    embeddings_results = get_embeddings_batch(texts_to_embed, model_name=EMBEDDING_MODEL)
    data_for_lancedb: List[Dict[str, Any]] = []
    successful_embeds, failed_embeds = 0, 0
    for i, doc_data in enumerate(all_docs_unembedded):
        if i < len(embeddings_results) and embeddings_results[i] is not None:
            doc_copy = doc_data.copy()
            doc_copy["vector"] = embeddings_results[i]
            doc_copy.setdefault("source_type", "unknown"); doc_copy.setdefault("repo_source", "unknown")
            doc_copy.setdefault("source_path", "unknown"); doc_copy.setdefault("chunk_id", f"unknown_chunk_{i}")
            doc_copy.setdefault("document_title", doc_copy.get("source_path", "N/A")) # For HTML docs
            data_for_lancedb.append(doc_copy)
            successful_embeds += 1
        else:
            failed_embeds +=1
            logger.warning(f"Skipping chunk (missing embedding): source='{doc_data.get('repo_source', 'N/A')}/{doc_data.get('source_path', 'N/A')}', chunk_id='{doc_data.get('chunk_id', 'N/A')}'")
    if not data_for_lancedb: logger.critical("CRITICAL: No data with embeddings. Exiting."); return
    logger.info(f"Embeddings generated: {successful_embeds} successful, {failed_embeds} failed.")

    logger.info("\n--- Starting LanceDB Storage Phase ---")
    try:
        db = lancedb.connect(DB_PATH)
        logger.info(f"Connected to LanceDB at {DB_PATH}.")
        if TABLE_NAME in db.table_names():
            logger.info(f"Table '{TABLE_NAME}' exists. Dropping for fresh build.")
            db.drop_table(TABLE_NAME)
            logger.info(f"Dropped existing table: '{TABLE_NAME}'.")
        logger.info(f"Creating new table: '{TABLE_NAME}' with {len(data_for_lancedb)} records...")
        if not data_for_lancedb: logger.error("No data to add to LanceDB."); return
        table = db.create_table(TABLE_NAME, data=data_for_lancedb)
        logger.info(f"Created table '{TABLE_NAME}', added {len(table)} documents.")
        try: logger.info(f"Table schema (inferred): {table.schema}")
        except Exception as e_schema: logger.warning(f"Could not log table schema: {e_schema}")
    except Exception as e: logger.critical(f"CRITICAL: LanceDB error: {e}", exc_info=True); return

    logger.info("\n--- Comprehensive RAG Document Processing and Indexing COMPLETE ---")
    logger.info(f"LanceDB database: {DB_PATH}, Table: {TABLE_NAME}")
    logger.info(f"Total documents indexed: {len(data_for_lancedb)}")

if __name__ == "__main__":
    required_pkgs_import_names = {
        'lancedb': 'lancedb', 'ollama': 'ollama', 'requests': 'requests',
        'beautifulsoup4': 'bs4', 'GitPython': 'git', 'pyarrow': 'pyarrow'
    }
    required_pkgs_pip_names = ['lancedb', 'ollama', 'requests', 'beautifulsoup4', 'GitPython', 'pyarrow']
    missing_for_pip_msg = []
    all_imports_ok = True

    for pip_name, import_name in required_pkgs_import_names.items():
        try:
            __import__(import_name)
        except ImportError:
            # Log the specific pip_name that failed, which is more user-friendly
            logger.error(f"Missing required Python package: '{pip_name}' (which should be importable as '{import_name}'). Please ensure it's installed in your venv.")
            missing_for_pip_msg.append(pip_name) # Store pip_name for overall message
            all_imports_ok = False

    if not all_imports_ok:
        # Join the pip_names of actually missing packages for the pip install command
        install_cmd_pkgs = [name for name in required_pkgs_pip_names if name in missing_for_pip_msg or \
                           (name == 'beautifulsoup4' and 'bs4' in [required_pkgs_import_names[m] for m in missing_for_pip_msg]) or \
                           (name == 'GitPython' and 'git' in [required_pkgs_import_names[m] for m in missing_for_pip_msg]) ]

        logger.error(f"Needed: {', '.join(required_pkgs_pip_names)}") # Still show all originally intended
        if install_cmd_pkgs:
             logger.error(f"Example to install missing: python3 -m pip install {' '.join(install_cmd_pkgs)}")
        else: # Should not happen if all_imports_ok is False, but as a fallback
             logger.error(f"Example: python3 -m pip install {' '.join(required_pkgs_pip_names)}")
        exit(1)
    
    logger.info("All required packages seem to be correctly installed and importable.")
    main()