#!/usr/bin/env python3
import asyncio
import logging
import os
import json
from datetime import datetime
from typing import List
import uuid

from langchain.agents import AgentExecutor
from langchain.tools import StructuredTool
from langchain.prompts import MessagesPlaceholder, ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.agents.agent import AgentOutputParser
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import SystemMessage

import re

from src.tools.registry import ToolRegistry
from src.prompts.system_prompt import SystemPrompt
from src.llm_factory import LLMFactory
from src.memory_manager import MemoryManager

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
                print(f"\n\nResponse: {response}")
                action = response.get("action", "").strip()
                action_input = response.get("action_input", {})
                
                if action == "Final Answer":
                    return AgentFinish(
                        return_values={"output": action_input if isinstance(action_input, str) else str(action_input)},
                        log=text,
                    )
                
                return AgentAction(
                    tool=action,
                    tool_input=action_input if isinstance(action_input, dict) else {"input": action_input},
                    log=text,
                )
            except json.JSONDecodeError as e:
                print(f"\n\nJSON decode error: {e}")
                pass  # Fall through to natural language handling

        # else check if clean_text is a valid JSON
        try:
            print(f"\n\nClean text: {clean_text}")
            print(f"\n\nClean text type: {type(clean_text)}")
            finish = json.loads(clean_text)
            return AgentFinish(
                return_values={"output": finish},
                log=text,
            )
        except json.JSONDecodeError as e:
            print(f"\n\nJSON decode error: {e}")
            pass  # Fall through to natural language handling
        else:
            return AgentFinish(
                return_values={"output": clean_text},
                log=text,
            )

        # If no valid JSON found, treat as a natural conversation response
        if not any(tool_indicator in clean_text.lower() for tool_indicator in ["action", "tool", "function"]):
            return AgentFinish(
                return_values={"output": clean_text},
                log=text,
            )
            
        # If it looks like a tool usage but not in JSON format, raise error
        raise ValueError(f"Could not parse response. Expected JSON format for tool usage: {text}")

def format_log_to_messages(intermediate_steps):
    """Format intermediate steps into chat messages"""
    messages = []
    for action, observation in intermediate_steps:
        # Combine the tool call and its response into a single assistant message
        messages.append({
            "role": "assistant",
            "content": f"I will use the {action.tool} tool with input: {json.dumps(action.tool_input)}\n\nTool response: {str(observation)}"
        })
    return messages

def load_tools() -> List[StructuredTool]:
    """Load all registered tools"""
    return list(ToolRegistry.get_all_tools().values())

def load_config():
    """Load configuration from mcp_config.json"""
    try:
        with open("mcp_config.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return {"llm": {"provider": "anthropic", "settings": {}}}

def setup_agent(tools: List[StructuredTool], memory_manager: MemoryManager, conversation_id: str):
    print("Setting up agent")
    """Set up the LangChain agent with configured LLM"""
    # Load configuration
    config = load_config()
    llm_config = config.get("llm", {"provider": "anthropic", "settings": {}})
    
    # Initialize the LLM using the factory
    try:
        llm = LLMFactory.create_llm(llm_config)
        print(f"LLM initialized: {llm_config['provider']}")
    except Exception as e:
        logging.error(f"Error initializing LLM: {e}")
        raise
    
    # Build tool-specific instructions
    tool_instructions = "Available Tools:\n\n"
    for tool in tools:
        tool_instructions += f"- {tool.name}: {tool.description}\n"
        # Get tool-specific prompt if available
        if hasattr(tool, 'PROMPT'):
            tool_instructions += f"\nTool-specific instructions:\n{tool.PROMPT}\n"
        # Add parameters info
        if tool.args_schema:
            tool_instructions += "Parameters:\n"
            schema = tool.args_schema.model_json_schema()
            for param_name, param_info in schema.get("properties", {}).items():
                param_type = param_info.get("type", "unknown")
                param_desc = param_info.get("description", "")
                tool_instructions += f"  - {param_name} ({param_type})"
                if param_desc:
                    tool_instructions += f": {param_desc}"
                tool_instructions += "\n"
        tool_instructions += "\n"
    
    # Create system prompt using SystemPrompt class
    system_prompt = SystemPrompt(
        tool_instructions=tool_instructions
    )

    content = [
        {
            "text": system_prompt.get_full_prompt(),
            "type": "text"
        }
    ]
    provider = config.get("provider", "anthropic").lower()
    # special case for anthropic to ensure the system prompt is cached
    if provider == "anthropic":
        content[0]["cache_control"] = {"type": "ephemeral"}
    
    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(
            content=content
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanMessagePromptTemplate.from_template("{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    print("Prompt template created")
    
    # Create the agent
    agent = (
        {
            "input": lambda x: x["input"],
            "agent_scratchpad": lambda x: format_log_to_messages(x["intermediate_steps"]),
            "chat_history": lambda x: memory_manager.get_conversation_history(conversation_id),
        }
        | prompt
        | llm
        | CustomJSONAgentOutputParser()
    )
    
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5
    )
    
    return agent_executor

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
    tools = load_tools()
    memory_manager = MemoryManager()
    conversation_id = str(uuid.uuid4())
    agent_executor = setup_agent(tools, memory_manager, conversation_id)
    
    # Create save directory if it doesn't exist
    save_dir = "conversations"
    os.makedirs(save_dir, exist_ok=True)
    
    print_welcome()
    
    while True:
        try:
            # Get user input
            user_input = input("\n👤 You: ").strip()
            
            # Handle special commands
            if user_input.lower() in ['quit', 'exit']:
                print("👋 Goodbye!")
                break
            elif user_input.lower() == 'tools':
                print_tools(tools)
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
            response = await agent_executor.ainvoke({"input": user_input})
            
            # Add AI response to memory
            await memory_manager.add_ai_message(conversation_id, response["output"])
            
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