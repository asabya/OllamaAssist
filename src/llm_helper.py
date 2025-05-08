import json
import os
import yaml
import logging
import traceback
import asyncio
from typing import Dict, Any, Optional, List, Union, Tuple, Callable, Type
from pydantic import BaseModel, Field, create_model
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, FunctionMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain.tools import StructuredTool
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.agents import AgentAction, AgentFinish
from langchain.agents import AgentExecutor, create_tool_calling_agent, create_openai_tools_agent
from langchain.agents.output_parsers.tools import ToolAgentAction, ToolsAgentOutputParser
from .prompts.system_prompt import SystemPrompt
from .config import config

class MCPToolWrapper:
    """Wrapper class to convert MCP tools to LangChain StructuredTools"""
    
    def __init__(self, mcp_tool: Any):
        self.mcp_tool = mcp_tool
        self.name = mcp_tool.name
        self.description = mcp_tool.description
        self.args_schema = self._create_args_schema()
        self.tool = StructuredTool.from_function(
            func=self._call_sync,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
        )
    
    def _create_args_schema(self) -> Type[BaseModel]:
        """Create a Pydantic model for the tool's parameters"""
        fields = {}
        
        # Get parameters from args_schema if available
        if hasattr(self.mcp_tool, 'args_schema') and self.mcp_tool.args_schema:
            # If the tool already has a Pydantic schema, use it directly
            return self.mcp_tool.args_schema
        
        # Fall back to parameters if available (for backward compatibility)
        if hasattr(self.mcp_tool, 'parameters'):
            for param_name, param_info in self.mcp_tool.parameters.items():
                # Map JSON schema types to Python types
                type_mapping = {
                    'string': str,
                    'integer': int,
                    'number': float,
                    'boolean': bool,
                    'array': list,
                    'object': dict
                }
                
                param_type = param_info.get('type', 'string')
                python_type = type_mapping.get(param_type, str)
                
                # Add field with description if available
                fields[param_name] = (
                    python_type,
                    Field(description=param_info.get('description', ''))
                )
        
        # Create and return the Pydantic model
        return create_model(f"{self.name}Schema", **fields)
    
    def _call_sync(self, **kwargs) -> Any:
        """Synchronously execute the async tool"""
        return asyncio.run(self.mcp_tool.execute(**kwargs))
    
    def __call__(self, *args, **kwargs) -> Any:
        """Make the wrapper callable"""
        return self.tool(*args, **kwargs)

def create_langchain_tools(tools_config):
    """Convert our tool definitions to LangChain tool format"""
    langchain_tools = []
    
    logging.info("Initializing LangChain tools from config:")
    for tool_def in tools_config:
        function = tool_def.get('function', {})
        tool_name = function.get('name')
        logging.info(f"  - Processing tool: {tool_name}")
        
        if tool := ToolRegistry.get_tool(tool_name):
            # Create a wrapped tool
            wrapper = MCPToolWrapper(mcp_tool=tool)
            langchain_tools.append(wrapper.tool)
            logging.info(f"    ✓ Successfully created wrapper for {tool_name}")
        else:
            logging.warning(f"    ✗ Tool {tool_name} not found in registry")
            
    logging.info(f"Created {len(langchain_tools)} LangChain tools")
    return langchain_tools

def load_character_from_yaml(file_path_or_content: str) -> str:
    """
    Load a character description from a YAML file or direct YAML content.
    
    Args:
        file_path_or_content: Path to the character YAML file or raw YAML content
        
    Returns:
        The content of the YAML file as a formatted string for the prompt
    """
    try:
        # First try to treat it as a file path
        if os.path.exists(file_path_or_content):
            logging.debug(f"Loading character YAML from file: {file_path_or_content}")
            with open(file_path_or_content, 'r') as file:
                character_data = yaml.safe_load(file)
        else:
            # If not a file, try to parse as direct YAML content
            logging.debug(f"Treating input as direct YAML content ({len(file_path_or_content)} chars)")
            character_data = yaml.safe_load(file_path_or_content)
        
        # Convert the YAML data to a nicely formatted string
        if character_data:
            formatted_yaml = yaml.dump(character_data, default_flow_style=False)
            logging.debug(f"Successfully processed YAML into {len(formatted_yaml)} characters")
            return formatted_yaml
        else:
            logging.warning("Empty or invalid YAML content")
            return file_path_or_content
    except Exception as e:
        logging.error(f"Error loading character YAML: {str(e)}")
        # Return the original content if parsing fails
        return file_path_or_content

