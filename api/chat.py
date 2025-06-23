#!/usr/bin/env python3
"""
Chat API endpoint for Advanced MCP Server
Main chat_proxy endpoint and related streaming functions
"""

import json
import logging
import asyncio
import time
from typing import List, Dict, Any, AsyncGenerator

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub

from core.orchestrator import (
    get_tool_recommendations,
    get_workflow_recommendations,
    should_use_naming_conventions,
    should_use_refactor_workflow,
    should_use_test_workflow
)

from config import (
    OLLAMA_API_BASE,
    OLLAMA_OPENAI_BASE,
    DEFAULT_MODEL,
    DIRECT_OLLAMA_TIMEOUT,
    LANGCHAIN_AGENT_TIMEOUT,
    DEFAULT_SLASH_COMMANDS
)

# Import all tools
from tools import (
    LangchainMemoryContextTool,
    LangchainMemorySaveTool,
    LangchainMemoryRuleTool,
    LangchainMemoryStatsTool,
    LangchainMemoryCorrectionTool,
    MultiLanguageSandboxTool,
    SandboxStatsTool,
    LangchainWebSearchTool,
    LangchainGitStatusTool,
    LangchainGitDiffTool,
    LangchainGitCommitTool,
    LangchainGitBranchTool,
    LangchainGitLogTool,
    LangchainAutoLinterTool,
    LangchainGitHubRepoSearchTool,
    LangchainGitHubIssuesTool,
    LangchainGitHubReleasesTool,
    LangchainRepoExploreTool,
    LangchainDependencyAnalysisTool,
    LangchainCodeMetricsTool,
    LangchainPackageSearchTool,
    LangchainBuildCommandTool,
    LangchainDateTimeTool,
    LangchainFlutterDocTool,
    LangchainCodeSearchTool
)

logger = logging.getLogger(__name__)

router = APIRouter()

