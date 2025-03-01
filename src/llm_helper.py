import json
from anthropic import Anthropic
from .tools.registry import ToolRegistry
from .prompts.system_prompt import SystemPrompt
from .config import config
from typing import Dict, Any, Optional
import yaml
import os

client = Anthropic(api_key=config.anthropic_api_key)

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
            print(f"Loading character YAML from file: {file_path_or_content}")
            with open(file_path_or_content, 'r') as file:
                character_data = yaml.safe_load(file)
        else:
            # If not a file, try to parse as direct YAML content
            print(f"Treating input as direct YAML content ({len(file_path_or_content)} chars)")
            character_data = yaml.safe_load(file_path_or_content)
        
        # Convert the YAML data to a nicely formatted string
        if character_data:
            formatted_yaml = yaml.dump(character_data, default_flow_style=False)
            print(f"Successfully processed YAML into {len(formatted_yaml)} characters")
            return formatted_yaml
        else:
            print("Warning: Empty or invalid YAML content")
            return file_path_or_content
    except Exception as e:
        print(f"Error loading character YAML: {str(e)}")
        # Return the original content if parsing fails
        return file_path_or_content

def _stream_response(response):
    """Helper function to handle streaming response"""
    text_content = ""
    tool_use = None
    json_content = ""
    
    for chunk in response:
        print(f"\n=== Event ===\nType: {chunk.type}")
        print(f"Full chunk: {chunk}")
        
        if chunk.type == "message_start":
            print("Message started")
            continue
            
        elif chunk.type == "content_block_start":
            if chunk.content_block.type == "tool_use":
                print(f"Tool use detected: {chunk.content_block}")
                tool_use = {
                    'tool_calls': [{
                        'function': {
                            'name': chunk.content_block.name,
                            'arguments': None  # Will be filled from json_content
                        }
                    }]
                }
            print(f"Content block started: {chunk.content_block.type}")
            
        elif chunk.type == "content_block_delta":
            if hasattr(chunk.delta, 'text'):
                print(f"Text delta: {chunk.delta.text}")
                text_content += chunk.delta.text
            elif hasattr(chunk.delta, 'type'):
                if chunk.delta.type == 'text_delta':
                    print(f"Text delta: {chunk.delta.text}")
                    text_content += chunk.delta.text
                elif chunk.delta.type == 'input_json_delta':
                    print(f"JSON delta: {chunk.delta.partial_json}")
                    json_content += chunk.delta.partial_json
        
        elif chunk.type == "message_delta":
            print(f"Message delta received: {chunk}")
            # Check if the delta has content attribute
            if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'content'):
                for content_block in chunk.delta.content:
                    if content_block.type == 'text':
                        text_content += content_block.text
                    elif content_block.type == 'tool_use':
                        tool_use = {
                            'tool_calls': [{
                                'function': {
                                    'name': content_block.name,
                                    'arguments': json.dumps(content_block.input)
                                }
                            }]
                        }
            
        elif chunk.type == "message_stop":
            print("Message stopped")
            # If we found a tool use, update its arguments and return
            if tool_use:
                # Only update arguments if they haven't been set yet
                if tool_use['tool_calls'][0]['function']['arguments'] is None:
                    tool_use['tool_calls'][0]['function']['arguments'] = json_content
                return tool_use
            return text_content
            
        elif chunk.type in ["content_block_stop", "ping"]:
            print(f"{chunk.type} received")
            continue

    # Fallback return if message_stop wasn't received
    if tool_use:
        if tool_use['tool_calls'][0]['function']['arguments'] is None:
            tool_use['tool_calls'][0]['function']['arguments'] = json_content
        return tool_use
    return text_content

