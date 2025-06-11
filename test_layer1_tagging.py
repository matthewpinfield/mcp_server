#!/usr/bin/env python3
"""
Test script for Enhanced Layer 1 Tagging System
"""

import time
import json
from typing import List, Dict

# Copy the classes and functions we need to test
class SessionContext:
    """Tracks ongoing session context for intelligent Layer 1 tagging"""
    def __init__(self):
        self.current_session = {
            "primary_domain": None,
            "active_language": None,
            "ongoing_task": None,
            "established_concepts": set(),
            "conversation_depth": 0,
            "user_expertise_level": "unknown",  # beginner, intermediate, advanced
            "session_start_time": time.time()
        }
        self.conversation_patterns = []
    
    def update_from_messages(self, messages: List[Dict]):
        """Update session context based on conversation history"""
        if not messages:
            return
            
        self.current_session["conversation_depth"] = len(messages)
        
        # Analyze conversation patterns
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        assistant_messages = [msg for msg in messages if msg.get("role") == "assistant"]
        
        if user_messages:
            # Determine expertise level from question complexity
            recent_user_content = " ".join([msg.get("content", "") for msg in user_messages[-3:]])
            self._analyze_expertise_level(recent_user_content)
            
            # Track established concepts
            self._extract_ongoing_concepts(recent_user_content)
            
            # Determine primary domain persistence
            self._analyze_domain_consistency(user_messages)
            
            # Track task progression
            self._analyze_task_progression(user_messages, assistant_messages)
    
    def _analyze_expertise_level(self, content: str):
        """Determine user expertise from conversation complexity"""
        content_lower = content.lower()
        
        beginner_indicators = ["how do i", "what is", "basic", "simple", "beginner", "new to", "first time"]
        advanced_indicators = ["optimize", "performance", "architecture", "scalability", "design pattern", "best practice"]
        
        beginner_score = sum(1 for indicator in beginner_indicators if indicator in content_lower)
        advanced_score = sum(1 for indicator in advanced_indicators if indicator in content_lower)
        
        if advanced_score > beginner_score and advanced_score >= 2:
            self.current_session["user_expertise_level"] = "advanced"
        elif beginner_score > advanced_score and beginner_score >= 2:
            self.current_session["user_expertise_level"] = "beginner"
        else:
            self.current_session["user_expertise_level"] = "intermediate"
    
    def _extract_ongoing_concepts(self, content: str):
        """Extract and maintain set of concepts being discussed"""
        content_lower = content.lower()
        
        concept_keywords = {
            "state_management": ["state", "bloc", "provider", "riverpod", "redux"],
            "async_programming": ["async", "await", "future", "stream", "isolate"],
            "navigation": ["navigation", "routing", "navigator", "route", "page"],
            "ui_components": ["widget", "component", "ui", "layout", "design"],
            "data_persistence": ["database", "storage", "cache", "local", "persist"],
            "api_integration": ["api", "http", "rest", "graphql", "endpoint"],
            "testing": ["test", "unit test", "widget test", "integration test"],
            "performance": ["performance", "optimization", "memory", "cpu", "lag"]
        }
        
        for concept, keywords in concept_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                self.current_session["established_concepts"].add(concept)
    
    def _analyze_domain_consistency(self, user_messages: List[Dict]):
        """Determine if user is consistently working in a domain"""
        if len(user_messages) < 3:
            return
            
        recent_content = " ".join([msg.get("content", "") for msg in user_messages[-5:]])
        
        domain_scores = {
            "flutter_mobile": ["flutter", "dart", "widget", "mobile", "app"],
            "web_development": ["web", "html", "css", "javascript", "frontend"],
            "backend": ["api", "server", "backend", "database", "endpoint"],
            "ai_ml": ["ai", "ml", "machine learning", "neural", "model"]
        }
        
        scores = {}
        for domain, keywords in domain_scores.items():
            scores[domain] = sum(1 for keyword in keywords if keyword in recent_content.lower())
        
        if scores:
            primary_domain = max(scores, key=scores.get)
            if scores[primary_domain] >= 3:  # Consistent mention
                self.current_session["primary_domain"] = primary_domain
    
    def _analyze_task_progression(self, user_messages: List[Dict], assistant_messages: List[Dict]):
        """Analyze what kind of task user is working on"""
        if not user_messages:
            return
            
        recent_user = " ".join([msg.get("content", "") for msg in user_messages[-3:]])
        recent_assistant = " ".join([msg.get("content", "") for msg in assistant_messages[-3:]])
        
        # Look for task progression patterns
        if "error" in recent_user.lower() or "problem" in recent_user.lower():
            self.current_session["ongoing_task"] = "debugging"
        elif "how to" in recent_user.lower() or "tutorial" in recent_user.lower():
            self.current_session["ongoing_task"] = "learning"
        elif "create" in recent_user.lower() or "build" in recent_user.lower():
            self.current_session["ongoing_task"] = "development"
        elif len(recent_assistant) > len(recent_user) * 2:  # Long explanations
            self.current_session["ongoing_task"] = "explanation"

