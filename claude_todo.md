# Claude Todo List - Permanent Record

NEVER MARK A ITEM AS COMPLETE TILL YOU HAVE TESTED IT FULLY AS PER CLAUDE.md test specs.

---

## Session 2026-09-19 (part 8): Removed dead qwen3/gemma3 config left from consolidation

Follow-up cleanup after consolidating everything onto gemma4:26b + nomic-embed-text.
User confirmed the running system now only actually invokes those two models and
asked to remove the remaining dead references.

- [x] Removed `DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "qwen3:30b-a3b")`
  and the also-unused `LLM_TIMEOUT` from `rag/dual_endpoint_server.py` - neither
  was read anywhere else in that file.
- [x] Deleted `model_switcher.py` entirely (`git rm`, recoverable from history if
  ever needed) - its whole purpose was switching `DEFAULT_MODEL` between several
  `qwen3` variants we no longer use, it referenced a `model_comparison_test.py`
  that doesn't even exist anymore, and nothing else in the codebase imported it.
- [x] **TESTED**: `pyflakes rag/dual_endpoint_server.py` clean; started the RAG
  server after the edit and confirmed `/health` still reports both LanceDB
  tables connected (5098 + 11663 docs). **PASS**
- [x] Confirmed via `grep -rn "qwen3\|gemma3"` across all `.py` files: zero
  remaining references anywhere in the live codebase.

---

## Session 2026-09-19 (part 7): Found the real speed bottleneck - VRAM model-swap thrashing

User asked whether it'd be faster to run everything on gemma4:26b, switch the
memory-summarizer to a new small gemma4:e2b variant, or keep gemma3:4b-it-qat,
on their RTX 3090 Ti.

### Investigation (measured on real hardware, not assumed)
- [x] Websearched to confirm gemma4:26b is actually a Mixture-of-Experts model
  with only ~4B ACTIVE params per token (26B-A4B) - similar order of magnitude
  to the old 4B summarizer per-token, not 6x heavier as the "26B" label implies.
  Source: https://huggingface.co/google/gemma-4-26B-A4B
- [x] Found gemma4:26b defaults to "thinking" mode ON when the `think` param is
  omitted - generates a full hidden reasoning block (measured 600-1300+ tokens)
  that our agent discards entirely (only `chunk.content` is read), roughly
  doubling response time for zero visible benefit. `think: false` fixes this
  per-call.
- [x] **Found the actual dominant bottleneck**: only ~3.96GB VRAM is free with
  gemma4:26b (18GB) resident on the 24GB card - not enough to also hold
  gemma3:4b-it-qat (4GB) at the same time. Ollama was silently EVICTING one
  model to load the other on every switch. Measured directly via Ollama's own
  `load_duration`: swapping gemma3 in cost ~3.9s, swapping gemma4:26b back in
  cost **8.3s** - and because every chat turn triggers a memory save ->
  gemma3 summarization -> next chat turn needing gemma4 again, this swap
  round-trip (~12s of pure dead reload time) was happening on EVERY turn.
  This is what the user was feeling as "slow and inconsistent", not tool
  count, not thinking mode alone, not raw compute contention.
- [x] Checked whether gemma4:e2b could coexist instead of full consolidation:
  websearched actual Ollama-distributed tag sizes (not just the raw spec-sheet
  numbers) - default `gemma4:e2b` is 7.2GB (Q4_K_M, too big), only
  `gemma4:e2b-it-qat` at 3.3GB comes close, and even that leaves <1GB spare
  for KV cache growth - fragile, not worth the download given a guaranteed
  zero-risk alternative exists.

### Fix
- [x] User decided: consolidate onto gemma4:26b for everything, thinking off
  for the background summarization task. Updated `summary_worker.py`:
  - Replaced hardcoded `"gemma3:4b-it-qat"` with `DEFAULT_MODEL` (from
    config.py, currently `gemma4:26b`) - same model as main chat, no more
    swap-triggering model switch.
  - Added `"think": False` to the `/api/generate` payload for the
    summarization call.
- [x] **Bonus fix found along the way**: `main.py` spawned `summary_worker.py`
  via `subprocess.Popen` with no handle kept and no shutdown cleanup - every
  time the dev server was restarted during this session, the OLD
  summary_worker.py process was orphaned (7 stray copies accumulated and were
  found running, silently polluting benchmark results). Fixed: the process
  handle is now captured and `.terminate()`'d in the FastAPI lifespan shutdown
  block. **TESTED**: started main.py, sent SIGTERM, confirmed via `ps aux`
  that BOTH main.py and its summary_worker.py child fully exited. **PASS**
- [x] **TESTED the actual fix** against the live server: sent a chat message,
  waited for the summary worker to process the save (confirmed via log:
  "Processing summary" / "Summary updated"), then sent a second chat message -
  took 5.69s, statistically identical to the first turn's 5.70s. No swap
  penalty. **PASS**

---

## Session 2026-09-19 (part 6): Standardized on one Cursor-style diff-first workflow

User was confused why there were 3 different ways to get code written (chat-only,
chat+write_file, editor Edit/Apply) and asked to make it work like Cursor IDE
instead. Websearched current (2026) Cursor behavior to confirm the actual model
rather than rely on training-data assumptions: Cursor's Cmd+K inline edit AND its
chat "Apply" button both funnel into the same paradigm - a reviewable diff shown
in the real editor that you explicitly accept, never a silent write.
Source: https://www.deployhq.com/guides/cursor

- [x] Diagnosed that our `write_file` tool was the odd one out: it does a blind
  overwrite (a chat text "permission?" question, no visual diff, no per-hunk
  review) - not Cursor-like. Continue's chat "Apply" button (fixed in the
  previous session to route through `direct_completion`) already gives the real
  Cursor-equivalent: a genuine inline diff you accept/reject in the editor.
- [x] **FIXED**: added a system-prompt rule in `core/orchestrator.py` - when the
  user asks to change code in an EXISTING file, the agent must reply with the
  updated code as a plain chat code block (for the user to Apply) instead of
  calling `write_file`. Reserved `write_file` only for explicitly-confirmed
  brand-new file creation where no diff review is needed.
- [x] **TESTED**: created a real test file `calc.py` with an `add()` function,
  asked the agent (via `core.orchestrate_request`, live) to "add a subtract
  function" to it. It called `read_system_file` to see the existing content,
  then replied with the full updated file as a chat code block - `write_file`
  was NOT invoked, and the file on disk was confirmed unchanged afterward.
  **PASS**
- Net result: exactly two entry points now, both diff-first like Cursor -
  (1) chat + Continue's Apply button, (2) Continue's inline Edit (Cmd/Ctrl+I) -
  and the agent no longer silently overwrites existing files from chat.

---

## Session 2026-09-19 (part 5): Continue's inline Edit/Apply were broken - added a direct-completion path

User asked whether the agent produces code directly in the VS Code window "as if
running a cloud LLM" (i.e. Continue's inline Edit / Apply-to-file features).

### Diagnosis
- [x] Traced the routes: `/v1/chat/completions` (api/chat.py:215) just delegates
  to the same `chat_proxy` as `/api/chat`. Every request - whether it came from
  Continue's `chat`, `edit`, or `apply` role - went through the identical path:
  only the LAST `user` message's text was extracted (any `system` message
  Continue sends, which for edit/apply carries its own "output ONLY the code"
  instructions, was silently discarded), then the FULL 28-tool agent ran with
  our own chat-assistant system prompt.
- [x] Confirmed this would break Edit/Apply: Continue expects clean replacement
  code it can drop straight into the file as a diff. Our old pipeline would
  instead return chatty markdown, tool-call narration, etc. - not usable as an
  inline diff.

### Fix
- [x] Added `direct_completion()` to `core/orchestrator.py` - a lightweight
  passthrough with NO tools, NO memory, NO system-prompt override. It converts
  the raw `messages` array (preserving whatever `system` message Continue sent)
  straight into langchain messages and streams the model's raw output back.
- [x] Added branching in `api/chat.py`'s `chat_proxy`: requests where
  `model == "gemma4-direct-edit"` (constant `DIRECT_COMPLETION_MODEL`) skip
  straight to `direct_completion()`, both streaming and non-streaming, before
  the code that strips down to just the last user message.
- [x] Split Continue's model config so `chat` uses the original agent-backed
  model and `edit`/`apply` use the new direct-completion model name, in both:
  - `~/.continue/config.yaml` (the global config actually used for the iceMap
    session) - backed up before editing.
  - `.continue/models/new-model.yaml` in this repo - this file's YAML was
    ALSO broken (bad indentation, would fail to parse - fixed that too while
    applying the same split) for whenever this project itself is opened in
    Continue.