def safe_copy_message(msg):
    """Create a safe copy of a message object to prevent circular references"""
    if not isinstance(msg, dict):
        return msg
    
    msg_copy = {}
    for k, v in msg.items():
        if k == "tool_calls" and isinstance(v, list):
            # Deep copy tool_calls list
            tool_calls_copy = []
            for tc in v:
                if isinstance(tc, dict):
                    tc_copy = {}
                    for tc_k, tc_v in tc.items():
                        # Handle nested dict in function args
                        if tc_k == "function" and isinstance(tc_v, dict):
                            function_copy = {}
                            for fn_k, fn_v in tc_v.items():
                                if isinstance(fn_v, str) and fn_k == "arguments":
                                    # Ensure arguments is a proper JSON object
                                    try:
                                        if not fn_v.strip().startswith('{'):
                                            # Try to parse as JSON if it's not already JSON formatted
                                            parsed = json.loads(fn_v)
                                            function_copy[fn_k] = json.dumps(parsed)
                                        else:
                                            function_copy[fn_k] = fn_v
                                    except:
                                        function_copy[fn_k] = fn_v
                                else:
                                    function_copy[fn_k] = fn_v
                            tc_copy[tc_k] = function_copy
                        else:
                            tc_copy[tc_k] = tc_v
                    tool_calls_copy.append(tc_copy)
                else:
                    tool_calls_copy.append(tc)
            msg_copy[k] = tool_calls_copy
        else:
            msg_copy[k] = v
    return msg_copy

def build_prompt(tools: Optional[List[Dict]], character_yaml: Optional[str], additional_instructions: str, system_prompt: Optional[str] = None) -> str:
    """Build the system prompt from components."""
    if system_prompt:
        return system_prompt
        
    # Check for character instructions
    character_instructions = ""
    if character_yaml:
        character_instructions = load_character_from_yaml(character_yaml)
        
    # Build tool instructions
    tool_instructions = ""
    if tools:
        tool_instructions = "Available Tools:\n\n"
        for t in tools:
            if 'function' in t:
                func = t['function']
                tool_instructions += f"- {func['name']}: {func['description']}\n"
                if 'parameters' in func:
                    params = func['parameters']
                    if 'properties' in params:
                        tool_instructions += "  Parameters:\n"
                        for param_name, param_info in params['properties'].items():
                            param_type = param_info.get('type', 'any')
                            param_desc = param_info.get('description', '')
                            tool_instructions += f"    - {param_name} ({param_type})"
                            if param_desc:
                                tool_instructions += f": {param_desc}"
                            tool_instructions += "\n"
                tool_instructions += "\n"
        
        # Add specific instruction for tool usage
        tool_instructions += "\nWhen using tools:\n"
        tool_instructions += "1. ALWAYS use the proper tool calling format. NEVER try to implement tool functionality yourself.\n"
        tool_instructions += "2. Before using a tool, first write 'Thought: ' followed by your reasoning.\n"
        tool_instructions += "3. Then write 'Action: ' followed by the tool name.\n"
        tool_instructions += "4. Then write 'Action Input: ' followed by the parameters as a JSON object.\n"
        tool_instructions += "5. After the tool responds, write 'Observation: ' followed by your analysis of the result.\n"
        tool_instructions += "6. Finally, write 'Thought: ' followed by your next steps.\n"
        tool_instructions += "7. NEVER make up tools that aren't listed above.\n\n"
        tool_instructions += "Example:\nThought: I need to search for information about a token\n"
        tool_instructions += "Action: alpha\nAction Input: {\"command\": \"search\", \"query\": \"bitcoin\"}\n"
        tool_instructions += "Observation: The search returned information about Bitcoin\n"
        tool_instructions += "Thought: Now I can analyze this information...\n\n"
        tool_instructions += "Available tool names: " + ", ".join(t['function']['name'] for t in tools if 'function' in t)
    
    # Create and return the full prompt
    system_prompt = SystemPrompt(
        additional_instructions=additional_instructions,
        character_instructions=character_instructions,
        tool_instructions=tool_instructions
    )
    return system_prompt.get_full_prompt()

