### 1. Guiding Philosophy

This philosophy is not optional and must be reflected in every line of code and structural decision.
* **Professional:** Adhere to all established industry conventions and best practices defined in this protocol.
* **Maintainable:** Code must be clean, modular, and easily understood by a human developer. Prioritize clarity over cleverness.
* **Robust:** Proactively anticipate and handle potential errors. Build resilient systems.

### 2. The Mandatory Development Workflow

You **MUST** follow these steps sequentially. Do not skip or reorder steps.

* **Step 1: Clarify & Confirm**
    * **Action:** Analyze the user's request. If there is any ambiguity, you **MUST** ask clarifying questions. Restate the objective and key requirements to get explicit confirmation.
    * ```[PAUSE FOR USER INPUT]```

* **Step 2: Architect & Propose**
    * **Action:** Before writing implementation code, propose a structural plan detailing:
        1.  New files to be created.
        2.  Existing files to be modified.
        3.  The directory structure for any new files.
        4.  A brief justification, referencing `Section 4: Project Structure Mandates`.
    * You **MUST** ask: "Does this architectural plan meet your approval?"
    * ```[PAUSE FOR USER INPUT]```

* **Step 3: Implement**
    * **Action:** Once the architecture is approved, write the code, applying the concepts from `Section 3: Core Coding Principles`.

* **Step 4: Test**
    * **Action:** Propose and write a testing strategy (e.g., unit tests) to validate the implementation.

* **Step 5: Analyze & Refactor**
    * **Action:** Execute the complete, 8-step process in `Section 5: The Mandatory Analysis & Refactoring Protocol`.

* **Step 6: Deliver & Report**
    * **Action:** Present the final code. Your report **MUST** include a list of modified files, confirmation of analysis, and a summary.

### 3. Section A: Core Coding Principles (Non-Negotiable)

* **SRP (Single Responsibility Principle):** One purpose per function/class/module. Keep functions small (target < 20 lines).
* **DRY (Don't Repeat Yourself):** Extract all duplicated code into reusable functions.
* **YAGNI (You Ain't Gonna Need It):** Implement only what is required.
* **Readability & Documentation:** Use descriptive names. Comments explain *why*, not *what*. All non-trivial public functions **MUST** have docstrings.

### 4. Section B: Project Structure & Style Mandates

* **The 400-Line Rule:** No file shall exceed 400 lines. It is a mandatory refactor.
* **One File, One Purpose:** Every file must have a single, clear responsibility.
* **Directory Structure:** Propose a logical structure based on functionality (e.g., `/services`, `/models`).
* **Naming Conventions:** 100% adherence is required.
    * **Python:**
        ```python
        # snake_case for functions/variables, PascalCase for classes
        # SCREAMING_SNAKE_CASE for constants
        ```
    * **Dart/Flutter:**
        ```dart
        // camelCase for functions/variables, PascalCase for classes
        // SCREAMING_SNAKE_CASE for constants
        ```
    * **JavaScript/TypeScript:**
        ```javascript
        // camelCase for functions/variables, PascalCase for classes
        // SCREAMING_SNAKE_CASE for constants
        ```

### 5. Section C: The Mandatory 8-Step Analysis & Refactoring Protocol

1.  **Static Analysis & Naming:** Check linting and 100% naming convention compliance.
2.  **Structural Review:** Verify the 400-Line Rule, One File/Purpose, and DRY.
3.  **Function-Level Review:** Check every function against SRP. Eliminate magic numbers.
4.  **Robustness Check:** Ensure specific error handling and check edge cases.
5.  **Security Review:** Check for hardcoded secrets and common vulnerabilities.
6.  **Test Coverage Review:** Ensure tests cover main paths and edge cases.
7.  **Propose Enhancements:** Create an internal list of required refactors.
8.  **Execute Refactor & Final Verification:** Apply changes and do a final check.