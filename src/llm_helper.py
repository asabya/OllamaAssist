import json
from anthropic import Anthropic
from .tools.registry import ToolRegistry
from .prompts.config import SystemPrompt
from .config import config

client = Anthropic(api_key=config.anthropic_api_key)

def _stream_response(response):
    """Helper function to handle streaming response"""
    collected_content = []
    for chunk in response:
        # Handle message chunks
        if hasattr(chunk, 'delta'):
            # Check if this is a text delta
            if hasattr(chunk.delta, 'text') and chunk.delta.text:
                collected_content.append(chunk.delta.text)
                yield chunk.delta.text
            # Check if this is a tool use delta
            elif hasattr(chunk.delta, 'content'):
                for content in chunk.delta.content:
                    if content.type == 'tool_use':
                        return {
                            'tool_calls': [{
                                'function': {
                                    'name': content.name,
                                    'arguments': json.dumps(content.input)
                                }
                            }]
                        }
                    elif content.type == 'text':
                        collected_content.append(content.text)
                        yield content.text

    # Return collected content if no tool use was found
    return "".join(collected_content)

def chat(messages, model, tools=None, stream=False, additional_instructions=''):
    """
    Chat with Claude using Anthropic's API.
    
    Args:
        messages: List of message dictionaries
        model: Name of the Claude model to use
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

    # Create system prompt with tool instructions and additional instructions
    system_prompt = SystemPrompt(
        additional_instructions=f"{additional_instructions}\n\n{tool_instructions}".strip()
    )
    
    # Format messages for Claude - keep it simple
    formatted_messages = []
    for msg in messages:
        if msg["role"] == "system":
            continue
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
        "system": system_prompt.get_full_prompt(),
        "max_tokens": 4096,
        "temperature": 0
    }

    if stream:
        kwargs["stream"] = True

    if formatted_tools:
        print("Adding tools to request")
        kwargs["tools"] = formatted_tools

    print("-------------------------------- begin")
    print("Request kwargs:", json.dumps(kwargs, indent=2))
    print("-------------------------------- end")
    
    # Make the API call
    try:
        response = client.messages.create(**kwargs)
        print(f"Response type: {type(response)}")
        
        if stream:
            print("Streaming mode:")
            return _stream_response(response)
        else:
            print("Non-streaming mode:")
            content = response.content
            print(f"Content: {content}")

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
                    continue

            # If no tool_use was found, return the text content
            return content[0].text if content else ""
            
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise