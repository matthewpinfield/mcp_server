import os
import sys
import logging
import shutil
import hashlib
import re
import json
import time
import uuid
import ast
import signal
import atexit
from typing import Dict, List, Any
from urllib.parse import urlparse

try:
    from git import Repo
    import chromadb
    from chromadb.utils import embedding_functions
    import scrapy
    from scrapy.crawler import CrawlerProcess
    from scrapy.linkextractors import LinkExtractor
    from scrapy.spiders import CrawlSpider, Rule
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"FATAL ERROR: A required library is missing: {e}")
    print("Run 'pip install -r requirements.txt' in your activated virtual environment.")
    sys.exit(1)

LOG_FILE = "ingestion_final.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE, mode='w')]
)

DATABASE_CONFIG = {
    "path": "./rag_db_final",
    "collection_name": "expert_py_flutter_dart_final",
    "embedding_model": "nomic-embed-text:latest"
}
OLLAMA_CONFIG = { "base_url": "http://127.0.0.1:11434" }

GIT_SOURCES = {
    "tier_2_elite_code": {
        "authority": "T2_Elite",
        "git_repos": {
            "flutter": [
                "flutter/flutter", "felangel/bloc", "rrousselGit/riverpod", 
                "FirebaseExtended/flutterfire", "iampawan/Flutter-UI-Kit", "Solido/awesome-flutter"
            ],
            "python": [
                "tiangolo/fastapi", "pandas-dev/pandas", "huggingface/transformers",
                "django/django", "google/pyglove", "Textualize/rich",
                "psf/requests", "pallets/click", "pytest-dev/pytest"
            ]
        },
        "file_extensions": { "python": [".py", ".pyi"], "flutter": [".dart"] },
        "metadata": {"doc_type": "elite_code_example"}
    }
}
CODE_EXCLUSION_PATTERNS = {
    "low_quality_indicators": ["todo", "fixme", "bug", "hack"],
    "content_filters": ["test", "dummy", "example", "poc"]
}