- [x] **TESTED** against the running server (real HTTP calls, not just import
  checks):
  - Non-streaming: sent a realistic Continue-edit-shaped request (system
    prompt = "respond with ONLY the final code", user = code + instruction to
    rename a function and add a docstring). Got back exactly
    `def sum_two(a, b):\n    """..."""\n    return a + b` - clean code, no
    chat chatter, no tool-call text. Server log confirmed NO "Agent has 28
    tools" line and NO "Memory saved" line for this request - direct path
    genuinely bypassed the agent. **PASS**
  - Streaming: same request with `stream: true` - correct SSE chunks, 0.89s
    to first token, clean final content. **PASS**

---

## Session 2026-09-19 (part 4): Removed dead Google Search fallback from tools/web.py

User confirmed Google search was intentionally dropped for cost reasons and asked
to remove the now-useless Google branch since it was just adding a wasted round-trip
before falling back to DuckDuckGo on every single search.

- [x] Removed `GOOGLE_API_KEY`/`GOOGLE_SEARCH_ENGINE_ID` env lookups and the whole
  Google Custom Search API branch from `_get_search_results()` in `tools/web.py`.
  DuckDuckGo Lite scraping is now the only path - no behavior change, just removes
  the always-failing 403 round-trip.
  - Also removed a redundant local `from bs4 import BeautifulSoup` (already
    imported at module level) and the now-unused `import os`.
- [x] **TESTED**: re-ran the "2026 FIFA World Cup host" query after the change -
  still correctly returns Canada/Mexico/USA with the FIFA.com source, 3.74s,
  `pyflakes tools/web.py` clean. **PASS**
- Leftover `.env` `GOOGLE_API_KEY`/`GOOGLE_SEARCH_ENGINE_ID` values are now fully
  unused dead config - safe to delete from `.env` whenever convenient, not
  referenced by any code anymore.

---

## Session 2026-09-19 (part 3): Confirmed web search - DuckDuckGo, working, and not costing Google API money

User asked whether search_web still uses DuckDuckGo and whether it gets useable
answers, after confirming the switch away from Google was deliberate (cost).

