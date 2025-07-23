# Memory System Scaling Plan - 200+ Rules Support

**Date**: 2025-06-22  
**Status**: Analysis Complete, Implementation Pending  
**Priority**: High - Current system will break with 200+ rules

## Current State Analysis

### ✅ Implemented Foundation
- **3-Tier Architecture**: Redis + MongoDB + ChromaDB
- **Basic CRUD**: Add/list/delete/update rules via slash commands
- **Simple Categories**: String-based rule categorization
- **Hard Limits**: 5 rules in prompts, 10 in listings to prevent overflow

### ❌ Critical Missing Features for Scale

#### 1. Rule Intelligence Layer
- **No prioritization system** - all rules treated equally
- **No conflict detection** - contradictory rules allowed
- **No deduplication** - identical rules accumulate
- **No semantic relevance scoring** - rules not matched to context

#### 2. Context Management Issues  
- **Static rule injection** - same 5 rules regardless of query
- **Token overflow risk** - context assembly doesn't scale
- **No dynamic selection** - can't pick relevant rules for situation
- **Fixed token budget** - no intelligent allocation

#### 3. Rule Relationship Management
- **No hierarchy support** - flat category system only
- **No conditional rules** - can't have "if coding Python, then..."
- **No rule dependencies** - can't group related rules
- **No usage analytics** - can't identify important vs unused rules

## Implementation Plan

### Phase 1: Rule Intelligence Engine
**Priority**: Critical  
**Files to modify**: `tools/knowledge.py`

```python
class RuleManager:
    def get_relevant_rules(self, context: str, max_tokens: int) -> List[Rule]:
        # Semantic similarity ranking using ChromaDB
        # Priority-based filtering
        # Token budget optimization
        
    def detect_conflicts(self, new_rule: Rule) -> List[ConflictResult]:
        # Semantic conflict detection
        # Contradiction analysis using embeddings
        
    def score_rule_relevance(self, rule: Rule, context: str) -> float:
        # Context-rule similarity scoring
        # Usage frequency weighting
```

### Phase 2: Context Assembly Optimization
**Priority**: High  
**Files to modify**: `tools/knowledge.py`, memory prompt templates

```python
class ContextAssembler:
    def build_memory_context(self, query: str, token_budget: int) -> MemoryContext:
        # Query-relevant rule selection
        # Hierarchical rule organization  
        # Dynamic token allocation based on rule importance
```

### Phase 3: Rule Hierarchy & Management
**Priority**: Medium  
**Schema changes**: MongoDB rule structure

```python
rule_schema = {
    "rule": str,
    "category": str,           # "coding.python.style" 
    "priority": int,           # 1-10 scale
    "conditions": List[str],   # When this rule applies
    "conflicts_with": List[str], # Rule IDs that conflict
    "usage_count": int,        # Analytics
    "last_used": datetime,     # Cleanup automation
}
```

### Phase 4: Advanced Features
**Priority**: Low
- Automatic rule archival
- Usage analytics dashboard
- Rule recommendation engine
- Bulk rule operations

## Technical Implementation Notes

### Database Changes Required
1. **MongoDB schema update** for rule metadata
2. **ChromaDB integration** for semantic rule matching
3. **Usage tracking** collection for analytics

### Performance Considerations
- Implement **caching layer** for frequently accessed rules
- Use **background processing** for rule conflict detection
- Add **token counting** to prevent context overflow
- Create **rule indexing** for faster retrieval

### Testing Strategy
1. **Load testing** with 200+ rules
2. **Performance benchmarks** for rule selection
3. **Context overflow prevention** testing
4. **Rule conflict detection** accuracy testing

## Next Session Tasks

### Immediate Actions (Start Here)
1. **Review current rule storage** in MongoDB
2. **Design rule scoring algorithm** for relevance
3. **Implement basic prioritization** in existing CRUD operations
4. **Add token counting** to context assembly

### Architecture Decisions Needed
- Rule priority scale (1-10 vs weighted scoring)
- Conflict resolution strategy (block vs warn vs override)
- Semantic similarity threshold for deduplication
- Token budget allocation algorithm

## Files Modified Today
- `/mnt/caseSSD/mcp_server_project/tools/web.py` - Added timeout budget system
- `/mnt/caseSSD/mcp_server_project/tools/knowledge.py` - Increased RAG results to 10
- `/mnt/caseSSD/mcp_server_project/tools/development.py` - Added system-wide file reader

## Context for Tomorrow
The memory system has good foundations but will fail with 200+ rules due to missing intelligence layer. Focus should be on implementing rule relevance scoring and dynamic context assembly before adding more features.

**Key Question**: How to balance rule comprehensiveness vs context token limits when user has 200+ rules?