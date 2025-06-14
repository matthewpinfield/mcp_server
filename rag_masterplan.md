 We are building the world's best coding RAG, with the following key features:***

### **Blueprint for the World's Best Coding RAG (v1)**

**1. Executive Summary**

This document outlines the definitive architecture, curriculum, operational philosophy, and implementation plan for a state-of-the-art Retrieval-Augmented Generation (RAG) system. Its purpose is to serve as the "expert library" and "source of truth" for a local LLM agent, elevating it from a simple programmer to an expert software architect. This system is designed to overcome knowledge cut-offs, instill deep architectural principles, and provide a curated, perpetually refreshed knowledge base across key technologies, including **Dart/Flutter, Python, JavaScript/TypeScript, and Firebase**. The core operational principle is a **"Context-First"** workflow, ensuring all AI-generated content is grounded in fact and aligned with best practices. The architecture is designed for precision, ethical data sourcing, and high-performance use within a local server environment.

**2. Core Operational Philosophy: The "Context-First" Principle**

The entire system will operate on a "Context-First" RAG workflow. This is a non-negotiable principle to ensure accuracy and efficiency.

*   **The Workflow:**
    1.  The Orchestrator receives a user prompt.
    2.  **Before** engaging the primary LLM, the Orchestrator queries the relevant tools (RAG, Memory System) to retrieve factual, up-to-date context.
    3.  This retrieved context (the "open book") is assembled into the "Master Prompt."
    4.  The primary LLM receives the user's question and the factual context simultaneously.
    5.  The LLM generates a single, grounded answer based on the provided truth.

*   **Why This Is Essential:** This approach preempts LLM "hallucination" by grounding every response in facts from our curated knowledge base. It is also more efficient, requiring a single LLM generation step instead of a flawed generation followed by a complex correction.

**3. The Knowledge Curriculum: A Master Developer's Library**

This is the heart of the RAG, defining the content that elevates the agent beyond a simple coder. The curriculum is structured in tiers, from foundational facts to the philosophy of engineering, and applies across all target domains.

*   **Tier 1: The Foundations (The "Source of Truth")**
    *   **Content:** This is the non-negotiable, foundational knowledge that forms the bedrock of correctness.
        *   **Official Language Documentation:** The latest, complete documentation for Python, Dart, and TypeScript, covering the standard library and core syntax.
        *   **Official Language Style Guides:** The full text of PEP 8 for Python and the Effective Dart guides.
        *   **Core Framework/Library Documentation:** Official, up-to-date documentation for essential tools like Flutter, FastAPI, Pandas, Firebase, Node.js, etc.

*   **Tier 2: The Principles & Patterns (The "Philosophy of Engineering")**
    *   **Content:** This material teaches what elevates code from merely functional to professional.
        *   **Pragmatic "Clean Code" Summaries:** Scraped articles and summaries of timeless principles like SOLID, DRY, and KISS, focusing on clear code examples.
        *   **Software Design Patterns:** High-quality articles (with code examples) explaining the implementation and use cases for common patterns (e.g., Factory, Singleton, Observer, Strategy).
        *   **Architectural Blueprints:** Articles and tutorials explaining high-level concepts like RESTful API design, MVC vs. MVVM, state management strategies, and error handling philosophies.

*   **Tier 3: High-Quality Examples (The "Case Studies & Practical Experience")**
    *   **Content:** This is the most important section for teaching the *art* of coding.
        *   **Your "Golden Snippets" Library:** A personal, curated collection of excellent code snippets. Each snippet should be a solution to a specific problem, tagged to teach the agent *your* preferred style.
        *   **Select, High-Quality Open-Source Code:** Specific files or small modules from well-regarded GitHub repositories. Scrape canonical examples like a `database_connector.py` or a `networking_service.dart`, not entire projects.

*   **Tier 4: Modern & Evolving Knowledge (The "Latest Bulletins")**
    *   **Content:** This tier directly combats the knowledge cut-off problem.
        *   **Official Blog Posts:** Posts from sources like the official Flutter or Python blogs to learn about new features and upcoming changes.
        *   **Key Release Notes:** The "What's New" sections from major framework and language updates.

**4. Technical Architecture & Implementation**

This section details the database setup, schemas, and the optimal input methods for building and maintaining the RAG.

**4.1. System Database Architecture**
The system uses three distinct databases, each with a specific role:

| Database | Technology      | Primary Purpose                                                                                      | Data Stored                                                                                                                              |
| :------- | :-------------- | :--------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------- |
| **RAG**  | **ChromaDB**    | The core "expert library." Stores knowledge chunks and their vector embeddings for semantic search.    | Text chunks, vector embeddings, and rich metadata.                                                                                       |
| **Cache** | **Redis**       | A high-speed caching layer to reduce redundant queries and provide instant answers.                  | Key-value pairs where the key is a hash of a user query and the value is the previously retrieved RAG context or the final answer.        |
| **Profile** | **MongoDB** (or similar) | Stores persistent user-specific configurations, preferences, and feedback loops. | User-specific coding standards (`Core Directives`), correction logs from the `/correct` command, and long-term conversational memory. |

**4.2. RAG Database (ChromaDB) Schema**
The power of the RAG lies in its metadata. Every chunk ingested into Chroma **must** be tagged with the following fields to enable "Strict Metadata Filtering":

*   `language`: (e.g., "python", "dart", "typescript")
*   `platform`: (e.g., "flutter", "firebase", "web")
*   `library`: (e.g., "pandas", "fastapi", "react")
*   `service`: (e.g., "firestore", "auth") - *For cloud platforms.*
*   `doc_type`: (e.g., "api_reference", "tutorial", "style_guide", "golden_snippet")
*   `authority`: A crucial tag for conflict resolution, based on the source tier: `"T1_Official"`, `"T2_Curated"`, `"T3_Community"`

An optimized query from the Orchestrator will be surgical:
`collection.query(query_texts=["..."], where={"language": "python", "library": "pandas"})`

**4.3. The Advanced Ingestion Pipeline (Optimal Input Method)**
This is the step-by-step process for getting high-quality, perfectly structured data into ChromaDB.

1.  **Ethical Scraping:** The process begins with an automated script that scrapes the "Gold Standard" sources. This script **must** be configured to:
    *   **Respect `robots.txt`**: Check and obey the rules for each domain.
    *   **Rate Limit**: Wait 1-2 seconds between requests to a single domain.
    *   **Identify**: Use a custom `User-Agent` string (e.g., `Personal-AI-Knowledge-Bot/1.0`).
    *   **Cache**: Save raw scraped pages locally to avoid re-scraping.

2.  **LLM-Powered Semantic Chunking:** This is the key innovation that replaces naive chunking.
    *   The script takes a full document (e.g., a documentation page or code file) and passes it to a dedicated "Tagger" LLM.
    *   The LLM is prompted: `"You are a code analysis tool. Read this document and identify the logical boundaries. Insert a special token '##CHUNK_BOUNDARY##' between each complete function, class, or distinct conceptual section."`
    *   The script then splits the document on the `##CHUNK_BOUNDARY##` token, creating a list of perfectly formed, semantically complete chunks.

3.  **Automated Metadata Tagging:** The script loops through each chunk and applies the full set of metadata tags defined in the schema above, deriving them from the source URL and content.

4.  **Embedding and Ingestion:** For each fully-tagged, semantically-whole chunk, the script generates its vector embedding and saves the original text, its vector, and all its metadata into the ChromaDB collection.

**4.4. Ingestion Exclusion Policy**
The quality of the RAG is defined as much by what you exclude. The ingestion pipeline will be programmed to actively reject and discard:
*   **Outdated Documentation:** Anything related to deprecated versions (e.g., Python 2, legacy Flutter APIs).
*   **Low-Quality Community Content:** Forum answers with no upvotes or accepted markers.
*   **Obscure or "Clever" Code:** Code that prioritizes cleverness over clarity and maintainability.
*   **Large, Monolithic Code Dumps:** Ingesting entire multi-thousand-line files or repositories at once.
*   **Pure Opinion Pieces:** Articles debating philosophies without providing concrete, actionable code examples.

**5. LLM & Agent Integration Strategy**

