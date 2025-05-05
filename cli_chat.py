#!/usr/bin/env python3
import asyncio
import logging
import os
import json
from datetime import datetime
from typing import List
import uuid

from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import StructuredTool
from langchain.prompts import MessagesPlaceholder, ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.agents.agent import AgentOutputParser
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

import re

from src.handlers import UsageTrackingHandler
from src.mcp_client import mcp
from src.prompts.system_prompt import SystemPrompt
from src.llm_factory import LLMFactory
from src.memory_manager import MemoryManager
from src.llm_helper import MCPToolWrapper
from src.database import get_db, Message

# Configure logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class CustomJSONAgentOutputParser(AgentOutputParser):
    """Custom output parser that handles both JSON and natural language responses from Claude"""
    def parse(self, text: str) -> AgentAction | AgentFinish:
        # Clean the text
        clean_text = text.strip()
        # First try to extract JSON from the response
        json_match = re.search(r'```json\s*(.*?)\s*```', clean_text, re.DOTALL)
        if json_match:
            try:
                # Get the JSON content and clean it
                json_str = json_match.group(1).strip()
                # Remove any invalid control characters
                json_str = "".join(char for char in json_str if char.isprintable())
                # Normalize newlines
                json_str = json_str.replace('\r\n', '\n').replace('\r', '\n')
                
                response = json.loads(json_str)
                action = response.get("action", "").strip()
                action_input = response.get("action_input", {})
                
                if action == "Final Answer":
                    return AgentFinish(
                        return_values={"output": action_input.strip() if isinstance(action_input, str) else str(action_input).strip()},
                        log=text,
                    )
                
                return AgentAction(
                    tool=action,
                    tool_input=action_input if isinstance(action_input, dict) else {"input": str(action_input).strip()},
                    log=text,
                )
            except json.JSONDecodeError as e:
                print(f"\n\nJSON decode error: {e}")
                pass  # Fall through to natural language handling

        return AgentFinish(
            return_values={"output": clean_text.strip()},
            log=text,
        )
            
        # If it looks like a tool usage but not in JSON format, raise error
        raise ValueError(f"Could not parse response. Expected JSON format for tool usage: {text}")

def format_log_to_messages(intermediate_steps):
    """Format intermediate steps into chat messages and update database
    
    Args:
        intermediate_steps: List of (action, observation) tuples from agent execution
    """
    messages = []
   
    for action, observation in intermediate_steps:
            # Format the message content
            content = f"I will use the {action.tool} tool with input: {json.dumps(action.tool_input)}\n\nTool response: {str(observation)}".rstrip()
            
            # Add to messages list for return
            messages.append({
                "role": "assistant",
                "content": content
            })
    
    return messages

