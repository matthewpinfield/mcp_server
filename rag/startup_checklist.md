# My RAG System Startup Checklist

This checklist outlines the steps to get the custom RAG (Retrieval Augmented Generation) system working with Ollama, the Python API server, and VS Code with the "Continue" extension.

## Phase 1: Start Core Services (Ollama)

1.  **Start the Ollama Server:**
    *   This depends on your usual method for running Ollama.
    *   **Option A: Ollama Desktop Application**
        *   Launch the Ollama Desktop application. It typically runs the server in the background.
    *   **Option B: Manual Terminal Command**
        *   Open a **new terminal window** (let's call this "Terminal 1: Ollama Server").
        *   Run the command:
            ```bash
            ollama serve
            ```
        *   This terminal window will display Ollama server logs and **must remain open** while using the RAG system.

2.  **Verify Ollama Server (Optional but Recommended):**
    *   Open another **new terminal window** (or a new tab).
    *   Run:
        ```bash
        ollama list
        ```
    *   **Expected Output:** You should see at least `gemma3:4b-it-qat` and `nomic-embed-text:latest` listed. If you receive a connection error, the Ollama server is not running correctly. Address this before proceeding.

## Phase 2: Start Your Custom RAG API Server (`server.py`)

1.  **Navigate to Project Directory & Activate Virtual Environment:**
    *   Open a **new terminal window** (let's call this "Terminal 2: RAG Server").
    *   Change to your project directory:
        ```bash
        cd /mnt/caseSSD/continue_custom_rag
        ```
    *   Activate the Python virtual environment:
        ```bash
        source venv/bin/activate
        ```
    *   Your terminal prompt should now be prefixed with `(venv)`.

2.  **Run `server.py`:**
    *   While in the `~/continue_custom_rag` directory and with the `(venv)` active, start the FastAPI server:
        ```bash
        python server.py
        ```
    *   **Expected Output:**
        *   The terminal will show startup logs from the script (using the `logging` module).
        *   Look for lines indicating successful connection to LanceDB (e.g., `Table has 2399 rows.`) and confirmation that Ollama models are available.
        *   The final lines should be similar to:
            ```
            INFO:     Application startup complete.
            INFO:     Uvicorn running on http://localhost:8008 (Press CTRL+C to quit)
            ```
    *   This terminal window ("Terminal 2: RAG Server") **must also remain open** while using the RAG system.

## Phase 3: Use the RAG System in VS Code

1.  **Launch VS Code:**
    *   Open your VS Code application.
    *   Open your target Flutter/Dart project (e.g., `/home/matthewpinfield/CodeProjects/GutFlutter`).

2.  **"Continue" Extension:**
    *   Ensure the "Continue" extension is enabled.
    *   The `~/.continue/config.yaml` file should be correctly configured with the `fldartdocs` HTTP context provider pointing to `http://localhost:8008/custom_rag_stuff`. (This is usually a one-time setup).

3.  **Start Interacting:**
    *   Open the "Continue" chat panel.
    *   Use your custom RAG provider by typing `@fldartdocs` followed by your query (e.g., `@fldartdocs how do I use ListView.builder?`).
        *   *(Remember: Based on our findings, the UI might display `@fldartdocs` in suggestions, and selecting it should correctly trigger the provider. If you previously found `@@fldartdocs` was what the UI inserted and worked, use that specific trigger.)*
    *   **Observe:**
        *   Responses should appear in the "Continue" chat panel.
        *   The "Terminal 2: RAG Server" window (running `server.py`) should show log activity for each query (e.g., "Request received," "Raw request body," "Extracted query," "Retrieved X documents," etc.).

---

**Summary of Running Processes for Full RAG Functionality:**

1.  ✅ **Ollama Server:** Running (either via desktop app or `ollama serve` in a terminal).
2.  ✅ **Custom RAG API Server (`server.py`):** Running (`python server.py` in a terminal with `venv` active).
3.  ✅ **VS Code:** Running with your project and the "Continue" extension.

---
