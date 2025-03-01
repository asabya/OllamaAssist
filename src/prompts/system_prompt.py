from dataclasses import dataclass
from typing import Optional
import yaml

@dataclass
class SystemPrompt:
    BASE_PROMPT = """I am an AI assistant and expert in crypto. I have access to a flexible set of tools through the Model Context Protocol (MCP) that I can use when helpful for your tasks.

Currently available tools include:
- File operations and analysis
- Web search and research capabilities
- Crypto analytics via Alpha API:
  • Token search and validation
  • Comprehensive report generation
  • PDF report downloads

For crypto analysis tasks, I can:
- Search for tokens by name/symbol
- Create detailed analysis reports
- Download PDF reports

I am designed to be extensible through MCP plugins, and I will automatically detect and utilize available tools based on the context of our conversation. I will proactively identify when specific tools could be helpful and use them appropriately to assist you.

I will remain aware of my current capabilities and available tools throughout our conversation."""

    def __init__(self, additional_instructions="", character_instructions="", tool_instructions=""):
        self.additional_instructions = additional_instructions
        self.character_instructions = character_instructions
        self.tool_instructions = tool_instructions

    def _process_character_yaml(self, yaml_text):
        """Process character YAML into formatted instructions"""
        if not yaml_text:
            return ""
            
        try:
            # Parse the YAML content
            character_data = yaml.safe_load(yaml_text)
            if not character_data or not isinstance(character_data, dict):
                print("Invalid character YAML format")
                return yaml_text
                
            # Build character instructions
            instructions = []
            
            # Add name and role
            if 'name' in character_data:
                instructions.append(f"# You are {character_data['name']}")
            
            # Add bio points
            if 'bio' in character_data and isinstance(character_data['bio'], list):
                instructions.append("## Bio")
                for point in character_data['bio']:
                    instructions.append(f"- {point}")
            
            # Add lore
            if 'lore' in character_data and isinstance(character_data['lore'], list):
                instructions.append("## Background")
                for point in character_data['lore']:
                    instructions.append(f"- {point}")
            
            # Add knowledge
            if 'knowledge' in character_data and isinstance(character_data['knowledge'], list):
                instructions.append("## Knowledge and Expertise")
                for point in character_data['knowledge']:
                    instructions.append(f"- {point}")
            
            # Add philosophical tenets
            if 'philosophical_tenets' in character_data and isinstance(character_data['philosophical_tenets'], list):
                instructions.append("## Core Beliefs")
                for tenet in character_data['philosophical_tenets']:
                    instructions.append(f"- {tenet}")
            
            # Add style guidelines
            if 'style' in character_data and isinstance(character_data['style'], dict):
                instructions.append("## Communication Style")
                
                # General style
                if 'all' in character_data['style'] and isinstance(character_data['style']['all'], list):
                    instructions.append("General style traits:")
                    for trait in character_data['style']['all']:
                        instructions.append(f"- {trait}")
                
                # Chat style
                if 'chat' in character_data['style'] and isinstance(character_data['style']['chat'], list):
                    instructions.append("Chat style traits:")
                    for trait in character_data['style']['chat']:
                        instructions.append(f"- {trait}")
            
            # Add message examples if available
            if 'message_examples' in character_data and isinstance(character_data['message_examples'], list):
                instructions.append("## Examples of how you respond:")
                for example in character_data['message_examples']:
                    if len(example) >= 2:
                        instructions.append(f"User: {example[0]['user']}")
                        instructions.append(f"Your response: {example[1]['assistant']}")
                        instructions.append("")
            
            # Add adjectives
            if 'adjectives' in character_data and isinstance(character_data['adjectives'], list):
                instructions.append("## Key personality traits:")
                instructions.append(", ".join(character_data['adjectives']))
            
            # Return formatted instructions
            formatted_instructions = "\n".join(instructions)
            print(f"Processed character YAML into {len(formatted_instructions)} characters of instructions")
            return formatted_instructions
            
        except Exception as e:
            print(f"Error processing character YAML: {str(e)}")
            # Fall back to raw YAML if there's an error
            return yaml_text

    def get_full_prompt(self):
        # Include all instructions in the full prompt with proper ordering
        all_instructions = [self.BASE_PROMPT]  # Start with the base prompt
        
        # Process and add character instructions
        if self.character_instructions:
            processed_character = self._process_character_yaml(self.character_instructions)
            all_instructions.append(processed_character)
        
        # Tool instructions come next
        if self.tool_instructions:
            all_instructions.append(self.tool_instructions)
            
        # Additional instructions come last
        if self.additional_instructions:
            all_instructions.append(self.additional_instructions)
            
        # Combine all instructions with proper spacing
        return "\n\n".join([instr for instr in all_instructions if instr]) 