def load_config():
    """Load configuration from mcp_config.json"""
    try:
        with open("mcp_config.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return {"llm": {"provider": "anthropic", "settings": {}}}

async def setup_agent(memory_manager: MemoryManager, conversation_id: str, context_window: int = 10):
    print("Setting up agent")
    """Set up the LangChain agent with configured LLM
    
    Args:
        memory_manager: Memory manager instance
        conversation_id: ID of the conversation
        context_window: Number of most recent messages to include in context (default: 10)
        
    Returns:
        Tuple of (agent_executor, mcp_client)
    """
    # Load configuration
    config = load_config()
    llm_config = config.get("llm", {"provider": "anthropic", "settings": {}})
    
    # Initialize the LLM using the factory
    llm = LLMFactory.create_llm(llm_config)
    print(f"LLM initialized: {llm_config['provider']}")
    
    # Initialize MCP clients using MultiServerMCPClient
    mcp_servers = config.get("mcpServers", {})
    print(f"MCP servers: {mcp_servers}")
    client = None
    if mcp_servers:
        client = MultiServerMCPClient(mcp_servers)
        await client.__aenter__()
    else:
        print("No MCP servers found in config")
        raise ValueError("No MCP servers configured")
    
    # Create system prompt using SystemPrompt class
    system_prompt = SystemPrompt()

    # Get tools
    tools = client.get_tools()
    tool_names = ", ".join([tool.name for tool in tools])
    tools_description = "\n".join([f"{tool.name}: {tool.description}" for tool in tools])

    content = [
        {
            "text": f"{system_prompt.get_full_prompt()}\n\nTools available:\n{tools_description}\n\nTool names: {tool_names}",
            "type": "text"
        }
    ]
    provider = config.get("provider", "anthropic").lower()
    # special case for anthropic to ensure the system prompt is cached
    if provider == "anthropic":
        content[0]["cache_control"] = {"type": "ephemeral"}
    
    # Create the prompt template with required variables
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(
            content=content
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanMessagePromptTemplate.from_template("{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]).partial(
        tools=tools_description,
        tool_names=tool_names
    )
    print("Prompt template created")

    usage_handler = UsageTrackingHandler(conversation_id)

    
    # Create the agent with windowed chat history
    agent = (
        {
            "input": lambda x: x["input"],
            "agent_scratchpad": lambda x: format_log_to_messages(x["intermediate_steps"]),
            "chat_history": lambda x: memory_manager.get_conversation_history(conversation_id, limit=context_window),
        }
        | prompt
        | llm.with_config({"callbacks": [usage_handler]})
        | CustomJSONAgentOutputParser()
    )
    
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
        return_intermediate_steps=True
    )
    
    return agent_executor, client

def print_welcome():
    """Print welcome message and available commands"""
    print("\n=== Welcome to CLI Chat ===")
    print("Type 'quit' or 'exit' to end the chat")
    print("Type 'tools' to see available tools")
    print("Type 'clear' to start a new chat")
    print("Type 'save' to save the conversation")
    print("Type 'load' to load a saved conversation")

def print_tools(tools: List[StructuredTool]):
    """Display available tools and their details"""
    print("\n=== Available Tools ===")
    for tool in tools:
        print(f"\n🔧 {tool.name}")
        print(f"Description: {tool.description}")
        if tool.args_schema:
            print("Parameters:")
            schema = tool.args_schema.model_json_schema()
            for param_name, param_info in schema.get("properties", {}).items():
                param_type = param_info.get("type", "unknown")
                param_desc = param_info.get("description", "")
                print(f"  - {param_name} ({param_type})")
                if param_desc:
                    print(f"    {param_desc}")

async def chat_loop():
    print("Starting chat loop")
    """Main chat loop using LangChain agent"""
    memory_manager = MemoryManager()
    conversation_id = str(uuid.uuid4())
    agent_executor, client = await setup_agent(memory_manager, conversation_id)
    
    # Create save directory if it doesn't exist
    save_dir = "conversations"
    os.makedirs(save_dir, exist_ok=True)
    
    print_welcome()
    
    try:
        while True:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                # Handle special commands
                if user_input.lower() in ['quit', 'exit']:
                    print("👋 Goodbye!")
                    break
                elif user_input.lower() == 'tools':
                    print("Tools information is not available in this mode")
                    continue
                elif user_input.lower() == 'clear':
                    memory_manager.clear_conversation(conversation_id)
                    print("🧹 Chat history cleared")
                    continue
                elif user_input.lower() == 'save':
                    save_path = os.path.join(save_dir, f"conversation_{conversation_id}.json")
                    memory_manager.save_state(save_path)
                    print(f"💾 Conversation saved to {save_path}")
                    continue
                elif user_input.lower() == 'load':
                    load_path = input("Enter the path to the conversation file: ").strip()
                    if os.path.exists(load_path):
                        memory_manager.load_state(load_path)
                        print("📂 Conversation loaded")
                    else:
                        print("❌ File not found")
                    continue
                elif not user_input:
                    continue
                
                # Add user message to memory
                await memory_manager.add_user_message(conversation_id, user_input)
                
                # Process user input through the agent
                print("\n⏳ Thinking...")
                print("\nMessages being sent to LLM:")
                messages = memory_manager.get_conversation_history(conversation_id)
                for msg in messages:
                    print(f"Role: {msg.type}, Content: {msg.content}")
                
                response = await agent_executor.ainvoke({"input": user_input})
                
                # Add AI response to memory with metadata
                await memory_manager.add_ai_message(
                    conversation_id=conversation_id,
                    content=response["output"].rstrip() if isinstance(response["output"], str) else str(response["output"]).rstrip()
                )
                
                # Print the response
                print("\n🤖 Assistant:", response["output"])
                
            except KeyboardInterrupt:
                print("\n👋 Chat interrupted. Goodbye!")
                break
            except Exception as e:
                import traceback
                error_msg = f"\n❌ Error: {str(e)}\n{traceback.format_exc()}"
                print(error_msg)
                logging.error("Error in chat loop", exc_info=True)
    finally:
        # Properly close the MCP client when we're done
        if client:
            await client.__aexit__(None, None, None)

def main():
    """Main entry point"""
    try:
        asyncio.run(chat_loop())
    except Exception as e:
        import traceback
        error_msg = f"\n❌ Fatal error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        logging.error("Fatal error", exc_info=True)

if __name__ == '__main__':
    main() 