def convert_messages_to_langchain(messages: List[Dict[str, Any]]) -> List[BaseMessage]:
    """Convert message dictionaries to LangChain message objects."""
    chat_history = []
    for msg in messages:
        if msg["role"] == "system":
            continue  # System message handled separately
        
        if msg["role"] == "user":
            if "content" in msg and msg["content"]:
                chat_history.append(HumanMessage(content=msg["content"]))
        
        elif msg["role"] == "assistant":
            if "content" in msg:
                # Check for tool calls in the message
                if "tool_calls" in msg:
                    message = AIMessage(
                        content=msg["content"],
                        additional_kwargs={"tool_calls": msg["tool_calls"]}
                    )
                else:
                    message = AIMessage(content=msg["content"])
                chat_history.append(message)
        
        elif msg["role"] == "function":
            if "content" in msg and "name" in msg:
                chat_history.append(FunctionMessage(content=msg["content"], name=msg["name"]))
    
    return chat_history

def prepare_tools(tools: Optional[List[Dict]]) -> List[StructuredTool]:
    """Convert tool configurations to LangChain StructuredTools."""
    langchain_tools = []
    if tools:
        logging.info("Preparing LangChain tools:")
        for tool in tools:
            if 'function' in tool:
                func = tool['function']
                tool_name = func['name']
                logging.info(f"  - Processing tool: {tool_name}")
                tool_obj = ToolRegistry.get_tool(tool_name)
                if tool_obj:
                    # Create a wrapped tool
                    wrapper = MCPToolWrapper(tool_obj)
                    langchain_tools.append(wrapper.tool)
                    logging.info(f"    ✓ Successfully created wrapper for {tool_name}")
                else:
                    logging.warning(f"    ✗ Tool {tool_name} not found in registry")
    
    logging.info(f"Total tools prepared: {len(langchain_tools)}")
    if langchain_tools:
        logging.info("Available tools:")
        for tool in langchain_tools:
            logging.info(f"  - {tool.name}: {tool.description}")
    
    return langchain_tools