DOC_SOURCES = {
    "tier_1_foundations": {
        "authority": "T1_Official",
        "start_urls": [
            "https://docs.python.org/3/whatsnew/3.12.html",
            "https://docs.python.org/3/whatsnew/3.11.html", 
            "https://docs.python.org/3/whatsnew/3.10.html",
            "https://peps.python.org/pep-0636/",
            "https://peps.python.org/pep-0634/",
            "https://peps.python.org/pep-0585/",
            "https://docs.pytest.org/en/stable/",
            "https://fastapi.tiangolo.com/release-notes/",
            "https://pandas.pydata.org/docs/whatsnew/v2.3.0.html",
            "https://pandas.pydata.org/docs/whatsnew/v2.2.0.html",
            "https://docs.sqlalchemy.org/en/20/changelog/",
            "https://dart.dev/language",
            "https://dart.dev/guides/language/effective-dart",
            "https://docs.flutter.dev/ui/widgets",
            "https://docs.flutter.dev/cookbook",
            "https://api.flutter.dev/flutter/",
            "https://docs.flutter.dev/data-and-backend/state-mgmt",
            "https://pub.dev/packages/provider",
            "https://pub.dev/packages/flutter_bloc",
            "https://pub.dev/packages/riverpod",
            "https://docs.flutter.dev/testing",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/import",
            "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-0.html",
            "https://www.typescriptlang.org/docs/handbook/release-notes/typescript-4-9.html",
            "https://firebase.google.com/docs/firestore",
            "https://firebase.google.com/docs/auth",
            "https://firebase.google.com/docs/storage", 
            "https://firebase.google.com/docs/functions",
            "https://google.github.io/styleguide/",
            "https://google.github.io/styleguide/pyguide.html",
            "https://google.github.io/styleguide/jsguide.html"
        ],
        "allowed_domains": [
            "docs.python.org", "peps.python.org", "docs.pytest.org", "fastapi.tiangolo.com", 
            "pandas.pydata.org", "docs.sqlalchemy.org", "dart.dev", "docs.flutter.dev", 
            "api.flutter.dev", "pub.dev", "developer.mozilla.org", "typescriptlang.org",
            "google.github.io", "github.com", "nodejs.org", "jestjs.io", "firebase.google.com",
            ""
        ],
        "metadata": {"doc_type": "official_docs"}
    },
    "tier_2_practical": {
        "authority": "T2_Practical",
        "start_urls": [
            "https://stackoverflow.com/questions/tagged/python?sort=votes&pageSize=50",
            "https://stackoverflow.com/questions/tagged/fastapi?sort=votes&pageSize=50",
            "https://stackoverflow.com/questions/tagged/flutter?sort=votes&pageSize=50",
            "https://stackoverflow.com/questions/tagged/dart?sort=votes&pageSize=50",
            "https://stackoverflow.com/questions/tagged/flutter-bloc?sort=votes&pageSize=50",
            "https://stackoverflow.com/questions/tagged/javascript?sort=votes&pageSize=50",
            "https://stackoverflow.com/questions/tagged/typescript?sort=votes&pageSize=50"
        ],
        "allowed_domains": ["stackoverflow.com"],
        "metadata": {"doc_type": "qa_solution"}
    },
    "tier_3_patterns": {
        "authority": "T3_Patterns", 
        "start_urls": [
            "https://realpython.com/python-code-quality/",
            "https://web.dev/articles/maintainable-css",
            "https://martinfowler.com/articles/is-quality-worth-cost.html",
            "https://refactoring.guru/design-patterns/factory-method",
            "https://refactoring.guru/design-patterns/observer",
            "https://refactoring.guru/design-patterns/strategy", 
            "https://refactoring.guru/design-patterns/singleton",
            "https://docs.flutter.dev/data-and-backend/state-mgmt/options",
            "https://fastapi.tiangolo.com/tutorial/bigger-applications/",
            "https://developer.mozilla.org/en-US/docs/Learn/Server-side/Express_Nodejs/routes"
        ],
        "allowed_domains": [
            "realpython.com", "web.dev", "martinfowler.com", "refactoring.guru",
            "docs.flutter.dev", "fastapi.tiangolo.com", "developer.mozilla.org"
        ],
        "metadata": {"doc_type": "best_practice"}
    },
    "tier_4_blogs": {
        "authority": "T4_Blog",
        "start_urls": [
            "https://blog.python.org/", 
            "https://blog.nodejs.org/",
            "https://firebase.blog/",
            "https://docs.flutter.dev/release/release-notes",
            "https://docs.python.org/3/whatsnew/",
            "https://nodejs.org/en/blog/release/"
        ],
        "allowed_domains": [
            "blog.python.org", "blog.nodejs.org", "firebase.blog",
            "docs.flutter.dev", "docs.python.org", "nodejs.org"
        ],
        "metadata": {"doc_type": "blog_post"}
    }
}
DOCS_EXCLUSION_PATTERNS = {}

