import asyncio
import json
import logging

import streamlit as st

from src.config import config
from src.llm_helper import chat
from src.ui import render_system_prompt_editor
from src.prompts import SystemPrompt
from src.tools.registry import ToolRegistry

# Configure logging
logging.basicConfig(filename='debug.log', level=logging.DEBUG)

def display_tool_details(tools):
    """Display available tools and their details in the sidebar."""
    st.sidebar.markdown("## Available Tools")
    for tool in tools:
        if 'function' in tool:
            func = tool['function']
            with st.sidebar.expander(f"🔧 {func['name']}"):
                st.markdown(f"**Description:**\n{func['description']}")
                st.markdown("**Parameters:**")
                if 'parameters' in func and 'properties' in func['parameters']:
                    for param, details in func['parameters']['properties'].items():
                        param_type = details.get('type', 'unknown') if isinstance(details, dict) else 'unknown'
                        st.markdown(f"- `{param}` ({param_type})")

def setup_sidebar():
    with st.sidebar:
        st.markdown("# Chat Options")
        
        # Add system prompt editor
        render_system_prompt_editor()
        
        # Model selection and tool toggle
        model = None
        use_tools = st.toggle('Use Tools', value=True)
        
        # Display tool details if enabled
        if use_tools:
            tools = load_tools_from_functions()
            display_tool_details(tools)
            
        if st.button('New Chat', key='new_chat', help='Start a new chat'):
            st.session_state.messages = []
            st.rerun()
            
    return model, use_tools

def display_previous_messages():
    for message in st.session_state.messages:
        display_role = message["role"]
        if display_role == "assistant" and "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                function_name = tool_call["function"]["name"]
                function_args = tool_call["function"]["arguments"]
                content = f"**Function Call ({function_name}):**\n```json\n{json.dumps(function_args, indent=2)}\n```"
                with st.chat_message("tool"):
                    st.markdown(content)
        else:
            with st.chat_message(display_role):
                st.markdown(message["content"])

def process_user_input():
    if user_prompt := st.chat_input("What would you like to ask?"):
        with st.chat_message("user"):
            st.markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

def load_tools_from_functions():
    """Load tools from the registry for LLM usage"""
    tools = []
    all_tools = ToolRegistry.get_all_tools()
    print(f"Available tools in registry: {list(all_tools.keys())}")
    
    for name, tool in all_tools.items():
        # Format tools according to API spec
        tool_def = {
            'function': {
                'name': name,
                'description': tool.description,
                'parameters': {
                    'type': 'object',
                    'properties': tool.parameters,
                    'required': list(tool.parameters.keys())
                }
            }
        }
        print(f"Tool definition: {json.dumps(tool_def, indent=2)}")
        tools.append(tool_def)
    return tools