async def run_agent(
    agent_executor: AgentExecutor,
    input_text: str,
    chat_history: List[BaseMessage],
    callback_on_tool_start: Optional[Callable] = None,
    callback_on_tool_end: Optional[Callable] = None
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Run the agent and process its results."""
    executed_tools = []
    
    # Execute the agent
    result = await agent_executor.ainvoke({
        "input": input_text,
        "chat_history": chat_history
    })
    
    logging.debug(f"Agent execution completed: {result}")
    
    # Process any tool executions
    if "intermediate_steps" in result:
        for action, output in result["intermediate_steps"]:
            if isinstance(action, AgentAction):
                # Record executed tools
                executed_tools.append({
                    'name': action.tool,
                    'args': action.tool_input,
                    'response': output
                })
                
                # Call callbacks if provided
                if callback_on_tool_start:
                    callback_on_tool_start(action.tool, action.tool_input)
                if callback_on_tool_end:
                    callback_on_tool_end(action.tool, output)
    
    # Return the agent's response and executed tools
    return {
        "role": "assistant",
        "content": result.get("output", "I couldn't generate a response.")
    }, executed_tools

async def chat(
    messages: List[Dict[str, Any]], 
    model: str, 
    tools: Optional[List[Dict]] = None,
    character_yaml: Optional[str] = None,
    system_prompt: Optional[str] = None,
    additional_instructions: str = '',
    callback_on_tool_start: Optional[Callable] = None,
    callback_on_tool_end: Optional[Callable] = None
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Chat with Claude using Anthropic's API via LangChain's agent framework.
    
    Args:
        messages: List of message dictionaries
        model: Name of the Claude model to use
        tools: List of tools in Claude's tool format
        character_yaml: Optional path to character YAML file or YAML content string
        system_prompt: Optional explicit system prompt to use instead of generating one
        additional_instructions: Additional instructions for system prompt
        callback_on_tool_start: Optional callback when tool execution starts
        callback_on_tool_end: Optional callback when tool execution completes
        
    Returns:
        Tuple with (final_response_message, executed_tools)
        - final_response_message: Dict with role="assistant" and the response content
        - executed_tools: List of tools that were executed with their inputs and outputs
    """
    executed_tools = []
    logging.info(f"Chat function called with {len(messages)} messages, model={model}, tools={bool(tools)}")
    if tools:
        logging.info(f"Received {len(tools)} tool configurations:")
        for tool in tools:
            if 'function' in tool:
                logging.info(f"  - Tool config: {tool['function'].get('name')}")
    
    try:
        # Limit message history to prevent recursion
        if len(messages) > 40:
            logging.warning("Message history too long. Truncating to prevent issues.")
            system_msgs = [msg for msg in messages if msg.get('role') == 'system']
            # Filter out messages with unresolved tool calls to prevent confusion
            recent_msgs = [msg for msg in messages[-30:] if not (
                msg.get('role') == 'assistant' and 
                'tool_calls' in msg and 
                not any(m.get('role') == 'function' for m in messages[messages.index(msg)+1:])
            )]
            if system_msgs and recent_msgs[0].get('role') != 'system':
                messages = system_msgs + recent_msgs
            else:
                messages = recent_msgs
                
        # Create safe copies of all messages
        messages = [safe_copy_message(msg) for msg in messages]
        
        # Initialize the ChatAnthropic model
        anthropic_api_key = config.anthropic_api_key
        if not anthropic_api_key:
            logging.error("No Anthropic API key found")
            return {"role": "assistant", "content": "Error: No Anthropic API key configured"}, []
        
        llm = ChatAnthropic(
            model=model,
            anthropic_api_key=anthropic_api_key,
            temperature=0
        )
        logging.info(f"Initialized ChatAnthropic with model={model}")

        # Build the system prompt
        system_content = build_prompt(tools, character_yaml, additional_instructions, system_prompt)
        logging.debug("System content prepared for prompt")
        logging.info("System Prompt Content:")
        logging.info("-" * 80)
        logging.info(system_content)
        logging.info("-" * 80)

        # Convert messages to LangChain format
        chat_history = convert_messages_to_langchain(messages)
        
        # Configure prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_content),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Prepare tools if provided
        langchain_tools = prepare_tools(tools)
        logging.info(f"Prepared {len(langchain_tools)} LangChain tools")
        if langchain_tools:
            logging.info("Tools being passed to agent:")
            for tool in langchain_tools:
                logging.info(f"  - {tool.name}: {tool.description}")
                logging.info(f"    Schema: {tool.args_schema.schema() if hasattr(tool, 'args_schema') else 'No schema'}")
        
        # Extract the last user message for input
        last_user_message = "How can I help you?"
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_message = msg["content"]
                break
        
        # Setup LangChain agent with tool calling if tools are available
        if langchain_tools:
            logging.info(f"Setting up tool calling agent with {len(langchain_tools)} tools")
            try:
                # Create the agent using create_tool_calling_agent
                agent = create_tool_calling_agent(
                    llm=llm,
                    tools=langchain_tools,
                    prompt=prompt
                )
                logging.info("Agent created successfully")
                logging.info(f"Agent tools: {[tool.name for tool in agent.tools]}")
                
                # Create the agent executor
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=langchain_tools,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=3,
                    early_stopping_method="force",
                    return_intermediate_steps=True
                )
                logging.info("Agent executor created successfully")
                logging.info(f"Executor tools: {[tool.name for tool in agent_executor.tools]}")
                
                return await run_agent(
                    agent_executor,
                    last_user_message,
                    chat_history,
                    callback_on_tool_start,
                    callback_on_tool_end
                )
                
            except Exception as e:
                error_msg = f"Error during agent creation/execution: {str(e)}"
                logging.error(error_msg)
                logging.error(traceback.format_exc())
                return {
                    "role": "assistant", 
                    "content": f"I encountered an error while setting up the tools: {str(e)}"
                }, executed_tools
        
        # No tools or tool setup failed, use LLM directly
        chat_history_with_input = chat_history.copy()
        chat_history_with_input.append(HumanMessage(content=last_user_message))
        
        # Prepend system message
        full_messages = [SystemMessage(content=system_content)] + chat_history_with_input
        
        # Invoke the LLM
        response = await llm.ainvoke(full_messages)
        
        # Return the response
        return {
            "role": "assistant",
            "content": response.content
        }, []
    
    except Exception as e:
        error_msg = f"Error in chat function: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        
        return {
            "role": "assistant",
            "content": f"I encountered an error while processing your request: {str(e)}"
        }, executed_tools