# Global session context
session_context = SessionContext()

PROGRAMMING_LANGUAGES = ["python", "dart", "flutter", "javascript", "typescript", "java", "c++", "c#", "rust", "go", "php", "ruby"]

def extract_layer1_tags(user_message: str, conversation_context: List[Dict]) -> Dict[str, str]:
    """
    Layer 1 Manual Tagging: Real-time context-aware tagging by the Orchestrator.
    
    This analyzes the current session context, conversation patterns, and user behavior
    to generate intelligent tags that reflect the actual programming context and task.
    """
    global session_context
    
    # Update session context with full conversation
    session_context.update_from_messages(conversation_context)
    
    tags = {}
    user_message_lower = user_message.lower()
    session = session_context.current_session
    
    # ===== DOMAIN TAGGING (based on session consistency) =====
    if session["primary_domain"]:
        # Use established session domain
        if session["primary_domain"] == "flutter_mobile":
            tags["domain"] = "programming"
            tags["subdomain"] = "mobile_development"
            tags["framework"] = "flutter"
        elif session["primary_domain"] == "web_development":
            tags["domain"] = "programming"
            tags["subdomain"] = "web_development"
        elif session["primary_domain"] == "backend":
            tags["domain"] = "programming"
            tags["subdomain"] = "backend_development"
        elif session["primary_domain"] == "ai_ml":
            tags["domain"] = "programming"
            tags["subdomain"] = "ai_ml"
    else:
        # Fallback to message-level detection
        if any(keyword in user_message_lower for keyword in ["flutter", "dart", "widget"]):
            tags["domain"] = "programming"
            tags["subdomain"] = "mobile_development"
            tags["framework"] = "flutter"
        elif any(keyword in user_message_lower for keyword in ["api", "backend", "server"]):
            tags["domain"] = "programming"
            tags["subdomain"] = "backend_development"
    
    # ===== LANGUAGE TAGGING (session-aware) =====
    if session["active_language"]:
        tags["language"] = session["active_language"]
    else:
        # Detect from current message
        for language in PROGRAMMING_LANGUAGES:
            if language in user_message_lower:
                tags["language"] = language
                session_context.current_session["active_language"] = language
                break
    
    # ===== TASK TAGGING (based on session progression) =====
    if session["ongoing_task"]:
        tags["task"] = session["ongoing_task"]
    else:
        # Message-level task detection
        if any(keyword in user_message_lower for keyword in ["error", "bug", "fix", "debug"]):
            tags["task"] = "debugging"
        elif any(keyword in user_message_lower for keyword in ["how to", "tutorial", "learn"]):
            tags["task"] = "learning"
        elif any(keyword in user_message_lower for keyword in ["create", "build", "make"]):
            tags["task"] = "development"
        elif any(keyword in user_message_lower for keyword in ["explain", "what is", "understand"]):
            tags["task"] = "explanation"
    
    # ===== CONCEPT TAGGING (from established session concepts) =====
    if session["established_concepts"]:
        # Use the most relevant established concept
        for concept in session["established_concepts"]:
            if concept.replace("_", " ") in user_message_lower or concept.replace("_", "") in user_message_lower:
                tags["concept"] = concept
                break
        
        # If no direct match, use the primary concept
        if "concept" not in tags and session["established_concepts"]:
            tags["concept"] = list(session["established_concepts"])[0]
    
    # ===== EXPERTISE LEVEL =====
    tags["user_level"] = session["user_expertise_level"]
    
    # ===== SESSION METADATA =====
    tags["conversation_depth"] = str(session["conversation_depth"])
    tags["session_duration"] = str(int(time.time() - session["session_start_time"]))
    
    # ===== CONTEXT-SPECIFIC ENHANCEMENTS =====
    
    # If this is a follow-up question, mark it
    if session["conversation_depth"] > 2:
        recent_topics = []
        for msg in conversation_context[-3:]:
            if msg.get("role") == "user":
                recent_topics.extend(msg.get("content", "").lower().split())
        
        # Check for follow-up indicators
        if any(word in user_message_lower for word in ["also", "additionally", "furthermore", "and", "another"]):
            tags["interaction_type"] = "follow_up"
        elif any(word in user_message_lower for word in ["but", "however", "instead", "different"]):
            tags["interaction_type"] = "clarification"
        elif any(word in user_message_lower for word in ["thanks", "thank you", "got it", "understood"]):
            tags["interaction_type"] = "acknowledgment"
    
    # Mark complex vs simple questions
    if len(user_message.split()) > 20 or any(word in user_message_lower for word in ["complex", "advanced", "detailed"]):
        tags["complexity"] = "high"
    elif len(user_message.split()) < 8:
        tags["complexity"] = "low" 
    else:
        tags["complexity"] = "medium"
    
    print(f"🏷️ Layer 1 Context-Aware Tags: {tags}")
    print(f"📊 Session Context: domain={session['primary_domain']}, task={session['ongoing_task']}, level={session['user_expertise_level']}, concepts={list(session['established_concepts'])}")
    
    return tags