def _build_master_prompt_with_memory(base_prompt, user_message: str):
    """
    Master Prompt Template: Integrates Memory System (Tier 1 + Tier 2) with base prompt
    Copied from working advanced_mcp_server.py
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
            from langchain.prompts import PromptTemplate
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

# ===== SLASH COMMAND PROCESSING =====

def process_slash_command(command: str, args: str, custom_commands: Dict[str, Any]) -> str:
    """Process slash commands and return appropriate response"""
    
    # Check custom commands first
    if command in custom_commands:
        custom_cmd = custom_commands[command]
        return f"Executing custom command: {custom_cmd['description']}"
    
    # Check built-in commands
    if command not in DEFAULT_SLASH_COMMANDS:
        available_commands = list(DEFAULT_SLASH_COMMANDS.keys()) + list(custom_commands.keys())
        return f"Unknown command '{command}'. Available commands: {', '.join(available_commands)}"
    
    cmd_config = DEFAULT_SLASH_COMMANDS[command]
    action = cmd_config["action"]
    
    # Route to appropriate tool based on action
    try:
        # Import memory functions from knowledge.py
        from tools.knowledge import (
            mcp_add_permanent_rule, mcp_save_interaction, mcp_get_context,
            mcp_get_memory_stats, mcp_add_correction, mcp_list_rules,
            mcp_delete_rule, mcp_update_rule
        )
        
        if action == "save_rule":
            result = mcp_add_permanent_rule(args, "preference")
            if result.get("status") == "success":
                return f"✅ Rule added: {args}"
            else:
                return f"❌ Failed to add rule: {result.get('error', 'Unknown error')}"
                
        elif action == "save_memory":
            # Convert summary to message format
            messages = [{"role": "user", "content": f"Remember: {args}"}]
            result = mcp_save_interaction(messages, {"type": "user_memory"})
            if result.get("status") == "success":
                return f"✅ Information saved: {args}"
            else:
                return f"❌ Failed to save: {result.get('error', 'Unknown error')}"
                
        elif action == "get_memory":
            result = mcp_get_context(args, include_long_term=True)
            if result.get("status") == "success":
                context = result.get("context", {})
                response = f"📋 Memory search results for '{args}':\n"
                response += f"• {len(context.get('short_term', []))} recent interactions\n"
                response += f"• {len(context.get('profile', {}).get('rules', []))} rules\n"
                response += f"• {len(context.get('long_term', []))} semantic matches"
                return response
            else:
                return f"❌ Memory search failed: {result.get('error', 'Unknown error')}"
                
        elif action == "get_stats":
            result = mcp_get_memory_stats()
            if result.get("status") == "success":
                stats = result.get("stats", {})
                return f"📊 Memory Statistics:\n• Redis: {stats.get('redis', {}).get('status', 'unknown')}\n• MongoDB: {stats.get('mongodb', {}).get('status', 'unknown')}\n• ChromaDB: {stats.get('chromadb', {}).get('status', 'unknown')}"
            else:
                return f"❌ Stats failed: {result.get('error', 'Unknown error')}"
                
        elif action == "correct" or action == "fix":
            result = mcp_add_correction(args)
            if result.get("status") == "success":
                return f"✅ Correction saved: {args}"
            else:
                return f"❌ Failed to save correction: {result.get('error', 'Unknown error')}"
                
        elif action == "list_rules":
            result = mcp_list_rules(args if args.strip() else None)
            if result.get("status") == "success":
                rules = result.get("rules", [])
                if not rules:
                    return f"📋 No rules found{' matching \"' + args + '\"' if args.strip() else ''}"
                response = f"📋 Found {len(rules)} rule(s):\n"
                for rule in rules[:10]:  # Show max 10 rules
                    rule_id = rule.get("id", "unknown")
                    rule_text = rule.get("rule", "")
                    category = rule.get("category", "general")
                    response += f"• [{rule_id}] ({category}): {rule_text}\n"
                if len(rules) > 10:
                    response += f"... and {len(rules) - 10} more rules"
                return response
            else:
                return f"❌ Failed to list rules: {result.get('error', 'Unknown error')}"
                
        elif action == "delete_rule":
            if not args.strip():
                return "❌ Please provide a rule ID to delete. Usage: /delete_rule <rule_id>"
            result = mcp_delete_rule(args.strip())
            if result.get("status") == "success":
                return f"✅ Rule {args.strip()} deleted successfully"
            else:
                return f"❌ Failed to delete rule: {result.get('error', 'Unknown error')}"
                
        elif action == "change_rule":
            parts = args.split(' ', 1)
            if len(parts) < 2:
                return "❌ Please provide rule ID and new text. Usage: /change_rule <rule_id> <new_text>"
            rule_id, new_text = parts
            result = mcp_update_rule(rule_id.strip(), new_text.strip())
            if result.get("status") == "success":
                return f"✅ Rule {rule_id} updated successfully"
            else:
                return f"❌ Failed to update rule: {result.get('error', 'Unknown error')}"
        elif action == "list_commands":
            category = args.strip().lower() if args else None
            if category:
                commands = {k: v for k, v in DEFAULT_SLASH_COMMANDS.items() if v["category"] == category}
            else:
                commands = DEFAULT_SLASH_COMMANDS
            
            result = f"Available {category + ' ' if category else ''}commands:\n"
            for cmd, info in commands.items():
                result += f"{cmd}: {info['description']}\n"
            return result
        elif action == "command_help":
            if args in DEFAULT_SLASH_COMMANDS:
                cmd_info = DEFAULT_SLASH_COMMANDS[args]
                return f"{args}: {cmd_info['description']}\nUsage: {cmd_info['usage']}\nExample: {cmd_info['example']}"
            else:
                return f"No help available for '{args}'"
        elif action == "git_status":
            tool = LangchainGitStatusTool()
            return tool._run()
        elif action == "repo_analysis":
            tool = LangchainRepoExploreTool() 
            analysis_type = args.strip() if args else "structure"
            return tool._run(path=".", analysis_type=analysis_type)
        elif action == "build_command":
            tool = LangchainBuildCommandTool()
            command_type = args.strip() if args else "detect"
            return tool._run(command=command_type)
        elif action == "package_search":
            if not args:
                return "Usage: /package <ecosystem> <query>\nExample: /package npm react-router"
            parts = args.split(' ', 1)
            if len(parts) < 2:
                return "Usage: /package <ecosystem> <query>\nExample: /package npm react-router"
            ecosystem, query = parts
            tool = LangchainPackageSearchTool()
            return tool._run(ecosystem=ecosystem, query=query)
        else:
            return f"Command '{command}' recognized but not yet implemented (action: {action})"
            
    except Exception as e:
        logger.error(f"Error executing slash command {command}: {e}")
        return f"Error executing command '{command}': {str(e)}"

# ===== DIRECT OLLAMA STREAMING =====

async def stream_ollama_direct(messages: List[Dict], model_name: str) -> AsyncGenerator[str, None]:
    """Stream response directly from Ollama without tools"""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=DIRECT_OLLAMA_TIMEOUT) as client:
            # Format for Ollama chat API
            ollama_payload = {
                "model": model_name,
                "messages": messages,
                "stream": True
            }
            
            url = f"{OLLAMA_OPENAI_BASE.rstrip('/v1')}/api/chat"
            
            async with client.stream("POST", url, json=ollama_payload) as response:
                if response.status_code != 200:
                    error_msg = f"Ollama API error: {response.status_code}"
                    logger.error(error_msg)
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    return
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            if 'message' in chunk and 'content' in chunk['message']:
                                content = chunk['message']['content']
                                if content:
                                    # Send OpenAI-compatible streaming format
                                    stream_chunk = {
                                        "id": "chatcmpl-ollama",
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": model_name,
                                        "choices": [{
                                            "index": 0,
                                            "delta": {"content": content},
                                            "finish_reason": None
                                        }]
                                    }
                                    yield f"data: {json.dumps(stream_chunk)}\n\n"
                            
                            # Check if done
                            if chunk.get('done', False):
                                # Send final chunk with finish_reason
                                final_chunk = {
                                    "id": "chatcmpl-ollama",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model_name,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield f"data: {json.dumps(final_chunk)}\n\n"
                                yield "data: [DONE]\n\n"
                                break
                        except json.JSONDecodeError:
                            continue
                            
    except Exception as e:
        logger.error(f"Direct Ollama streaming error: {e}")
        yield f"data: {json.dumps({'error': f'Streaming error: {str(e)}'})}\n\n"

# ===== MAIN CHAT ENDPOINT =====

@router.post("/api/chat")
async def chat_proxy(request: Request):
    """Main chat endpoint that routes requests to appropriate handlers"""
    try:
        request_body = await request.json()
        requested_model_name = request_body.get('model', DEFAULT_MODEL) 
        messages = request_body.get('messages', []) 
        stream = request_body.get("stream", True)
        
        if not messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
        # Get the latest user message (matching old format)
        user_message = ""
        if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "user":
            content = messages[-1].get("content")
            if isinstance(content, str): 
                user_message = content
        
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")
        
        logger.info(f"Chat Request: Model='{requested_model_name}', Msgs={len(messages)}")
        
        # Check for slash commands
        if user_message.strip().startswith('/'):
            parts = user_message.strip().split(' ', 1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            
            # Get custom commands from memory
            try:
                memory_tool = LangchainMemoryContextTool()
                custom_commands_result = memory_tool._run("custom_slash_commands")
                custom_commands = json.loads(custom_commands_result) if custom_commands_result else {}
            except:
                custom_commands = {}
            
            # Process slash command
            response_text = process_slash_command(command, args, custom_commands)
            
            if stream:
                async def command_stream():
                    # Send command response as streaming chunks
                    stream_chunk = {
                        "id": "chatcmpl-command",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": response_text},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(stream_chunk)}\n\n"
                    
                    # Send final chunk
                    final_chunk = {
                        "id": "chatcmpl-command",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }]
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                
                return StreamingResponse(
                    command_stream(), 
                    media_type="text/event-stream",
                    headers={"Content-Type": "text/event-stream"}
                )
            else:
                return JSONResponse({
                    "message": {"role": "assistant", "content": response_text}
                })
        
        # Get tool and workflow recommendations
        tool_recommendations = get_tool_recommendations(user_message)
        workflow_recommendations = get_workflow_recommendations(user_message)
        
        # Check if we need to use tools/agent
        tools_needed = any(tool_recommendations.values()) or any(workflow_recommendations.values())
        logger.info(f"🔍 Debug: tools_needed={tools_needed}, tool_recommendations={tool_recommendations}")
        logger.info(f"🔍 Debug: user_message='{user_message}', client_type=Continue/OpenWebUI")
        
        if not tools_needed:
            # Use direct Ollama path like working version
            logger.info(f"💬 Chat Path: No special tools needed. Using Direct Ollama path with model '{requested_model_name}'.")
            return StreamingResponse(
                stream_ollama_direct(messages, requested_model_name),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*", "X-Accel-Buffering": "no"}
            )
        
        if tools_needed:
            logger.info(f"💡 Tool recommendations: {tool_recommendations}")
            logger.info(f"🔄 Workflow recommendations: {workflow_recommendations}")
            
            # Initialize Langchain agent with tools
            try:
                # Set up LLM
                llm = ChatOllama(
                    model=requested_model_name,
                    base_url=OLLAMA_API_BASE,
                    temperature=0.1
                )
                
                # Build tool list conditionally (like working version)
                tools = []
                
                if tool_recommendations.get("memory"):
                    tools.extend([
                        LangchainMemoryContextTool(),
                        LangchainMemorySaveTool(),
                        LangchainMemoryRuleTool(),
                        LangchainMemoryStatsTool(),
                        LangchainMemoryCorrectionTool()
                    ])
                    logger.info("🧠 Added memory tools to agent")
                
                if tool_recommendations.get("rag"):
                    tools.extend([
                        LangchainFlutterDocTool(),
                        LangchainCodeSearchTool()
                    ])
                    logger.info("📚 Added RAG tools to agent")
                
                if tool_recommendations.get("web_search"):
                    tools.append(LangchainWebSearchTool())
                    logger.info("🔍 Added web search tool to agent")
                
                if tool_recommendations.get("git"):
                    tools.extend([
                        LangchainGitStatusTool(),
                        LangchainGitDiffTool(),
                        LangchainGitCommitTool(),
                        LangchainGitBranchTool(),
                        LangchainGitLogTool()
                    ])
                    logger.info("🔧 Added Git tools to agent")
                
                if tool_recommendations.get("github"):
                    tools.extend([
                        LangchainGitHubRepoSearchTool(),
                        LangchainGitHubIssuesTool(),
                        LangchainGitHubReleasesTool()
                    ])
                    logger.info("🐙 Added GitHub tools to agent")
                
                if tool_recommendations.get("repo_analysis"):
                    tools.extend([
                        LangchainRepoExploreTool(),
                        LangchainDependencyAnalysisTool(),
                        LangchainCodeMetricsTool()
                    ])
                    logger.info("📊 Added repository analysis tools to agent")
                
                if tool_recommendations.get("dev_workflow"):
                    tools.extend([
                        LangchainPackageSearchTool(),
                        LangchainBuildCommandTool(),
                        LangchainDateTimeTool()
                    ])
                    logger.info("🔧 Added development workflow tools to agent")
                
                if tool_recommendations.get("auto_linter"):
                    tools.append(LangchainAutoLinterTool())
                    logger.info("🔍 Added auto-linter tool to agent")
                
                if tool_recommendations.get("sandbox"):
                    tools.extend([
                        MultiLanguageSandboxTool(),
                        SandboxStatsTool()
                    ])
                    logger.info("🔒 Added sandbox tools to agent")
                
                # Get base ReAct prompt 
                base_prompt = hub.pull("hwchase17/react")
                
                # Get memory context for system message instead of prompt enhancement
                memory_context = ""
                try:
                    from tools.knowledge import mcp_get_context
                    memory_result = mcp_get_context(user_message, include_long_term=False)
                    if memory_result.get("status") == "success":
                        context = memory_result.get("context", {})
                        profile = context.get("profile", {})
                        rules = profile.get("rules", [])
                        if rules:
                            memory_context = "IMPORTANT IDENTITY RULES:\n"
                            for rule in rules[:10]:  # Top 10 rules
                                rule_text = rule.get("rule", str(rule))
                                memory_context += f"- {rule_text}\n"
                            memory_context += "\nYou MUST follow these rules, especially regarding your identity and name.\n"
                except Exception as e:
                    logger.error(f"Memory context retrieval error: {e}")
                
                # Create ReAct agent with system message instead of prompt modification
                llm_with_system = llm
                if memory_context:
                    # Prepend memory context to LLM calls
                    llm_with_system = llm.bind(system=memory_context)
                
                # Create agent with tools using system-enhanced LLM
                agent = create_react_agent(llm_with_system, tools, base_prompt)
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=tools,
                    verbose=True,
                    return_intermediate_steps=True,
                    handle_parsing_errors="Check messages and try to recover, or output the parsing error directly to the user."
                )
                
                # Execute agent asynchronously (like working version)
                lc_messages_history = []
                for msg in messages:
                    if msg["role"] == "user":
                        lc_messages_history.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        lc_messages_history.append(AIMessage(content=msg["content"]))
                
                agent_input_data = {"input": user_message, "chat_history": lc_messages_history}
                
                # Execute agent completely FIRST (like working version)
                logger.info(f"🤖 Invoking ReAct agent for query: '{user_message}'")
                result = await agent_executor.ainvoke(agent_input_data)
                agent_response = result.get("output", "[Agent did not return a final answer.]")
                
                # Include full tool execution details for debugging tools like sandbox
                intermediate_steps = result.get("intermediate_steps", [])
                if intermediate_steps:
                    tool_details = "\n\n**Tool Execution Details:**\n"
                    for i, (action, observation) in enumerate(intermediate_steps):
                        tool_name = getattr(action, 'tool', 'unknown_tool')
                        tool_input = getattr(action, 'tool_input', 'unknown_input')
                        tool_details += f"\n🔧 **{tool_name}** execution:\n"
                        tool_details += f"Input: {tool_input}\n"
                        tool_details += f"Full Output: {observation}\n"
                    agent_response += tool_details
                
                logger.info(f"🤖 Agent completed. Response length: {len(agent_response)}")
                
                if stream:
                    async def agent_stream():
                        # Stream the final answer word-by-word like working version
                        for word in agent_response.split():
                            stream_chunk = {
                                "id": "chatcmpl-agent",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": requested_model_name,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": word + " "},
                                    "finish_reason": None
                                }]
                            }
                            yield f"data: {json.dumps(stream_chunk)}\n\n"
                            await asyncio.sleep(0.05)
                        
                        # Send final chunk
                        final_chunk = {
                            "id": "chatcmpl-agent",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": requested_model_name,
                            "choices": [{
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop"
                            }]
                        }
                        yield f"data: {json.dumps(final_chunk)}\n\n"
                        yield "data: [DONE]\n\n"
                    return StreamingResponse(
                        agent_stream(), 
                        media_type="text/event-stream",
                        headers={"Content-Type": "text/event-stream"}
                    )
                else:
                    return JSONResponse({
                        "id": "chatcmpl-agent",
                        "object": "chat.completion", 
                        "created": int(time.time()),
                        "model": requested_model_name,
                        "choices": [{
                            "index": 0,
                            "message": {"role": "assistant", "content": agent_response},
                            "finish_reason": "stop"
                        }],
                        "usage": {
                            "prompt_tokens": len(user_message) // 4,
                            "completion_tokens": len(agent_response) // 4,
                            "total_tokens": (len(user_message) + len(agent_response)) // 4
                        }
                    })
                    
            except Exception as e:
                logger.error(f"Agent execution error: {e}")
                raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# ===== ADDITIONAL ENDPOINTS =====

@router.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint"""
    return {
        "data": [
            {
                "id": DEFAULT_MODEL,
                "object": "model",
                "created": 1677610602,
                "owned_by": "Advanced MCP Server"
            }
        ]
    }

@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint"""
    # Delegate to the main chat endpoint
    return await chat_proxy(request)

# --- START: Added Legacy Endpoint ---
@router.post("/v1/completions")
async def legacy_completions(request: Request):
    """
    OpenAI-compatible legacy completions endpoint.
    This acts as an alias for the chat completions endpoint.
    """
    # Delegate to the main chat endpoint
    return await chat_proxy(request)
# --- END: Added Legacy Endpoint ---

@router.get("/api/context-status") 
async def context_status():
    """Get current context configuration and status"""
    # This would show context limits, usage, etc.
    # For now, return basic info
    return {
        "model": DEFAULT_MODEL,
        "context_limit": "Auto-detected from Ollama",
        "compaction_enabled": True,
        "status": "operational"
    }
