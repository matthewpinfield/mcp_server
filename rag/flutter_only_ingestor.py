import os
import sys
import logging
import shutil
import hashlib
import re
import json
import time
import uuid
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

LOG_FILE = "flutter_ingestion.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE, mode='w')]
)

DATABASE_CONFIG = {
    "path": "./flutter_only_db",
    "collection_name": "flutter_dart_knowledge",
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
            ]
        },
        "file_extensions": { "flutter": [".dart"] },
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
            "https://firebase.google.com/docs/firestore",
            "https://firebase.google.com/docs/auth",
            "https://firebase.google.com/docs/storage", 
            "https://firebase.google.com/docs/functions",
            "https://firebase.google.com/docs/rules"
        ],
        "allowed_domains": [
            "dart.dev", "docs.flutter.dev", "api.flutter.dev", "pub.dev", "firebase.google.com"
        ],
        "metadata": {"doc_type": "official_docs"}
    },
    "tier_2_practical": {
        "authority": "T2_Practical",
        "start_urls": [
            "https://stackoverflow.com/questions/tagged/flutter?sort=votes&pageSize=50",
            "https://stackoverflow.com/questions/tagged/dart?sort=votes&pageSize=50",
            "https://stackoverflow.com/questions/tagged/flutter-bloc?sort=votes&pageSize=50"
        ],
        "allowed_domains": ["stackoverflow.com"],
        "metadata": {"doc_type": "qa_solution"}
    },
    "tier_3_patterns": {
        "authority": "T3_Patterns", 
        "start_urls": [
            "https://docs.flutter.dev/data-and-backend/state-mgmt/options"
        ],
        "allowed_domains": ["docs.flutter.dev"],
        "metadata": {"doc_type": "best_practice"}
    },
    "tier_4_blogs": {
        "authority": "T4_Blog",
        "start_urls": [
            "https://firebase.blog/",
            "https://docs.flutter.dev/release/release-notes"
        ],
        "allowed_domains": [
            "firebase.blog", "docs.flutter.dev"
        ],
        "metadata": {"doc_type": "blog_post"}
    }
}
DOCS_EXCLUSION_PATTERNS = {}

class ChromaDBManager:
    def __init__(self):
        try:
            self.client = chromadb.PersistentClient(path=DATABASE_CONFIG["path"])
            self.collection = self.client.get_or_create_collection(
                name=DATABASE_CONFIG["collection_name"],
                embedding_function=embedding_functions.OllamaEmbeddingFunction(
                    model_name=DATABASE_CONFIG["embedding_model"], url=OLLAMA_CONFIG["base_url"]
                )
            )
            logging.info(f"✅ ChromaDB connection established.")
        except Exception as e:
            logging.critical(f"❌ FATAL: Could not connect to ChromaDB. {e}")
            sys.exit(1)
    
    def close(self):
        """Close the database connection"""
        if hasattr(self, 'client'):
            del self.client
            logging.info("✅ ChromaDB connection closed.")

    def store_chunks(self, chunks: List[Dict[str, Any]], source_id: str):
        if not chunks: return
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
                logging.info(f"✅ Stored {len(new_chunks)} new chunks from {source_id} (skipped {len(chunks)-len(new_chunks)} duplicates).")
            else:
                logging.info(f"✅ All {len(chunks)} chunks from {source_id} already exist (skipped duplicates).")
        except Exception as e: logging.error(f"Failed to store chunks from {source_id}: {e}")

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
        chunk_hash = f"{doc_hash}-{i}"; chunk_metadata = {**metadata, "chunk_index": i}
        chunk_results.append({"text": chunk_text, "metadata": chunk_metadata, "semantic_id": chunk_hash})
    return chunk_results

def chunk_text(text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]  # Skip empty paragraphs only
    chunk_results, doc_hash = [], hashlib.md5(text.encode()).hexdigest()
    for i, p_text in enumerate(paragraphs):
        chunk_hash = f"{doc_hash}-{i}"; chunk_metadata = {**metadata, "chunk_index": i}
        chunk_results.append({"text": p_text, "metadata": chunk_metadata, "semantic_id": chunk_hash})
    return chunk_results

class GitIngestor:
    def __init__(self): 
        self.db_manager = ChromaDBManager()
    
    def run(self):
        logging.info("--- LAUNCHING FLUTTER/DART GIT INGESTOR ---")
        try:
            for tier_name, tier_config in GIT_SOURCES.items():
                authority = tier_config["authority"]
                for lang, repos in tier_config["git_repos"].items():
                    for repo_path in repos: self._process_repo(repo_path, lang, tier_config, authority)
        finally:
            self.close()
        logging.info("--- FLUTTER/DART GIT INGESTOR FINISHED ---")
    
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
        temp_dir = f"./temp_repo_{repo_path.split('/')[-1]}"
        try:
            # Clean up existing temp directory if it exists
            if os.path.exists(temp_dir):
                logging.info(f"Removing existing temp directory: {temp_dir}")
                shutil.rmtree(temp_dir)
            logging.info(f"Cloning repo: {repo_path}"); Repo.clone_from(f"https://github.com/{repo_path}.git", temp_dir, depth=1)
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
        source_domain = urlparse(response.url).netloc; current_metadata, current_authority = {}, "T_Unknown"
        for tier_config in DOC_SOURCES.values():
            if any(domain == source_domain for domain in tier_config["allowed_domains"]):
                current_metadata = tier_config["metadata"]; current_authority = tier_config["authority"]; break
        
        # Set language based on domain
        language = "flutter"  # Flutter-only script, all docs are Flutter-related
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']): element.decompose()
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            text = main_content.get_text(separator='\n', strip=True); text = re.sub(r'\n{3,}', '\n\n', text).strip()
            metadata = {**current_metadata, "source": response.url, "authority": current_authority, "language": language}
            chunks = chunk_text(text, metadata)
            self.db_manager.store_chunks(chunks, response.url)

def main():
    if os.path.exists(DATABASE_CONFIG["path"]):
        logging.info(f"Deleting old database at {DATABASE_CONFIG['path']}...")
        shutil.rmtree(DATABASE_CONFIG["path"])
    git_ingestor = GitIngestor()
    git_ingestor.run()
    logging.info("--- LAUNCHING FLUTTER/DART DOCUMENTATION CRAWLER ---")
    process = CrawlerProcess(settings={
        "BOT_NAME": "flutter_doc_crawler", "SPIDER_MODULES": [__name__], "NEWSPIDER_MODULE": __name__,
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
        "RETRY_TIMES": 2,
        "DUPEFILTER_DEBUG": True,
        "CLOSESPIDER_PAGECOUNT": 200,
        "EXTENSIONS": {
            'scrapy.extensions.logstats.LogStats': None,  # Disable misleading logstats
        },
    })
    process.crawl(DocumentationSpider)
    process.start()
    logging.info("--- FLUTTER/DART DOCUMENTATION CRAWLER FINISHED ---")

if __name__ == "__main__":
    main()