def generate_response(model, use_tools):
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.spinner('Generating response...'):
            try:
                tools = load_tools_from_functions() if use_tools else []
                messages = []
                
                # Get character YAML from session state
                character_yaml = st.session_state.get('character_yaml', '')
                if character_yaml:
                    print(f"\n=== Character YAML Found ===")
                    print(f"Length: {len(character_yaml)} characters")
                    print(f"Preview: {character_yaml[:100]}...")
                
                # Add system prompt if it exists
                system_prompt = st.session_state.get('system_prompt')
                if system_prompt:
                    print(f"\n=== System Prompt Found ===")
                    print(f"Length: {len(system_prompt)} characters")
                    print(f"Preview: {system_prompt[:200]}...")
                    
                    messages.append({
                        "role": "system",
                        "content": system_prompt
                    })
                else:
                    print("\n=== WARNING: No system prompt found! ===")
                
                # Add conversation history
                messages.extend(st.session_state.messages)
                
                # Debug log all messages
                print(f"\n=== Message Count: {len(messages)} ===")
                for i, msg in enumerate(messages):
                    role = msg.get('role', 'unknown')
                    content_preview = msg.get('content', '')[:50] if isinstance(msg.get('content', ''), str) else 'non-text content'
                    print(f"Message {i}: role={role}, content preview: {content_preview}...")
                
                print("\n=== Making initial API call ===")
                response = chat(
                    messages=messages, 
                    model=model or config.DEFAULT_MODEL,
                    character_yaml=character_yaml,
                    tools=tools,
                    stream=True
                )
                
                print("\n=== Checking response type ===")
                print(f"Response type: {type(response)}")
                
                # Handle tool calls or stream response
                if isinstance(response, dict) and 'tool_calls' in response:
                    print("\n=== Tool call detected ===")
                    tool_calls = response['tool_calls']
                    print(f"Tool calls: {json.dumps(tool_calls, indent=2)}")
                    
                    assistant_message = {
                        "role": "assistant",
                        "tool_calls": tool_calls
                    }
                    st.session_state.messages.append(assistant_message)
                    
                    for tool_call in tool_calls:
                        function_name = tool_call['function']['name']
                        function_args = tool_call['function']['arguments']
                        
                        # Debug logging
                        logging.debug(f"Tool call detected: {function_name}")
                        logging.debug(f"Arguments content: {function_args}")
                        
                        with st.chat_message("tool"):
                            content = f"**Function Call ({function_name}):**\n```json\n{function_args}\n```"
                            st.markdown(content)
                        
                        if function_name in ToolRegistry.get_all_tools():
                            tool = ToolRegistry.get_tool(function_name)
                            try:
                                args = json.loads(function_args) if isinstance(function_args, str) else function_args
                                function_response = asyncio.run(tool.execute(**args))
                                
                                tool_message = {
                                    'role': 'function',
                                    'name': function_name,
                                    'content': str(function_response)
                                }
                                st.session_state.messages.append(tool_message)
                                messages.append(tool_message)
                                # with st.chat_message("tool"):
                                #     st.markdown(tool_message['content'])
                            except Exception as e:
                                error_message = f"Error executing {function_name}: {str(e)}"
                                logging.error(f"Error details - Args: {function_args}, Error: {str(e)}")
                                st.error(error_message)
                                logging.error(error_message)

                    # Get final response with streaming
                    final_response = chat(
                        messages=messages,
                        model=model or config.DEFAULT_MODEL,
                        character_yaml=character_yaml,
                        stream=True
                    )
                    
                    with st.chat_message("assistant"):
                        message_placeholder = st.empty()
                        full_response = ""
                        
                        # Handle streaming response
                        print("\n=== Starting stream ===")
                        for chunk in final_response:
                            if chunk:
                                full_response += chunk
                                message_placeholder.markdown(full_response + "▌")
                        
                        print(f"\n=== Final response ===\n{full_response}")
                        # Final update without cursor
                        message_placeholder.markdown(full_response)
                        
                        # Add to message history
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": full_response
                        })
                
                else:
                    print("\n=== Regular response detected ===")
                    # Regular response without tool calls
                    with st.chat_message("assistant"):
                        message_placeholder = st.empty()
                        full_response = ""
                        
                        # Handle streaming response
                        print("\n=== Starting stream ===")
                        for chunk in response:
                            print(f"Chunk received: {chunk}")
                            if chunk:
                                full_response += chunk
                                message_placeholder.markdown(full_response + "▌")
                        
                        print(f"\n=== Final response ===\n{full_response}")
                        # Final update without cursor
                        message_placeholder.markdown(full_response)
                        
                        # Add to message history
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": full_response
                        })

            except Exception as e:
                error_msg = f"Error generating response: {str(e)}"
                st.error(error_msg)
                logging.error(error_msg)
                logging.error(f"Messages: {json.dumps(messages, indent=2)}")
                return

def show_quick_start_buttons():
    """Display quick start buttons for tool discovery."""
    st.markdown("### 🚀 Quick Start")
    st.markdown("Choose an action to begin:")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # Only show buttons if no messages exist
    if not st.session_state.messages:
        with col1:
            if st.button("🔍 Deep Seek AI News"):
                return "Can you help me search the web for projects integrating with Deep Seek AI, as well as other important news about it?"
        with col2:
            if st.button("📂 List Files & Directories"):
                return "Can you list the available directories and the files within them?"
        with col3:
            if st.button("🛠️ Available Tools"):
                return "What tools do you have access to and how can they help me?"
        with col4:
            if st.button("📊 AI Trends & Innovations"):
                return "What are the latest trends and innovations in AI?"
        with col5:
            if st.button("🌎 Global Tech News"):
                return "Can you find the latest global technology news updates?"
    return None

def main():
    st.set_page_config(
        page_title=config.PAGE_TITLE,
        initial_sidebar_state="expanded"
    )
    st.title(config.PAGE_TITLE)
    model, use_tools = setup_sidebar()
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Show quick start buttons and handle their actions
    quick_start_action = show_quick_start_buttons()
    if quick_start_action:
        st.session_state.messages.append({
            "role": "user",
            "content": quick_start_action
        })
        st.rerun()
    
    display_previous_messages()
    process_user_input()
    generate_response(model, use_tools)

if __name__ == '__main__':
    main()