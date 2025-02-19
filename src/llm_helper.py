import json
import ollama
from .tools.registry import ToolRegistry
from .prompts.config import SystemPrompt

def chat(messages, model, tools=None, stream=True, additional_instructions=''):
    """
    Chat with the Ollama model.
    
    Args:
        messages: List of message dictionaries
        model: Name of the Ollama model to use
        tools: Optional list of tool definitions
        stream: Whether to stream the response
        additional_instructions: Additional instructions for system prompt
    """
    # Collect tool prompts if tools are provided
    tool_instructions = ""
    if tools:
        tool_prompts = []
        for tool_def in tools:
            tool_name = tool_def.get('function', {}).get('name')
            if tool := ToolRegistry.get_tool(tool_name):
                if tool.prompt:
                    tool_prompts.append(f"Tool '{tool_name}' instructions:\n{tool.prompt}")
        
        if tool_prompts:
            tool_instructions = "Available Tool Instructions:\n" + "\n\n".join(tool_prompts)
    
    # Create system prompt with tool instructions and additional instructions
    system_prompt = SystemPrompt(
        additional_instructions=f"{additional_instructions}\n\n{tool_instructions}".strip()
    )
    
    # Format messages with system prompt
    formatted_messages = [
        {"role": "system", "content": system_prompt.get_full_prompt()}
    ]

    # Add the rest of the messages
    for msg in messages:
        if msg["role"] in ["user", "assistant", "system"]:
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        elif msg["role"] == "function":
            formatted_messages.append({
                "role": "user",
                "content": f"Function {msg.get('name', 'unknown')} returned: {msg['content']}"
            })

    # Prepare the request payload
    payload = {
        "model": model,
        "messages": formatted_messages,
        "stream": stream
    }

    if tools:
        payload["tools"] = tools

    # Make the API call
    response = ollama.chat(**payload)

    return response