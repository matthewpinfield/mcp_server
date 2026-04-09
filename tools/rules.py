#!/usr/bin/env python3
"""
Rules Management Tool
====================
Handles user rules/preferences - the agent's "notebook" of how to behave.
This is SEPARATE from memory (conversations). Rules are persistent configuration.

Rules are like a notebook:
- Agent reads them each day to understand user preferences
- User adds new rules over time
- Rules persist forever (not temporal like memories)
- No embedding/semantic search needed - just CRUD operations
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Type

import pymongo
from pydantic import BaseModel, Field

from config import MONGODB_URI, MONGODB_DATABASE, DEFAULT_USER
from .base import AsyncTool

logger = logging.getLogger(__name__)

# Global MongoDB connection (singleton like RAG pattern)
mongo_client = None
mongo_db = None
rules_collection = None

def get_rules_db():
    """Get or create MongoDB connection for rules (singleton pattern)"""
    global mongo_client, mongo_db, rules_collection
    
    if mongo_client is None:
        try:
            mongo_client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            mongo_client.admin.command("ping")
            mongo_db = mongo_client[MONGODB_DATABASE]
            rules_collection = mongo_db.user_rules
            
            # Create index for fast lookups
            rules_collection.create_index("user_id")
            rules_collection.create_index("created_at")
            
            # Ensure default user profile exists
            if not rules_collection.find_one({"user_id": DEFAULT_USER}):
                default_profile = {
                    "user_id": DEFAULT_USER,
                    "created_at": datetime.now(),
                    "rules": [],
                    "metadata": {
                        "total_rules": 0,
                        "last_updated": datetime.now()
                    }
                }
                rules_collection.insert_one(default_profile)
            
            logger.info("Rules database connected successfully")
            
        except Exception as e:
            logger.error(f"Rules database connection failed: {e}")
            raise
    
    return rules_collection

class RulesManager:
    """Simple rules manager - like a persistent notebook"""
    
    def __init__(self):
        self.collection = get_rules_db()
    
    def add_rule(self, rule_text: str, category: str = "general") -> Dict:
        """Add a new rule to the user's notebook"""
        try:
            rule_id = f"rule_{int(datetime.now().timestamp())}"
            new_rule = {
                "id": rule_id,
                "rule": rule_text.strip(),
                "category": category,
                "added_at": datetime.now(),
                "active": True
            }
            
            # Add rule to user's profile
            result = self.collection.update_one(
                {"user_id": DEFAULT_USER},
                {
                    "$push": {"rules": new_rule},
                    "$set": {"metadata.last_updated": datetime.now()},
                    "$inc": {"metadata.total_rules": 1}
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Added rule: {rule_text[:50]}...")
                return {"status": "success", "rule_id": rule_id, "rule": new_rule}
            else:
                return {"status": "error", "error": "Failed to add rule"}
                
        except Exception as e:
            logger.error(f"Error adding rule: {e}")
            return {"status": "error", "error": str(e)}
    
    def list_rules(self, category: Optional[str] = None, active_only: bool = True) -> Dict:
        """List all rules in the notebook"""
        try:
            profile = self.collection.find_one({"user_id": DEFAULT_USER})
            if not profile or "rules" not in profile:
                return {"status": "success", "rules": [], "count": 0}
            
            rules = profile["rules"]
            
            # Filter by category if specified  
            if category:
                rules = [r for r in rules if r.get("category", "core") == category]
            
            # Filter by active status
            if active_only:
                rules = [r for r in rules if r.get("active", True)]
            
            # Sort by creation date (newest first)
            rules.sort(key=lambda x: x.get("added_at", datetime.min), reverse=True)
            
            return {
                "status": "success", 
                "rules": rules, 
                "count": len(rules),
                "categories": list(set(r.get("category", "general") for r in rules))
            }
            
        except Exception as e:
            logger.error(f"Error listing rules: {e}")
            return {"status": "error", "error": str(e)}
    
    def update_rule(self, rule_id: str, new_text: str) -> Dict:
        """Update an existing rule"""
        try:
            result = self.collection.update_one(
                {"user_id": DEFAULT_USER, "rules.id": rule_id},
                {
                    "$set": {
                        "rules.$.rule": new_text.strip(),
                        "rules.$.updated_at": datetime.now(),
                        "metadata.last_updated": datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                return {"status": "success", "message": f"Rule {rule_id} updated"}
            else:
                return {"status": "error", "error": "Rule not found"}
                
        except Exception as e:
            logger.error(f"Error updating rule {rule_id}: {e}")
            return {"status": "error", "error": str(e)}
    
    def delete_rule(self, rule_id: str) -> Dict:
        """Delete a rule from the notebook"""
        try:
            result = self.collection.update_one(
                {"user_id": DEFAULT_USER},
                {
                    "$pull": {"rules": {"id": rule_id}},
                    "$set": {"metadata.last_updated": datetime.now()},
                    "$inc": {"metadata.total_rules": -1}
                }
            )
            
            if result.modified_count > 0:
                return {"status": "success", "message": f"Rule {rule_id} deleted"}
            else:
                return {"status": "error", "error": "Rule not found"}
                
        except Exception as e:
            logger.error(f"Error deleting rule {rule_id}: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_rules_summary(self) -> Dict:
        """Get summary of rules for agent startup"""
        try:
            profile = self.collection.find_one({"user_id": DEFAULT_USER})
            if not profile:
                return {"status": "success", "summary": "No rules configured", "count": 0}
            
            rules = profile.get("rules", [])
            active_rules = [r for r in rules if r.get("active", True)]
            
            # Group by category
            categories = {}
            for rule in active_rules:
                cat = rule.get("category", "general")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(rule["rule"])
            
            summary_lines = []
            for category, rule_texts in categories.items():
                summary_lines.append(f"[{category.upper()}]")
                for text in rule_texts:
                    summary_lines.append(f"- {text}")
                summary_lines.append("")
            
            return {
                "status": "success",
                "summary": "\n".join(summary_lines),
                "count": len(active_rules),
                "categories": list(categories.keys()),
                "last_updated": profile.get("metadata", {}).get("last_updated")
            }
            
        except Exception as e:
            logger.error(f"Error getting rules summary: {e}")
            return {"status": "error", "error": str(e)}

# Global rules manager instance (singleton)
_rules_manager = None

def get_rules_manager() -> RulesManager:
    """Get global rules manager instance"""
    global _rules_manager
    if _rules_manager is None:
        _rules_manager = RulesManager()
    return _rules_manager

# Global cache for user rules
_cached_user_rules = None

def invalidate_rules_cache():
    """Invalidate rules cache when rules are modified"""
    global _cached_user_rules
    _cached_user_rules = None

# ===== LANGCHAIN TOOLS =====

class AddRuleSchema(BaseModel):
    rule_text: str = Field(description="The rule text to add to the user's preferences")
    category: str = Field(default="general", description="Category for the rule (general, preference, core, etc.)")

class LangchainAddRuleTool(AsyncTool):
    name: str = "add_user_rule"
    description: str = (
        "Add a new rule to the user's persistent preferences notebook. "
        "Rules are how the user configures the agent's behavior and preferences. "
        "Use this when the user wants to establish a permanent preference or instruction."
    )
    args_schema: Type[BaseModel] = AddRuleSchema

    def _run(self, rule_text: str, category: str = "general") -> str:
        try:
            result = get_rules_manager().add_rule(rule_text, category)
            if result["status"] == "success":
                invalidate_rules_cache()  # Invalidate cache when rules change
                return f"✅ Added rule: {rule_text}\nRule ID: {result['rule_id']}"
            else:
                return f"❌ Failed to add rule: {result['error']}"
        except Exception as e:
            return f"❌ Error adding rule: {str(e)}"

class ListRulesSchema(BaseModel):
    category: Optional[str] = Field(default=None, description="Filter rules by category (optional)")

class LangchainListRulesTool(AsyncTool):
    name: str = "list_user_rules"
    description: str = (
        "List all user rules from their preferences notebook. "
        "Shows the persistent rules/preferences that guide the agent's behavior. "
        "This is separate from conversational memories."
    )
    args_schema: Type[BaseModel] = ListRulesSchema

    def _run(self, category: Optional[str] = None) -> str:
        try:
            result = get_rules_manager().list_rules(category)
            if result["status"] == "success":
                rules = result["rules"]
                if not rules:
                    return "📝 No rules found in the notebook."
                
                output = [f"📝 User Rules ({result['count']} total):"]
                output.append("")
                
                for rule in rules:
                    cat = rule.get("category", "general")
                    rule_id = rule.get("id", "unknown")
                    output.append(f"[{rule_id}] [{cat.upper()}] {rule['rule']}")
                    output.append("")
                
                return "\n".join(output)
            else:
                return f"❌ Error listing rules: {result['error']}"
        except Exception as e:
            return f"❌ Error listing rules: {str(e)}"

class UpdateRuleSchema(BaseModel):
    rule_id: str = Field(description="The ID of the rule to update")
    new_text: str = Field(description="The new text for the rule")

class LangchainUpdateRuleTool(AsyncTool):
    name: str = "update_user_rule"
    description: str = (
        "Update an existing user rule in their preferences notebook. "
        "Requires the rule ID and new text."
    )
    args_schema: Type[BaseModel] = UpdateRuleSchema

    def _run(self, rule_id: str, new_text: str) -> str:
        try:
            result = get_rules_manager().update_rule(rule_id, new_text)
            if result["status"] == "success":
                invalidate_rules_cache()  # Invalidate cache when rules change
                return f"✅ Updated rule {rule_id}: {new_text}"
            else:
                return f"❌ Failed to update rule: {result['error']}"
        except Exception as e:
            return f"❌ Error updating rule: {str(e)}"

class DeleteRuleSchema(BaseModel):
    rule_id: str = Field(description="The ID of the rule to delete")

class LangchainDeleteRuleTool(AsyncTool):
    name: str = "delete_user_rule"  
    description: str = (
        "Delete a user rule from their preferences notebook. "
        "Requires the rule ID."
    )
    args_schema: Type[BaseModel] = DeleteRuleSchema

    def _run(self, rule_id: str) -> str:
        try:
            result = get_rules_manager().delete_rule(rule_id)
            if result["status"] == "success":
                invalidate_rules_cache()  # Invalidate cache when rules change
                return f"✅ Deleted rule {rule_id}"
            else:
                return f"❌ Failed to delete rule: {result['error']}"
        except Exception as e:
            return f"❌ Error deleting rule: {str(e)}"

# ===== SLASH COMMANDS =====

def process_rules_slash_command(command: str, args: str) -> str:
    """Process rules-related slash commands"""
    
    if command == "/list_rules":
        try:
            result = get_rules_manager().list_rules()
            if result["status"] == "success":
                rules = result["rules"]
                if not rules:
                    return "📝 No rules found in the notebook."
                
                output = [f"📝 User Rules ({result['count']} total):"]
                output.append("")
                
                for rule in rules:
                    cat = rule.get("category", "general")
                    rule_id = rule.get("id", "unknown")
                    output.append(f"[{rule_id}] [{cat.upper()}] {rule['rule']}")
                    output.append("")
                
                return "\n".join(output)
            else:
                return f"❌ Error listing rules: {result['error']}"
        except Exception as e:
            return f"❌ Error listing rules: {str(e)}"
    
    elif command == "/rule":
        if args:
            try:
                result = get_rules_manager().add_rule(args)
                if result["status"] == "success":
                    invalidate_rules_cache()  # Invalidate cache when rules change
                    return f"✅ Added rule: {args}\nRule ID: {result['rule_id']}"
                else:
                    return f"❌ Failed to add rule: {result['error']}"
            except Exception as e:
                return f"❌ Error adding rule: {str(e)}"
        else:
            return "Usage: /rule <rule text>"
    
    elif command == "/delete_rule":
        if args:
            try:
                result = get_rules_manager().delete_rule(args)
                if result["status"] == "success":
                    invalidate_rules_cache()  # Invalidate cache when rules change
                    return f"✅ Deleted rule {args}"
                else:
                    return f"❌ Failed to delete rule: {result['error']}"
            except Exception as e:
                return f"❌ Error deleting rule: {str(e)}"
        else:
            return "Usage: /delete_rule <rule_id>"
    
    elif command == "/change_rule":
        if args and " " in args:
            parts = args.split(" ", 1)
            rule_id = parts[0]
            new_text = parts[1]
            try:
                result = get_rules_manager().update_rule(rule_id, new_text)
                if result["status"] == "success":
                    invalidate_rules_cache()  # Invalidate cache when rules change
                    return f"✅ Updated rule {rule_id}: {new_text}"
                else:
                    return f"❌ Failed to update rule: {result['error']}"
            except Exception as e:
                return f"❌ Error updating rule: {str(e)}"
        else:
            return "Usage: /change_rule <rule_id> <new text>"
    
    else:
        return f"Unknown rules command '{command}'. Available: /rule, /list_rules, /delete_rule, /change_rule"

# ===== STARTUP FUNCTIONS =====

def load_user_rules() -> str:
    """Load user rules at startup - agent reads the notebook"""
    try:
        result = get_rules_manager().get_rules_summary()
        if result["status"] == "success":
            logger.info(f"Loaded {result['count']} user rules at startup")
            return result["summary"]
        else:
            logger.warning(f"Failed to load user rules: {result['error']}")
            return "No user rules available"
    except Exception as e:
        logger.error(f"Error loading user rules: {e}")
        return "Error loading user rules"

def get_user_rules() -> str:
    """Get formatted user rules for system prompt with caching"""
    global _cached_user_rules
    
    if _cached_user_rules is not None:
        return _cached_user_rules
    
    try:
        result = get_rules_manager().get_rules_summary()
        if result["status"] == "success":
            _cached_user_rules = result["summary"]
            logger.info(f"Cached {result['count']} user rules from rules system")
            return _cached_user_rules
        else:
            logger.warning(f"Failed to load user rules: {result['error']}")
            _cached_user_rules = "No user rules available"
            return _cached_user_rules
    except Exception as e:
        logger.error(f"Error loading user rules: {e}")
        _cached_user_rules = "Error loading user rules"
        return _cached_user_rules