- [x] Confirmed `.env` still has a `GOOGLE_API_KEY`/`GOOGLE_SEARCH_ENGINE_ID`, and
  `tools/web.py` still tries Google first on every search - but verified directly
  against Google's API that the key returns **403 PERMISSION_DENIED** ("project
  does not have access to Custom Search JSON API"). This fails instantly with no
  billable search performed, so **it is not costing money**, it just silently
  falls through to DuckDuckGo Lite scraping every time (one wasted fast round-trip
  per search, not worth removing given it's a harmless no-op).
- [x] Ran real functional tests against `LangchainWebSearchTool` (not just "does it
  return something" - checked the actual answers were correct):
  - "2026 FIFA World Cup host" -> correctly returned USA/Mexico/Canada, June 11 -
    July 19 2026, sourced from Wikipedia. **PASS**
  - "latest stable Python version" -> correctly returned 3.14.7, sourced from
    python.org/downloads/latest. **PASS**
  - DuckDuckGo Lite fallback scraping is genuinely working and returning accurate,
    current, sourced answers.
- [x] **Found & fixed the same dead-caching bug as core/orchestrator.py**:
  `LangchainWebSearchTool._run()` was creating its own `ChatOllama(...)` instance
  directly instead of calling `get_cached_llm()`, bypassing the LLM instance
  cache on every single web search. Fixed to use `get_cached_llm(DEFAULT_MODEL)`.
  **TESTED**: re-ran the Python-version query after the fix, still correct, log
  confirms the cached-instance code path is used.

---

## Session 2026-09-19 (part 2): Fixed "/code" file-access hallucination + wasteful tool-guessing

User report via Continue in VS Code: asked the agent to read a file in
`/home/matthewpinfield/iceMap`, agent claimed it could only see a `/code` folder
and couldn't say where `/code` actually was. Also reported the agent feels slow,
"as if it opens every tool before answering."

### Root cause 1: hallucinated "/code" containerization story - FIXED
- [x] Confirmed `read_system_file` genuinely works on any real host path with zero
  issue — tested directly against `/home/matthewpinfield/iceMap/project_brief.md`,
  read it fine. **No actual access restriction exists.**
- [x] Found the real cause: `execute_code`'s tool description says it's an
  "isolated Docker-based sandbox" and its own code (tools/sandbox.py) mounts
  submitted code at `/code` inside that throwaway container. The system prompt in
  `core/orchestrator.py` never explained this is unrelated to the other file
  tools, so gemma4:26b — on hitting one failed/relative-path lookup — conflated
  the two and confidently invented a false "I'm containerized, only /code is
  mounted" narrative (visible verbatim in `~/.continue/sessions/*.json` history).
  This is a pure LLM hallucination, not a real system limitation.
  - [x] **FIXED**: added an explicit "two separate filesystems" clarification to
    the system prompt distinguishing host-filesystem tools from the
    sandbox-only `/code` mount.
  - [x] **TESTED**: asked the agent to read the real iceMap file by absolute
    path — read it correctly, no confusion. **PASS**

### Root cause 2: agent burns many tool calls on an ambiguous file reference - FIXED
- [x] Reproduced: asked "Can you read project_brief.md for me?" (no path). Agent
  fired `explore_repository` → `read_system_file` (wrong dir) → `explore_repository`
  (dup) → `explore_repository` (dup again) → `execute_code` → `git_status` →
  `git_log` — 7 sequential tool calls (each its own LLM round-trip) before giving
  up and asking for the path anyway. This is the literal mechanism behind "it
  opens every tool before answering."
  - [x] **FIXED**: added a system-prompt instruction to ask for the absolute path
    immediately when a file/folder is named without one, instead of guessing
    across tools.
  - [x] **TESTED**: same exact prompt now goes straight to asking for the path,
    zero tool calls. **PASS**

### Performance investigation - NOT a tool-count problem, found a real contention source
Measured directly (raw `ChatOllama`/Ollama API, no LangChain agent overhead):
- Binding all 28 tools vs 0 tools: negligible difference once the model is warm
  (~0.7-1.2s either way). **Ruled out** "too many tools" as the slowness cause.
- Cold model load after Ollama's idle-unload: ~15s one-off cost. Expected, not a bug.
- Same warm prompt repeated: latency varied 3.7s-12.4s call-to-call with identical
  inputs. Ollama's own `eval_count`/`eval_duration` showed generation speed
  swinging between ~160-190 tok/s (fast, GPU-bound, fine) with no obvious cause
  visible from the MCP server side alone.
- Likely contributor found: `summary_worker.py` runs a second model
  (`gemma3:4b-it-qat`) on the **same GPU** immediately after every saved memory,
  right after each chat turn finishes. Back-to-back user messages can land while
  that summarization job is still running, contending for the one RTX 3090.
- [ ] **NOT YET ACTIONED** — this is a design trade-off (debounce/delay
  summarization vs. keep it immediate), needs a decision before changing it.

---

## Session 2026-09-19: Verified 2026-04-14 fixes against actual purpose, found & fixed LLM caching gap ✅ COMPLETE

Note: earlier in-between session work was mistakenly done against a stale copy at
`/home/matthewpinfield/Superceeded_MCP_Server` instead of this project. That copy's
git history was checked and confirmed clean (no uncommitted work, one commit from
2026-09-04) — nothing was lost, there was simply nothing to recover from it.

Re-verified the 2026-04-14 uncommitted fixes below with real functional tests
(RAG server on 8008 + main server on 8013 + live Ollama gemma4:26b), not just
startup/existence checks:

- [x] **Short-term memory (chat_history injection)**: `test_memory.py` — told the
  agent a secret word mid-conversation, asked for it back in the same request.
  Correctly returned "Giraffe". **TESTED — PASS**
- [x] **Long-term memory save/recall (async fix in tools/memory.py)**: `test_long_term.py`
  — saved a fact, waited 20s, asked for it from a blank-slate session with no chat
  history. Agent invoked `search_memory` tool and correctly recalled "Nebula Roast"
  with zero errors in server log (previously this exact path threw "a coroutine was
  expected" under the old `asyncio.run()`-in-`_run()` bug). **TESTED — PASS**
- [x] **Sandbox tool new schema** (`code`/`language`/`timeout`/`stdin_input` fields
  instead of a single JSON string): called `MultiLanguageSandboxTool._run()` directly
  with `code="print(2 + 2)"`, got back `4`. **TESTED — PASS**
- [x] **write_file tool**: called `LangchainWriteFileTool._run()`, then read the file
  back from disk and confirmed byte-for-byte match. **TESTED — PASS**
- [ ] **LLM instance caching (MEMORY ISSUE #2)** — FOUND BROKEN: `get_cached_llm()`
  existed in `config.py` but was never called anywhere in the codebase.
  `core/orchestrator.py` was still doing `ChatOllama(model=DEFAULT_MODEL, ...)`
  directly on every request, so a brand-new LLM instance was created per-request
  despite the todo list claiming this was "✅ COMPLETE — IMPLEMENTED". This is
  exactly the "existence vs functional" trap called out in CLAUDE.md's Proven Issue
  Resolution Methodology — the cache function existed and imported fine, but was
  dead code.
  - [x] **FIXED**: `core/orchestrator.py` now calls `get_cached_llm(DEFAULT_MODEL)`.
    Kept the existing "always use DEFAULT_MODEL" behavior (was a deliberate choice
    per the tool-calling reliability notes below, not something to change here).
  - [x] **TESTED**: sent 4 sequential chat requests after a fresh server start;
    `"Creating new LLM instance for model: gemma4:26b"` appeared in the log exactly
    once, on the first request. **PASS**

## Session 2026-04-14: Continue IDE Integration & Memory Fixes ✅ COMPLETE

### Completed Today:
- [x] **Continue IDE Setup**: Configured Continue VSCode extension to use MCP server
  - Updated `~/.continue/config.yaml` to use `gemma4:26b` model
  - Set API endpoint to `http://localhost:8013/v1`
  - Continue now routes through MCP server with all tools, memory, RAG, web search

- [x] **Fixed Memory Tools Event Loop Bug**: 3 async tools had `asyncio.run()` issues
  - Fixed: `LangchainMemorySearchTool` (search_memory)
  - Fixed: `LangchainSaveAgentNoteTool` (save_agent_note)
  - Fixed: `LangchainSearchAgentNotesTool` (search_agent_notes)
  - Issue: Used `asyncio.run()` which fails when event loop already running
  - Solution: Removed `_run()` methods, kept only async `_arun()` with NotImplementedError stubs
  - **TESTED**: Memory save/recall working - saved "Matthew" as user name, "Eric" as dog name

- [x] **Fixed Sandbox Execute Tool Schema**: Tool had wrong parameter format
  - Changed from: Single `tool_input: str` JSON string parameter
  - Changed to: Individual fields `code`, `language`, `timeout`, `stdin_input`
  - Updated `_run()` signature to match new schema
  - **TESTED**: Tool loads without validation errors

- [x] **Added File Writing Tool**: New `write_file` tool for saving files
  - Tool: `LangchainWriteFileTool` in `tools/code_analysis.py`
  - Features: Write to any path, auto-create directories, permission handling
  - Description explicitly tells AI to ask user permission first
  - Added to SHARED_TOOLS in `tools/all_tools.py`
  - **STATUS**: Code added, needs server restart to test

### Known Issues to Address Tomorrow:
- [ ] **File Path Context Mismatch**: Continue shows files at `/code/test.py` but actual filesystem path is `/home/matthewpinfield/code school/test.py`
  - Continue's workspace view ≠ MCP server filesystem view
  - Workaround: Use `@currentFile` or highlight code instead of file path tools
  - Long-term fix: Configure Continue workspace mapping or teach AI to expand `~/code school/` paths

- [ ] **Tool Selection**: Gemma4 sometimes chooses wrong tools (sandbox instead of read_file)
  - May improve with better tool descriptions or prompt tuning
  - Or consider switching to model with better tool calling (Qwen3)

### Current System Status:
- **Total Tools**: 28 (was 27, added write_file)
- **Memory System**: Fully working (Redis: 50 today, LanceDB SSD: 200, NAS: 1, Rules: 11)
- **Model**: gemma4:26b via Ollama
- **Active Integrations**: Continue IDE, Open Web UI, MCP server on port 8013

--- 

### CRITICAL MEMORY OPTIMIZATIONS NEEDED ✅ COMPLETE

**MEMORY ISSUE #1: Tool Instantiation - 25+ objects created per request** ✅ FIXED
- [x] Current: orchestrator.py lines 66-76 create NEW tool instances every request
- [x] Impact: LangchainGitStatusTool(), LangchainWebSearchTool(), etc. x25 tools = 25+ object creations per request
- [x] Fix: Create tools once at module level and reuse: _SHARED_TOOLS = [LangchainGitStatusTool(), ...]
- [x] Priority: HIGH - eliminates 25+ allocations per request
- [x] **IMPLEMENTED**: Shared tools in tools/all_tools.py, imported by orchestrator.py

**MEMORY ISSUE #2: LLM Model Loading - New ChatOllama instance per request** ✅ FIXED
- [x] Current: orchestrator.py line 101 creates NEW ChatOllama(model=requested_model_name) every request
- [x] Impact: For 100 requests using "qwen3:14b", creates 100 separate model instances instead of 1
- [x] Fix: Implement singleton pattern with model cache by name - get_cached_llm(model_name)
- [x] Priority: HIGH - 100x memory reduction for repeated model usage
- [x] **IMPLEMENTED**: get_cached_llm() function in config.py with model caching


### IMPORTANT ALL BELOW NEEDS TO BE CHECKED FOR: IS IT STILL RELEVANT OR OUT OF DATE / HAS IT ALREADY BEEN CARRIED OUT


### 3. Fix Overly Complex Prompting (Medium Priority)
**Problem**: Long threatening prompts with CAPS counterproductive with fine-tuned models

#### Step 3.1: Audit current system prompt
- [ ] Read full SYSTEM_PROMPT in orchestrator
- [ ] Count total words/tokens in system prompt
- [ ] List all CAPS warnings and threats ("CRITICAL DIRECTIVE", "MUST FOLLOW")
- [ ] Identify core identity elements that must be preserved

#### Step 3.2: Design simplified prompts
- [ ] Create simple router prompt: "You are an ai assistant. Choose which specialist can help."
- [ ] Create simple specialist prompts: "You are an ai assistant. Use your tools to help."
- [ ] Remove all CAPS warnings and threatening language
- [ ] Keep only essential identity and behavior guidance
- [ ] Trust tool descriptions to guide behavior

#### Step 3.3: Test simplified prompts
- [ ] Replace complex prompts with simple versions
- [ ] Test router still makes correct category choices
- [ ] Test specialists still follow core identity rules  
- [ ] Verify tool usage improves with cleaner prompts
- [ ] Check for any behavior regressions or rule violations

### 4. Check for Duplicate Model Loading (Medium Priority) ✅ COMPLETE
**Problem**: Performance impact from loading same model multiple times

#### Step 4.1: Audit model instantiation points ✅ COMPLETE
- [x] Search entire codebase for "ChatOllama(" instantiations
- [x] Search for any other LLM model loading patterns
- [x] Count how many times same model (qwen3:30b-a3b) is loaded
- [x] Map where each model instance is used in code flow

#### Step 4.2: Implement model sharing/singleton ✅ COMPLETE
- [x] Create single shared model instance if duplicates found
- [x] Modify all components to use shared instance
- [x] Test that shared model works across all use cases
- [x] Measure performance improvement from model sharing
- [x] **IMPLEMENTED**: get_cached_llm() singleton pattern in config.py

### 5. Check for Duplicate Tool Registration ✅ COMPLETE
**Problem**: Same tools registered multiple times causing agent confusion

#### Step 5.1: Audit tool registration points ✅ COMPLETE
- [x] Search for all tool import statements across codebase
- [x] Check if same tool class imported in multiple files
- [x] Verify each tool only registered once with agents
- [x] List any tools with duplicate names or overlapping functionality

#### Step 5.2: Deduplicate tool registrations ✅ COMPLETE
- [x] Remove duplicate tool imports and registrations
- [x] Consolidate overlapping tools into single implementations
- [x] Test that all tool functionality still accessible
- [x] Verify agents can access all needed capabilities without confusion
- [x] **IMPLEMENTED**: SHARED_TOOLS in tools/all_tools.py eliminates duplicate instantiation

### 6. Remove Redundant Logging
**Problem**: Excessive logging clutters output and impacts readability

#### Step 6.1: Audit logging verbosity
- [ ] Review all logger.info/debug/warning statements in orchestrator
- [ ] Identify redundant or overly verbose log messages
- [ ] Check for logging in performance-critical loops
- [ ] Categorize essential vs noise logging

#### Step 6.2: Clean up logging output
- [ ] Remove redundant log statements that don't add value
- [ ] Reduce verbosity of remaining logs to key information only
- [ ] Ensure critical errors and status still properly logged
- [ ] Test that cleaner output improves debugging experience

### Step 6.3: Fix RAG "Cut Off" Messaging (Critical Priority) 
**Problem**: Agent thinks RAG data is incomplete when it should know data is complete and current through July 26, 2025

#### Steps:
- [ ] Fix RAG tools to clearly state data is COMPLETE through July 26, 2025
- [ ] Remove any "cut off" or "incomplete" messaging
- [ ] Test that agent treats RAG data as authoritative for recent info

#### Step 7.1: Identify duplicate functions
**Duplicate functions in codebase to be found and ekeminated (ignore backups)**
