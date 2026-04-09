# Claude Todo List - Permanent Record

NEVER MARK A ITEM AS COMPLETE TILL YOU HAVE TESTED IT FULLY AS PER CLAUDE.md test specs. 

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