def chat(messages, model, character_yaml: Optional[str] = None, tools=None, stream=False, additional_instructions=''):
    """
    Chat with Claude using Anthropic's API.
    
    Args:
        messages: List of message dictionaries
        model: Name of the Claude model to use
        character_yaml: Optional path to character YAML file or YAML content string
        tools: Optional list of tool definitions
        stream: Whether to stream the response
        additional_instructions: Additional instructions for system prompt
        
    Returns:
        If stream=True: Generator yielding response chunks
        If stream=False: Complete response message
    """

    # Collect tool prompts if tools are provided
    tool_instructions = ""
    formatted_tools = []
    
    if tools:
        tool_prompts = []
        
        for tool_def in tools:
            function = tool_def.get('function', {})
            tool_name = function.get('name')
            print(f"Processing tool: {tool_name}")
            
            if tool := ToolRegistry.get_tool(tool_name):
                if tool.prompt:
                    tool_prompts.append(f"Tool '{tool_name}' instructions:\n{tool.prompt}")
                
                # Format tools according to API spec
                formatted_tool = {
                    'name': tool_name,
                    'description': function.get('description', ''),
                    'input_schema': {
                        'type': 'object',
                        'properties': {
                            # Use the actual parameters from the tool
                            **tool.parameters
                        },
                        'required': list(tool.parameters.keys())
                    }
                }
                print(f"Formatted tool: {formatted_tool}")
                formatted_tools.append(formatted_tool)
        
        if tool_prompts:
            tool_instructions = "Available Tool Instructions:\n" + "\n\n".join(tool_prompts)

    # Check for system message
    system_content = None
    for msg in messages:
        if msg.get('role') == 'system':
            system_content = msg.get('content', '')
            print(f"Found system message in input: {len(system_content)} characters")
            break
            
    # If system content is provided directly in messages, use it
    # Otherwise, create it from components
    if not system_content:
        # Handle character instructions from YAML
        character_instructions = ""
        if character_yaml:
            # Either load from file or use directly if it's already the content
            if isinstance(character_yaml, str) and character_yaml.endswith(('.yml', '.yaml')):
                character_instructions = load_character_from_yaml(character_yaml)
            else:
                character_instructions = character_yaml
            
        # Create system prompt with character instructions, tool instructions and additional instructions as separate parameters
        system_prompt = SystemPrompt(
            additional_instructions=additional_instructions,
            character_instructions=character_instructions,
            tool_instructions=tool_instructions
        )
        
        system_content = system_prompt.get_full_prompt()
        print(f"Created system content from components: {len(system_content)} characters")
    
    # Format messages for Claude - keep it simple
    formatted_messages = []
    for msg in messages:
        if msg["role"] == "system":
            continue  # Skip system messages as we handle them separately
        elif msg["role"] in ["user", "assistant"]:
            # Check if content exists in the message
            if "content" not in msg:
                print(f"Warning: Message missing content: {msg}")
                continue
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        elif msg["role"] == "function":
            if "content" not in msg or "name" not in msg:
                print(f"Warning: Function message missing content or name: {msg}")
                continue
            formatted_messages.append({
                "role": "assistant",
                "content": f"Function {msg.get('name', 'unknown')} returned: {msg['content']}"
            })

    # Prepare the request
    kwargs = {
        "model": model,
        "messages": formatted_messages,
        "max_tokens": 4096,
        "temperature": 0
    }
    
    # Add system content if we have it
    if system_content:
        kwargs["system"] = system_content
        print(f"Setting system content: {len(system_content)} characters")
        print(f"System preview: {system_content[:200]}...")

    if stream:
        kwargs["stream"] = True

    if formatted_tools:
        print("Adding tools to request")
        kwargs["tools"] = formatted_tools

    print("-------------------------------- begin")
    print("Request kwargs:", json.dumps({k: v if k != "system" else f"[{len(v)} chars]" for k, v in kwargs.items()}, indent=2))
    print("-------------------------------- end")
    
    # Make the API call
    try:
        response = client.messages.create(**kwargs)
        
        if stream:
            return _stream_response(response)
        else:
            content = response.content
            
            # Check for tool_use in content
            for item in content:
                if item.type == 'tool_use':
                    return {
                        'tool_calls': [{
                            'function': {
                                'name': item.name,
                                'arguments': json.dumps(item.input)
                            }
                        }]
                    }
                elif item.type == 'text':
                    return item.text

            # If no tool_use was found, return the text content
            return content[0].text if content else ""
            
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise