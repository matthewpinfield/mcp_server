### **Definitive Blueprint: The MCP Knowledge & Memory Architecture (v2.1)**

**1. Executive Summary**

This document outlines the definitive architecture, curriculum, and operational philosophy for the MCP system's two core cognitive components: the **3-Tier Memory System** and the **Retrieval-Augmented Generation (RAG) System**. Its purpose is to serve as a single, authoritative source of truth for their design, function, and interaction.

*   The **3-Tier Memory System** serves as the AI's "autobiographical brain," managing its identity, learned preferences, and the complete history of its conversations.
*   The **RAG System** serves as the AI's "expert technical library," providing a perpetually refreshed, curated knowledge base across key technologies (**Dart/Flutter, Python, JavaScript/TypeScript, and Firebase**) to elevate its capabilities from a simple programmer to an expert software architect.

The entire system operates on a non-negotiable **"Context-First"** principle. This means that before the primary LLM is engaged, the Orchestrator first queries the RAG and Memory systems to retrieve factual, up-to-date context. This "open book" approach grounds every response in fact, preempts hallucination, and is the core operational tenet of the MCP.

**2. System Architecture: The Brain and the Bookshelf**

The system is composed of two distinct, specialized components. They are not tiers of each other but separate systems with unique responsibilities. This separation resolves all confusion: "memory" refers to the 3-tier system; "RAG" refers to the expert knowledge library.

#### **2.1. The 3-Tier Memory System (The AI's Brain)**

This system manages the AI's "autobiographical" memory—its past experiences and its sense of self. It works in three layers, organized by access speed and purpose.

| Tier | Name | Purpose | Technology | Location |
| :--- | :--- | :--- | :--- | :--- |
| **1**  | **Working Memory** | Manages the context of the *current conversation*. What are we talking about *right now*? | **Redis**  | Local M2
| **2**  | **Permanent Profile**| Defines the AI's identity: *who I am, my rules, and my preferences*. | **MongoDB**  | Local SSD |
| **3**  | **Long-Term Archive**| Stores *all past conversations* for semantic recall. What did we talk about *last month*? | **ChromaDB** | **Starts on Local SSD then moves to NAS**

n.b the Flow is Tier 1 moves to Tier 3, Tier does does not move

#### **2.2. The RAG System (The AI's Bookshelf)**

This is the AI's professional library of textbooks, code examples, and best practices. It is a separate, specialized tool, not a tier of memory.

| Purpose | Technology | Primary Location |
| :--- | :--- | :--- |
| To provide expert, up-to-date code knowledge & examples. | **ChromaDB** | **Local SSD** |

The RAG database is kept on the local SSD for high-performance access during active development sessions. It can be archived or synchronized with a larger instance on the NAS but is treated as a high-speed local resource by the MCP to ensure the AI can instantly access its reference materials.

**3. The RAG Knowledge Curriculum: A Master Developer's Library Stored on M2**

The heart of the RAG is its content, which is structured in tiers to elevate the agent beyond a simple coder. This curriculum applies across all target domains.

*   **Tier 1: The Foundations (The "Source of Truth")**
    *   **Content:** The non-negotiable, foundational knowledge. This includes the latest official language documentation (Python, Dart, TS), official language style guides (PEP 8, Effective Dart), and core framework/library documentation (Flutter, FastAPI, Firebase, Node.js).
    *   **Authority Tag:** `T1_Official`

*   **Tier 2: Principles & Patterns (The "Philosophy of Engineering")**
    *   **Content:** Material that teaches what elevates code from functional to professional. This includes pragmatic summaries of SOLID, DRY, and KISS; high-quality articles on software design patterns (Factory, Singleton, Observer); and architectural blueprints (REST, MVC vs. MVVM, state management strategies).
    *   **Authority Tag:** `T2_Curated`

*   **Tier 3: High-Quality Examples (The "Case Studies & Practical Experience")**
    *   **Content:** This tier teaches the *art* of coding. It includes a personal, curated library of your "Golden Snippets" and select, high-quality modules from well-regarded GitHub repositories (e.g., a canonical `database_connector.py` or `networking_service.dart`).
    *   **Authority Tag:** `T3_Community`

*   **Tier 4: Modern & Evolving Knowledge (The "Latest Bulletins")**
    *   **Content:** This tier directly combats the knowledge cut-off problem. It includes official blog posts from sources like the Flutter or Python blogs and key release notes from major framework updates.

**4. Technical Implementation & Operations**

#### **4.1. RAG Database Schema & Querying**
The power of the RAG lies in its metadata. Every chunk ingested into Chroma **must** be tagged with the following fields to enable "Strict Metadata Filtering":

*   `language`: (e.g., "python", "dart", "typescript")
*   `platform`: (e.g., "flutter", "firebase", "web")
*   `library`: (e.g., "pandas", "fastapi", "react")
*   `doc_type`: (e.g., "api_reference", "tutorial", "style_guide", "golden_snippet")
*   `authority`: A crucial tag for conflict resolution, based on the source tier: `"T1_Official"`, `"T2_Curated"`, `"T3_Community"`

The Orchestrator **must** use these `where` clauses in ChromaDB queries for surgical precision:
`collection.query(query_texts=["..."], where={"language": "python", "library": "pandas"})`

#### **4.2. The Advanced Ingestion Pipeline**
This is the process for getting high-quality, perfectly structured data into ChromaDB.

1.  **Ethical Scraping:** An automated script scrapes "Gold Standard" sources, respecting `robots.txt`, using rate limits (1-2s delay), identifying with a custom `User-Agent`, and caching raw pages.
2.  **LLM-Powered Semantic Chunking:** This is a key innovation. A dedicated "Tagger" LLM reads a full document and inserts a special token, `##CHUNK_BOUNDARY##`, between each complete function, class, or distinct conceptual section. The script then splits the document on this token, creating perfectly formed, semantically complete chunks.
3.  **Automated Metadata Tagging:** The script loops through each chunk and applies the full set of metadata tags defined in the schema.
4.  **Embedding and Ingestion:** For each chunk, the script generates its vector embedding and saves the original text, its vector, and all metadata into ChromaDB.

The pipeline will be programmed to **actively exclude and discard** outdated documentation, low-quality community content, overly "clever" code, and large, monolithic code dumps.

#### **4.3. LLM & Agent Integration Strategy**
*   **Role of the Main LLM (20B+): The "Synthesis Engine"**: This large model acts as a superior reasoning engine, processing the RAG's output to synthesize coherent answers from multiple retrieved documents.
*   **Role of the Dedicated "Tagger" LLM**: A smaller, specialized model will handle all background AI-based tagging and chunking, offloading routine work to keep the main LLM responsive.
*   **Tool Integration**: The RAG, Memory System, and Code Sandbox will be defined as formal `Tools` within the agent framework, allowing the LLM to reason about which tool to use for a given task.

#### **4.4. The "Master Prompt" Template**
The Orchestrator will dynamically assemble prompts using this explicit structure to guide the LLM's reasoning:
```
[PERSONA]
You are a senior software engineer with 10+ years of experience. Your code is clean, maintainable, and robust. You ground your answers in the provided reference material.

[CORE DIRECTIVES - THE LAW]
You must adhere to the following coding standards at all times:
(Inject all permanent rules retrieved from the Tier 2 MongoDB Profile)

[USER CORRECTIONS]
You previously made a mistake on this topic. Adhere to the following correction:
(Inject relevant correction from the `correction_logs` if a match is found)

[REFERENCE MATERIAL & EXAMPLES - THE LIBRARY]
Based on the user's query, here is the most relevant, authoritative information from the knowledge base. Use this to formulate your answer.
--- REFERENCE ---
(Inject the highest-authority text chunks & "golden snippets" retrieved from the Chroma RAG here)
---

[CONVERSATIONAL HISTORY]
(Inject the short-term history from the Tier 1 Redis Working Memory here)
```

#### **4.5. System Operations & Optimization**
*   **Strict Metadata Filtering:** The Orchestrator **must** use `where` clauses in all Chroma queries.
*   **Two-Stage Retrieval (Re-ranking):** For complex questions, the Orchestrator can perform a broad initial search, then use the LLM to re-rank the results for relevance.
*   **Handling Contradictory Information:** If retrieved documents conflict, the Orchestrator's logic will instruct the LLM to prioritize the source with the higher **`authority`** tag (T1 > T2 > T3).
*   **Automated Knowledge Refresh:** A weekly CRON job will re-scrape Tier 4 sources (blogs, release notes) to ensure the agent's knowledge never goes stale.
*   **Caching Layer (Redis):** The Redis instance will cache results for common RAG queries, providing instant answers for frequent questions.
*   **User Correction Loop:** A `/correct` command will log flawed responses and user corrections, giving this feedback top priority in future context retrieval on that topic.

**5. Desired Outcome: Simulating Expert Judgment**

A senior developer's code isn't just "correct"—it exhibits judgment. The entire purpose of this system is to provide the raw materials for the LLM to develop a simulated form of that judgment. The agent's code will be indistinguishable from a real coder's when it consistently demonstrates these four qualities, all derived directly from the RAG's curriculum:

1.  **It's Idiomatic:** It uses the language in the way a native speaker would. This comes from the **Tier 1 Foundations** and **Tier 3 Golden Snippets**.
2.  **It's Maintainable:** It's easy for a human to read and modify. This comes from the **Tier 1 Style Guides** and **Tier 2 Principles**.
3.  **It's Context-Aware:** It chooses the right tool for the job. This comes from the **Tier 2 Design Patterns** and **Architectural Blueprints**.
4.  **It's Robust:** It anticipates problems with proper error handling and logging. This comes from seeing how **Tier 3 High-Quality Open-Source Code** handles real-world complexity.