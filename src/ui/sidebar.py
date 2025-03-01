import streamlit as st
from src.prompts.system_prompt import SystemPrompt
import os
import yaml
from pathlib import Path

def load_character_yaml(file_path):
    """Load character YAML file and return its contents"""
    try:
        # Try to open the file directly first
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                yaml_content = file.read()
                print(f"Successfully loaded character file from: {file_path}")
                return yaml_content
        
        # If not found, try looking in the project root directory
        project_root = Path(__file__).parent.parent.parent
        absolute_path = project_root / file_path
        
        if os.path.exists(absolute_path):
            with open(absolute_path, 'r') as file:
                yaml_content = file.read()
                print(f"Successfully loaded character file from project root: {absolute_path}")
                return yaml_content
                
        print(f"ERROR: Character file not found at {file_path} or {absolute_path}")
        return ""
    except Exception as e:
        print(f"Error loading character file: {str(e)}")
        return ""

def render_system_prompt_editor():
    """Render system prompt controls in sidebar"""
    with st.sidebar.expander("System Instructions", expanded=False):
        # Show base prompt (read-only)
        st.markdown("#### Base Instructions")
        st.info(SystemPrompt.BASE_PROMPT)
        
        # Character selection section
        st.markdown("#### Character Selection")
        
        # Define available character presets
        character_options = {
            "None": "",
            "Gordon Gekko": "gordon_gekko.yaml"
        }
        
        # Initialize character selection to Gordon Gekko if not already set
        if 'selected_character' not in st.session_state:
            st.session_state['selected_character'] = "Gordon Gekko"
        
        selected_character = st.selectbox(
            "Select a character preset:",
            options=list(character_options.keys()),
            index=list(character_options.keys()).index(st.session_state['selected_character'])
        )
        
        # Store the selected character
        st.session_state['selected_character'] = selected_character
        
        # Load the selected character YAML if any
        character_yaml = ""
        if selected_character != "None" and character_options[selected_character]:
            file_path = character_options[selected_character]
            character_yaml = load_character_yaml(file_path)
            print(f"Loaded character YAML for {selected_character}: {len(character_yaml)} bytes")
            
            # Debug - print the first 100 characters to verify content
            if character_yaml:
                print(f"Character YAML preview: {character_yaml[:100]}...")
            else:
                print(f"WARNING: Empty character YAML for {selected_character}")
        
        # Additional instructions editor
        st.markdown("#### Additional Instructions")
        additional_instructions = st.text_area(
            "Add your specific instructions below:",
            value=st.session_state.get('additional_instructions', ''),
            height=200,
            placeholder="""Examples of additional instructions:

- We are reviewing Python files in directory X
- Help me analyze and improve code quality
- We are building a web application with Flask
- Explain concepts clearly and provide examples
- Use web search for current documentation

Your instructions will be added to the base system prompt."""
        )
        
        # Character instructions editor (custom YAML)
        st.markdown("#### Custom Character Instructions")
        custom_character_yaml = st.text_area(
            "Add character configuration (YAML format):",
            value=character_yaml or st.session_state.get('character_yaml', ''),
            height=200,
            placeholder="""name: Dobby
bio:
  - Dobby is a free assistant who chooses to help because of his enormous heart.
  - Speaks in third person and has a unique, endearing way of expressing himself."""
        )
        
        # Tool instructions (for display only in the UI)
        tool_instructions = st.session_state.get('tool_instructions', '')
        if tool_instructions:
            st.markdown("#### Active Tool Instructions")
            st.info(tool_instructions)
        
        # Store values in session state
        st.session_state['additional_instructions'] = additional_instructions
        st.session_state['character_yaml'] = custom_character_yaml
        
        # Create a SystemPrompt instance with all the instructions
        system_prompt = SystemPrompt(
            additional_instructions=additional_instructions,
            character_instructions=custom_character_yaml,
            tool_instructions=tool_instructions
        )
        
        # Provide feedback on active components
        active_components = []
        if custom_character_yaml:
            active_components.append(f"✓ Character instructions active: {selected_character if selected_character != 'None' else 'Custom'}")
        if tool_instructions:
            active_components.append("✓ Tool instructions active")
        if additional_instructions:
            active_components.append("✓ Additional instructions active")
            
        if active_components:
            st.info("\n".join(active_components))
        
        # Store the complete system prompt in session state
        full_prompt = system_prompt.get_full_prompt()
        st.session_state['system_prompt'] = full_prompt
        
        # Debug output
        print(f"System prompt length: {len(full_prompt)} characters")
        print(f"Character active: {selected_character}")
        print(f"Character length: {len(custom_character_yaml)} characters")