if __name__ == "__main__":
    print("=== Testing Enhanced Layer 1 Context-Aware Tagging ===\n")
    
    # Test scenario: User learning Flutter over multiple messages
    conversation = [
        {'role': 'user', 'content': 'I am new to Flutter development. How do I create my first app?'},
        {'role': 'assistant', 'content': 'To create your first Flutter app, you can use flutter create command...'},
        {'role': 'user', 'content': 'What is a widget in Flutter?'},
        {'role': 'assistant', 'content': 'A widget is the basic building block of Flutter UI...'},
        {'role': 'user', 'content': 'How do I manage state in Flutter? I heard about Provider and Bloc.'},
        {'role': 'assistant', 'content': 'State management is crucial in Flutter. Provider and Bloc are popular solutions...'},
        {'role': 'user', 'content': 'Can you show me an example of async programming with Future?'}
    ]
    
    # Test progression of tagging
    for i in range(0, len(conversation), 2):  # Every user message
        if i < len(conversation) and conversation[i]['role'] == 'user':
            context = conversation[:i+2] if i+1 < len(conversation) else conversation[:i+1]
            user_msg = conversation[i]['content']
            
            print(f"\n--- Message {i//2 + 1}: \"{user_msg[:50]}...\" ---")
            tags = extract_layer1_tags(user_msg, context)
            print("\nExtracted Tags:")
            for key, value in tags.items():
                print(f"  {key}: {value}")
            print("-" * 60)
    
    print("\n=== Testing Advanced User Scenario ===\n")
    
    # Reset session for advanced user test
    session_context = SessionContext()
    
    advanced_conversation = [
        {'role': 'user', 'content': 'How can I optimize Flutter performance for complex animations and large datasets?'},
        {'role': 'assistant', 'content': 'For performance optimization, consider these advanced techniques...'},
        {'role': 'user', 'content': 'I need to implement a custom widget that efficiently handles state updates.'},
        {'role': 'assistant', 'content': 'Custom widgets with efficient state management require...'}
    ]
    
    for i in range(0, len(advanced_conversation), 2):
        if i < len(advanced_conversation) and advanced_conversation[i]['role'] == 'user':
            context = advanced_conversation[:i+2] if i+1 < len(advanced_conversation) else advanced_conversation[:i+1]
            user_msg = advanced_conversation[i]['content']
            
            print(f"\n--- Advanced Message {i//2 + 1}: \"{user_msg[:50]}...\" ---")
            tags = extract_layer1_tags(user_msg, context)
            print("\nExtracted Tags:")
            for key, value in tags.items():
                print(f"  {key}: {value}")
            print("-" * 60)