class ChromaDBManager:
    def __init__(self, max_retries=3):
        self.max_retries = max_retries
        self.client = None
        self.collection = None
        self._connect()
    
    def _connect(self):
        """Connect to ChromaDB with retry logic"""
        for attempt in range(self.max_retries):
            try:
                self.client = chromadb.PersistentClient(path=DATABASE_CONFIG["path"])
                self.collection = self.client.get_or_create_collection(
                    name=DATABASE_CONFIG["collection_name"],
                    embedding_function=embedding_functions.OllamaEmbeddingFunction(
                        model_name=DATABASE_CONFIG["embedding_model"], url=OLLAMA_CONFIG["base_url"]
                    )
                )
                logging.info(f"✅ ChromaDB connection established (attempt {attempt + 1}).")
                return
            except Exception as e:
                logging.warning(f"ChromaDB connection attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    logging.critical(f"❌ FATAL: Could not connect to ChromaDB after {self.max_retries} attempts.")
                    sys.exit(1)
                time.sleep(2 ** attempt)  # Exponential backoff
    
    def _ensure_connection(self):
        """Ensure database connection is healthy, reconnect if needed"""
        try:
            if self.collection is None:
                self._connect()
            # Test connection with a simple operation
            self.collection.count()
        except Exception as e:
            logging.warning(f"ChromaDB connection lost: {e}. Reconnecting...")
            self._connect()
    
    def close(self):
        """Close the database connection"""
        if hasattr(self, 'client'):
            del self.client
            logging.info("✅ ChromaDB connection closed.")

    def store_chunks(self, chunks: List[Dict[str, Any]], source_id: str):
        if not chunks: return
        
        # Ensure healthy connection before operations
        self._ensure_connection()
        
        try:
            # Check for existing chunks to avoid semantic duplicates
            existing_ids = set()
            try:
                existing_results = self.collection.get(ids=[c["semantic_id"] for c in chunks])
                existing_ids = set(existing_results["ids"])
            except:
                pass  # Collection might be empty
            
            # Filter out existing chunks
            new_chunks = [c for c in chunks if c["semantic_id"] not in existing_ids]
            
            if new_chunks:
                ids = [c["semantic_id"] for c in new_chunks]
                documents = [c["text"] for c in new_chunks]
                metadatas = [c["metadata"] for c in new_chunks]
                self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
                # Ensure data is persisted
                if hasattr(self.client, 'persist'):
                    self.client.persist()
                logging.info(f"✅ Stored {len(new_chunks)} new chunks from {source_id} (skipped {len(chunks)-len(new_chunks)} duplicates).")
            else:
                logging.info(f"✅ All {len(chunks)} chunks from {source_id} already exist (skipped duplicates).")
        except Exception as e: 
            logging.error(f"Failed to store chunks from {source_id}: {e}")
            # Try to reconnect for next operation
            self._connect()

def validate_code_quality(code_text: str, language: str) -> bool:
    """Validate code quality using AST parsing for Python/Dart"""
    if language == "python":
        try:
            # Try to parse as Python AST
            ast.parse(code_text)
            return True
        except SyntaxError:
            return False
    elif language == "flutter":
        # Basic Dart validation - check for common patterns
        if any(pattern in code_text for pattern in ["class ", "void ", "String ", "int ", "double ", "bool "]):
            # Contains Dart-like syntax
            return True
        return False
    return True  # Allow other languages through

def validate_chunk_size(text: str, max_tokens: int = 7000) -> str:
    """Validate chunk size for embedding model token limits (nomic-embed-text: 8192 tokens)"""
    # Rough approximation: 1 token ≈ 4 characters for English text
    approx_tokens = len(text) // 4
    if approx_tokens > max_tokens:
        # Truncate to safe size, keeping complete lines
        lines = text.splitlines()
        truncated_lines = []
        current_length = 0
        for line in lines:
            if current_length + len(line) // 4 > max_tokens:
                break
            truncated_lines.append(line)
            current_length += len(line) // 4
        logging.warning(f"Truncated chunk from {approx_tokens} to ~{current_length} tokens")
        return "\n".join(truncated_lines)
    return text

def chunk_code(code_text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    chunks, current_chunk = [], []
    lines = code_text.splitlines()
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Start new chunk on top-level class or function (no indentation)
        if (line.strip().startswith('def ') or line.strip().startswith('class ')) and not line.startswith(' ') and not line.startswith('\t'):
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
        
        current_chunk.append(line)
        
        # If this is a class, include all its methods
        if line.strip().startswith('class ') and not line.startswith(' ') and not line.startswith('\t'):
            i += 1
            # Collect everything that belongs to this class (indented content)
            while i < len(lines):
                next_line = lines[i]
                # Stop if we hit another top-level class/function or end of file
                if next_line.strip() and not next_line.startswith(' ') and not next_line.startswith('\t'):
                    break
                current_chunk.append(next_line)
                i += 1
            continue
        
        i += 1
    
    if current_chunk: 
        chunks.append("\n".join(current_chunk))
    
    chunk_results, doc_hash = [], hashlib.md5(code_text.encode()).hexdigest()
    for i, chunk_text in enumerate(chunks):
        if not chunk_text.strip(): continue
        
        # Validate code quality first
        language = metadata.get("language", "unknown")
        if not validate_code_quality(chunk_text, language):
            logging.info(f"FILTERED: Invalid {language} code syntax in chunk {i}")
            continue
            
        # Validate chunk size for embedding model
        chunk_text = validate_chunk_size(chunk_text)
        chunk_hash = f"{doc_hash}-{i}"; chunk_metadata = {**metadata, "chunk_index": i}
        chunk_results.append({"text": chunk_text, "metadata": chunk_metadata, "semantic_id": chunk_hash})
    return chunk_results

def chunk_text(text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]  # Skip empty paragraphs only
    chunk_results, doc_hash = [], hashlib.md5(text.encode()).hexdigest()
    for i, p_text in enumerate(paragraphs):
        # Validate chunk size for embedding model
        p_text = validate_chunk_size(p_text)
        chunk_hash = f"{doc_hash}-{i}"; chunk_metadata = {**metadata, "chunk_index": i}
        chunk_results.append({"text": p_text, "metadata": chunk_metadata, "semantic_id": chunk_hash})
    return chunk_results

class GitIngestor:
    def __init__(self): 
        self.db_manager = ChromaDBManager()
        self.processed_repos = 0
        self.total_repos = 0
        self.processed_files = 0
    
    def run(self):
        logging.info("--- LAUNCHING GIT INGESTOR ---")
        
        # Calculate total repos for progress tracking
        for tier_config in GIT_SOURCES.values():
            for repos in tier_config["git_repos"].values():
                self.total_repos += len(repos)
        
        logging.info(f"📊 Total repositories to process: {self.total_repos}")
        
        try:
            for tier_name, tier_config in GIT_SOURCES.items():
                authority = tier_config["authority"]
                for lang, repos in tier_config["git_repos"].items():
                    for repo_path in repos: 
                        self._process_repo(repo_path, lang, tier_config, authority)
                        self.processed_repos += 1
                        progress = (self.processed_repos / self.total_repos) * 100
                        logging.info(f"📈 Git progress: {self.processed_repos}/{self.total_repos} repos ({progress:.1f}%) - {self.processed_files} files processed")
        finally:
            self.close()
        logging.info("--- GIT INGESTOR FINISHED ---")
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
    def _apply_filters(self, text: str, file_path: str) -> bool:
        text_lower = text.lower()
        for patterns in [CODE_EXCLUSION_PATTERNS.get("low_quality_indicators", []), CODE_EXCLUSION_PATTERNS.get("content_filters", [])]:
            for pattern in patterns:
                if pattern in text_lower: logging.info(f"FILTERED: {file_path} due to pattern '{pattern}'."); return False
        return True
    def _process_repo(self, repo_path: str, lang: str, tier_config: Dict[str, Any], authority: str):
        # Create unique temp directory to avoid naming conflicts
        repo_name = repo_path.replace('/', '_')  # Replace slash with underscore
        unique_id = str(uuid.uuid4())[:8]  # Short unique identifier
        temp_dir = f"./temp_repo_{repo_name}_{unique_id}"
        
        try:
            # Clean up existing temp directory if it exists (should be rare with UUID)
            if os.path.exists(temp_dir):
                logging.info(f"Removing existing temp directory: {temp_dir}")
                shutil.rmtree(temp_dir)
            logging.info(f"Cloning repo: {repo_path} to {temp_dir}"); Repo.clone_from(f"https://github.com/{repo_path}.git", temp_dir, depth=1)
            file_extensions = tier_config["file_extensions"][lang]
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if any(file.endswith(ext) for ext in file_extensions):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: code_text = f.read()
                            if not self._apply_filters(code_text, file_path): continue
                            relative_path = os.path.relpath(file_path, temp_dir)
                            metadata = {**tier_config["metadata"], "language": lang, "source": f"git://{repo_path}/{relative_path}", "authority": authority}
                            chunks = chunk_code(code_text, metadata)
                            self.db_manager.store_chunks(chunks, file_path)
                            self.processed_files += 1
                        except Exception as e: logging.warning(f"Could not process file {file_path}: {e}")
        except Exception as e: logging.error(f"Failed to process repo {repo_path}: {e}")
        finally:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

class DocumentationSpider(CrawlSpider):
    name = 'docs_spider'
    
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.db_manager = ChromaDBManager()
        spider.pages_processed = 0
        spider.pages_stored = 0
        spider.start_time = time.time()
        logging.info("✅ Documentation spider database connection established")
        return spider
    
    def __init__(self, *args, **kwargs):
        super(DocumentationSpider, self).__init__(*args, **kwargs)
        self.rules = []; self.start_urls = []
        for tier_config in DOC_SOURCES.values():
            self.start_urls.extend(tier_config["start_urls"])
            # One rule per domain - stay within each target site
            for domain in tier_config["allowed_domains"]:
                if domain == "github.com":
                    # GitHub: only follow code navigation, not issues/PRs/discussions
                    self.rules.append(Rule(LinkExtractor(
                        allow_domains=[domain], 
                        allow=[r"/tree/", r"/blob/"],
                        deny=[r"/issues/", r"/pull/", r"/releases/", r"/wiki/", r"/discussions/", r"/actions/"]
                    ), callback='parse_item', follow=True))
                else:
                    self.rules.append(Rule(LinkExtractor(allow_domains=[domain]), callback='parse_item', follow=True))
        super(DocumentationSpider, self)._compile_rules()
    
    def close_spider(self, spider):
        """Close database connection when spider finishes"""
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close()
            logging.info("✅ Documentation spider database connection closed")
    def parse_item(self, response):
        self.pages_processed += 1
        
        # Progress tracking every 5 seconds
        current_time = time.time()
        if not hasattr(self, 'last_log_time'):
            self.last_log_time = self.start_time
        if current_time - self.last_log_time >= 5:
            elapsed = time.time() - self.start_time
            rate = self.pages_processed / elapsed if elapsed > 0 else 0
            logging.info(f"📈 Docs progress: {self.pages_processed} pages processed, {self.pages_stored} pages stored ({rate:.2f} pages/sec)")
            self.last_log_time = current_time
        
        source_domain = urlparse(response.url).netloc; current_metadata, current_authority = {}, "T_Unknown"
        for tier_config in DOC_SOURCES.values():
            if any(domain == source_domain for domain in tier_config["allowed_domains"]):
                current_metadata = tier_config["metadata"]; current_authority = tier_config["authority"]; break
        
        # Set language based on domain
        language = "unknown"
        if source_domain in ["docs.python.org", "peps.python.org", "docs.pytest.org", "fastapi.tiangolo.com", "pandas.pydata.org", "docs.sqlalchemy.org", "blog.python.org"]:
            language = "python"
        elif source_domain in ["dart.dev", "docs.flutter.dev", "api.flutter.dev", "pub.dev"]:
            language = "flutter"
        elif source_domain in ["developer.mozilla.org", "typescriptlang.org", "nodejs.org", "jestjs.io", "blog.nodejs.org"]:
            language = "javascript"
        elif source_domain in ["firebase.google.com", "firebase.blog"]:
            language = "firebase"
        elif source_domain in ["google.github.io"]:
            language = "styleguide"
        elif source_domain in ["stackoverflow.com"]:
            # Parse language from Stack Overflow URL tags
            if "/tagged/python" in response.url or "/tagged/fastapi" in response.url:
                language = "python"
            elif "/tagged/flutter" in response.url or "/tagged/dart" in response.url or "/tagged/flutter-bloc" in response.url:
                language = "flutter"
            elif "/tagged/javascript" in response.url or "/tagged/typescript" in response.url:
                language = "javascript"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']): element.decompose()
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            text = main_content.get_text(separator='\n', strip=True); text = re.sub(r'\n{3,}', '\n\n', text).strip()
            
            # Validate code examples in documentation
            code_blocks = re.findall(r'```[\s\S]*?```|`[^`\n]+`', text)
            valid_code_count = 0
            for code_block in code_blocks:
                code_content = re.sub(r'```\w*\n?|```|`', '', code_block).strip()
                if code_content and validate_code_quality(code_content, language):
                    valid_code_count += 1
            
            if text.strip():  # Only store if there's actual content
                metadata = {**current_metadata, "source": response.url, "authority": current_authority, "language": language, "code_examples": len(code_blocks), "valid_code_examples": valid_code_count}
                chunks = chunk_text(text, metadata)
                if chunks:  # Only count if chunks were created
                    self.db_manager.store_chunks(chunks, response.url)
                    self.pages_stored += 1

class GracefulKiller:
    def __init__(self):
        self.kill_now = False
        self.cleanup_functions = []
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        atexit.register(self.cleanup)
    
    def add_cleanup(self, func):
        """Add cleanup function to be called on exit"""
        self.cleanup_functions.append(func)
    
    def exit_gracefully(self, signum, frame):
        logging.info(f"🛑 Received signal {signum}. Initiating graceful shutdown...")
        self.kill_now = True
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Run all cleanup functions"""
        for func in self.cleanup_functions:
            try:
                func()
            except Exception as e:
                logging.error(f"Error during cleanup: {e}")

def cleanup_temp_directories():
    """Clean up any remaining temp directories"""
    for item in os.listdir('.'):
        if item.startswith('temp_repo_'):
            try:
                shutil.rmtree(item)
                logging.info(f"🧹 Cleaned up temp directory: {item}")
            except Exception as e:
                logging.warning(f"Could not clean up {item}: {e}")

def main():
    # Set up graceful shutdown handling
    killer = GracefulKiller()
    killer.add_cleanup(cleanup_temp_directories)
    
    if os.path.exists(DATABASE_CONFIG["path"]):
        logging.info(f"Deleting old database at {DATABASE_CONFIG['path']}...")
        shutil.rmtree(DATABASE_CONFIG["path"])
    
    git_ingestor = GitIngestor()
    killer.add_cleanup(git_ingestor.close)
    
    git_ingestor.run()
    
    if killer.kill_now:
        logging.info("🛑 Interrupted during Git ingestion. Exiting...")
        return
    
    logging.info("--- LAUNCHING DOCUMENTATION CRAWLER ---")
    process = CrawlerProcess(settings={
        "BOT_NAME": "doc_crawler", "SPIDER_MODULES": [__name__], "NEWSPIDER_MODULE": __name__,
        "ROBOTSTXT_OBEY": False, "LOG_LEVEL": "INFO",
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "LOG_STDOUT": True,
        "DEPTH_LIMIT": 4,
        "DOWNLOAD_TIMEOUT": 30,
        "CONCURRENT_REQUESTS": 8,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1,
        "RANDOMIZE_DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1,
        "AUTOTHROTTLE_MAX_DELAY": 60,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "AUTOTHROTTLE_DEBUG": False,
        "RETRY_TIMES": 2,
        "DUPEFILTER_DEBUG": True,
        "DUPEFILTER_CLASS": "scrapy.dupefilters.RFPDupeFilter",
        "CLOSESPIDER_PAGECOUNT": 500,
        "EXTENSIONS": {
            'scrapy.extensions.logstats.LogStats': None,  # Disable misleading logstats
        },
    })
    process.crawl(DocumentationSpider)
    process.start()
    logging.info("--- DOCUMENTATION CRAWLER FINISHED ---")

if __name__ == "__main__":
    main()
