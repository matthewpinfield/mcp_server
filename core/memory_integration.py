#!/usr/bin/env python3
"""
Memory Integration Module
Handles memory prompt enhancement and context building
As per mcp_engineering_plan.md structure
"""

import logging
from typing import List, Dict, Any, Optional
from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)

def build_master_prompt_with_memory(base_prompt, user_message: str):
    """
    Master Prompt Template: Integrates Memory System (Tier 1 + Tier 2) with base prompt
    Moved from chat.py as per engineering plan
    """
    try:
        from tools.knowledge import mcp_get_context, mcp_get_corrections
        
        # Get memory context (Tier 1: Redis recent context + Tier 2: MongoDB profile)
        memory_result = mcp_get_context(user_message, include_long_term=False)
        
        if memory_result.get("status") != "success":
            logger.warning(f"Memory context retrieval failed: {memory_result.get('error', 'unknown')}")
            return base_prompt
            
        context = memory_result.get("context", {})
        short_term = context.get("short_term", [])
        profile = context.get("profile", {})
        
        # Get relevant corrections from MongoDB
        corrections = mcp_get_corrections(limit=3)
        
        # Build memory-enhanced prompt
        memory_sections = []
        
        # Add user profile (Tier 2: Rules & Preferences)
        if profile:
            rules = profile.get("rules", [])
            preferences = profile.get("preferences", {})
            
            if rules:
                rules_text = "\n".join([f"- {rule.get('rule', rule)}" for rule in rules[:5]])
                memory_sections.append(f"**User Rules & Preferences:**\n{rules_text}")
                
            if preferences:
                prefs_text = "\n".join([f"- {k}: {v}" for k, v in preferences.items() if k != "_id"])
                if prefs_text:
                    memory_sections.append(f"**Preferences:**\n{prefs_text}")
        
        # Add recent conversation context (Tier 1: Redis)
        if short_term:
            recent_context = []
            for interaction in short_term[-3:]:  # Last 3 interactions
                messages = interaction.get("messages", [])
                for msg in messages[-2:]:  # Last 2 messages per interaction
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")[:150]  # Truncate for brevity
                    recent_context.append(f"{role}: {content}...")
            
            if recent_context:
                context_text = "\n".join(recent_context)
                memory_sections.append(f"**Recent Context:**\n{context_text}")
        
        # Add learning from corrections
        if corrections:
            correction_lessons = []
            for correction in corrections:
                ai_resp = correction.get("ai_response", "")[:100]
                user_correction = correction.get("user_correction", "")[:100]
                topic = correction.get("topic", "general")
                correction_lessons.append(f"Topic: {topic}\n  My mistake: {ai_resp}...\n  Correction: {user_correction}...")
            
            if correction_lessons:
                lessons_text = "\n\n".join(correction_lessons)
                memory_sections.append(f"**Learn from Past Mistakes:**\n{lessons_text}")
        
        # Combine into enhanced prompt
        if memory_sections:
            memory_context = "\n\n".join(memory_sections)
            
            # Get the original template text and enhance it
            original_template = base_prompt.template if hasattr(base_prompt, 'template') else str(base_prompt)
            
            # Escape any braces in memory context to prevent template errors
            escaped_memory_context = memory_context.replace('{', '{{').replace('}', '}}')
            
            enhanced_template = f"""{original_template}

IMPORTANT CONTEXT FROM MEMORY SYSTEM:
{escaped_memory_context}

Use this memory context to provide personalized, consistent responses that respect user preferences and learn from past interactions."""
            
            # Create new PromptTemplate with enhanced content
            enhanced_prompt = PromptTemplate(
                input_variables=base_prompt.input_variables if hasattr(base_prompt, 'input_variables') else ['tools', 'tool_names', 'agent_scratchpad', 'input'],
                template=enhanced_template
            )
            
            logger.info(f"Enhanced prompt with memory context: {len(memory_sections)} sections")
            return enhanced_prompt
        else:
            logger.info("💭 No memory context available, using base prompt")
            return base_prompt
            
    except Exception as e:
        logger.error(f"💭 Memory prompt enhancement error: {e}")
        return base_prompt