*   **Role of the Main LLM (20B+): The "Synthesis Engine"**: This large model is a superior reasoning and synthesis engine for processing the RAG's output. It can understand more nuanced queries and synthesize coherent answers from a larger number of retrieved documents.
*   **Role of the Dedicated "Tagger" LLM**: A smaller, specialized model handles all background AI-based tagging and chunking, offloading routine work to keep the main LLM responsive.
*   **Tool Integration**: The RAG, Memory System, and Code Sandbox will be defined as formal `Tools` within the agent framework. The LLM will be taught to reason about which tool to use.

**6. The "Master Prompt" Template**

The Orchestrator will dynamically assemble prompts using this explicit structure to guide the LLM's reasoning:
```
[PERSONA]
You are a senior software engineer with 10+ years of experience. Your code is clean, maintainable, and robust. You ground your answers in the provided reference material.

[CORE DIRECTIVES - THE LAW]
You must adhere to the following coding standards at all times:
- (List of all rules retrieved from the MongoDB profile)

[USER CORRECTIONS]
You previously made a mistake on this topic. Adhere to the following correction:
- (Inject relevant correction from the `correction_logs` if found)

[REFERENCE MATERIAL & EXAMPLES - THE LIBRARY]
Based on the user's query, here is the most relevant, authoritative information from the knowledge base. Use this to formulate your answer.
--- REFERENCE ---
(Inject the highest-authority text chunks & "golden snippets" retrieved from the Chroma RAG here)
---

[CONVERSATIONAL HISTORY]
(Inject the short-term history from Redis here)
```

**7. System Operations & Optimization**

*   **Strict Metadata Filtering:** The Orchestrator **must** use `where` clauses in all Chroma queries to surgically target relevant data.
*   **Two-Stage Retrieval (Re-ranking):** For complex questions, the Orchestrator can perform a broad initial search, then use the LLM to re-rank the results for relevance.
*   **Handling Contradictory Information:** If retrieved documents conflict, the Orchestrator's logic will instruct the LLM to prioritize the source with the higher **`authority`** tag (T1 > T2 > T3).
*   **Automated Knowledge Refresh:** A weekly CRON job will re-scrape Tier 4 sources (blogs, release notes) to ensure the agent's knowledge never goes stale.
*   **Caching Layer (Redis):** The Redis instance will cache results for common RAG queries, providing instant answers for frequent questions.
*   **User Correction Loop:** A `/correct` command will log flawed responses and user corrections, giving this feedback top priority in future context retrieval on that topic.

**8. Desired Outcome: Simulating Expert Judgment**

A senior developer's code isn't just "correct"—it exhibits judgment. The entire purpose of this system is to provide the raw materials for the LLM to develop a simulated form of that judgment. The agent's code will be indistinguishable from a real coder's when it consistently demonstrates these four qualities, all derived directly from the RAG's curriculum:

1.  **It's Idiomatic:** It uses the language in the way a native speaker would. This comes from the **Tier 1 Foundations** and **Tier 3 Golden Snippets**.
2.  **It's Maintainable:** It's easy for a human to read and modify. This comes from the **Tier 1 Style Guides** and **Tier 2 Principles**.
3.  **It's Context-Aware:** It chooses the right tool for the job. This comes from the **Tier 2 Design Patterns** and **Architectural Blueprints**.
4.  **It's Robust:** It anticipates problems with proper error handling and logging. This comes from seeing how **Tier 3 High-Quality Open-Source Code** handles real-world complexity.

Recommendation: The Best of Both Worlds
Given that this chunking process is a background task that is not directly in the user-facing request/response loop, you have the flexibility to prioritize quality over speed.

Use the 8B Model for Prototyping and General Use: For your day-to-day development and for less critical documents, using the faster 8B model is a perfectly valid and efficient choice.
Use the 14B Model for "Gold Standard" Sources: When you are ingesting your most important, Tier-1 documents (like the official PEP 8 guide or the Effective Dart documentation), it is worth taking the performance hit to use the 14B model. You can run this as a slower, overnight batch process. The higher-quality chunks it produces for your most critical knowledge will pay dividends for the lifetime of your RAG.
In summary, the 14B model offers tangible benefits in logical reasoning and semantic understanding, leading to a higher-quality RAG. The fact that your 8B model is faster makes it the right tool for rapid, day-to-day ingestion, while the 14B model is the right tool for the slower, more deliberate ingestion of your most valuable knowledge sources.