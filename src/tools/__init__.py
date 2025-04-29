from typing import ClassVar, Type, Optional
from pydantic import BaseModel, Field, ConfigDict
import logging
from pathlib import Path
import json
from langchain.tools import StructuredTool

from .registry import ToolRegistry
from .brave import BraveSearchTool
from .filesystem import FileSystemTool as FilesystemTool
from .alpha import AlphaApiTool, AlphaToolInput
from ..config import config

# Initialize logging
logger = logging.getLogger(__name__)

class HelpToolInput(BaseModel):
    """Input schema for Help tool"""
    tool_name: str = Field(
        default="",
        description="Optional name of the tool to get help for. Leave empty to get help for all tools."
    )

# Define a help tool that shows how to use other tools
class HelpTool(StructuredTool):
    """Help tool for getting information about available tools"""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Tool configuration
    name: str = "help"
    description: str = "Get help on how to use available tools. Use this if you're not sure how to use a specific tool."
    args_schema: Type[BaseModel] = HelpToolInput
    
    async def _arun(self, tool_name: str = "") -> str:
        """Get help on tool usage"""
        all_tools = ToolRegistry.get_all_tools()
        
        # If no specific tool requested, list all tools
        if not tool_name:
            tools_info = []
            for name, tool in all_tools.items():
                # Get schema from args_schema if available
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    schema = tool.args_schema.schema()
                    parameters = schema.get("properties", {})
                    # Add descriptions from Field definitions if available
                    for param_name, param_info in parameters.items():
                        if not param_info.get("description"):
                            field = tool.args_schema.__fields__.get(param_name)
                            if field and field.field_info.description:
                                param_info["description"] = field.field_info.description
                else:
                    parameters = {}
                
                tools_info.append({
                    "name": name,
                    "description": tool.description,
                    "parameters": parameters
                })
            return json.dumps(tools_info, indent=2)
        
        # Get help for a specific tool
        if tool_name in all_tools:
            tool = all_tools[tool_name]
            
            # Get schema from args_schema if available
            if hasattr(tool, 'args_schema') and tool.args_schema:
                schema = tool.args_schema.schema()
                parameters = schema.get("properties", {})
                # Add descriptions from Field definitions if available
                for param_name, param_info in parameters.items():
                    if not param_info.get("description"):
                        field = tool.args_schema.__fields__.get(param_name)
                        if field and field.field_info.description:
                            param_info["description"] = field.field_info.description
            else:
                parameters = {}
            
            # Create example arguments based on parameter types
            example_args = {}
            for param_name, param_info in parameters.items():
                param_type = param_info.get("type", "")
                if param_type == "string":
                    example_args[param_name] = "example_value"
                elif param_type == "integer":
                    example_args[param_name] = 5
                elif param_type == "boolean":
                    example_args[param_name] = True
                elif param_type == "array":
                    example_args[param_name] = []
                elif param_type == "object":
                    example_args[param_name] = {}
            
            return {
                "name": tool_name,
                "description": tool.description,
                "parameters": parameters,
                "example_usage": f"Action: {tool_name}\nAction Input: {json.dumps(example_args, indent=2)}"
            }
            
        return f"Tool '{tool_name}' not found. Available tools: {', '.join(all_tools.keys())}"

    def get_args_schema(self) -> Type[BaseModel]:
        """Return the args schema for the tool"""
        return self.args_schema

# Register available tools based on configuration
def register_configured_tools():
    # Get enabled servers from config
    enabled_servers = config.get_enabled_servers()
    print(f"Enabled servers: {enabled_servers}")
    
    # Register Help tool first (always available)
    try:
        ToolRegistry.register_tool(HelpTool)
        logger.info("Registered Help tool")
    except Exception as e:
        logger.error(f"Failed to register Help tool: {e}")
        
    # Register Brave Search if configured
    if 'brave-search' in enabled_servers:
        try:
            ToolRegistry.register_tool(BraveSearchTool)
            logger.info("Registered Brave Search tool")
        except Exception as e:
            logger.error(f"Failed to register Brave Search tool: {e}")
    
    # Register Filesystem tool
    try:
        ToolRegistry.register_tool(FilesystemTool)
        logger.info("Registered Filesystem tool")
    except Exception as e:
        logger.error(f"Failed to register Filesystem tool: {e}")
    
    # Register Alpha API if configured
    if 'alpha-api' in enabled_servers:
        try:
            # Verify alpha.json path exists
            alpha_config = enabled_servers['alpha-api']
            alpha_path = alpha_config.get('args', [])[1] if len(alpha_config.get('args', [])) > 1 else None
            
            if alpha_path and Path(alpha_path).exists():
                ToolRegistry.register_tool(AlphaApiTool)
                logger.info("Registered Alpha API tool")
            else:
                logger.warning(f"Alpha API OpenAPI spec not found at {alpha_path}")
        except Exception as e:
            logger.error(f"Failed to register Alpha API tool: {e}")
    else:
        logger.info("Alpha API not configured in MCP servers")

# Register tools on module import
register_configured_tools()

__all__ = [
    'AlphaApiTool',
    'AlphaToolInput',
    'BraveSearchTool',
    'FilesystemTool',
    'ToolRegistry'
]
