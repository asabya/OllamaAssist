from typing import Dict, Type
from langchain.tools import StructuredTool
from .alpha import AlphaApiTool
from .brave import BraveSearchTool
from .filesystem import FileSystemTool as FilesystemTool

class ToolRegistry:
    """Registry for all available tools"""
    _tools: Dict[str, Type[StructuredTool]] = {}
    _instances: Dict[str, StructuredTool] = {}

    @classmethod
    def register_tool(cls, tool_class: Type[StructuredTool]) -> None:
        """Register a tool class"""
        # Create a temporary instance to get the name
        tool_instance = tool_class()
        cls._tools[tool_instance.name] = tool_class
    
    @classmethod
    def get_tool(cls, name: str) -> StructuredTool:
        """Get a tool instance by name"""
        if name not in cls._instances:
            if name in cls._tools:
                tool = cls._tools[name]()
                cls._instances[name] = tool.to_langchain_tool()
            else:
                return None
        return cls._instances[name]
    
    @classmethod
    def get_all_tools(cls) -> Dict[str, StructuredTool]:
        """Get all registered tools"""
        # Initialize any tools that haven't been instantiated yet
        for name, tool_class in cls._tools.items():
            if name not in cls._instances:
                tool = tool_class()
                cls._instances[name] = tool
        return cls._instances

# Register all tools
ToolRegistry.register_tool(AlphaApiTool)
ToolRegistry.register_tool(BraveSearchTool)
ToolRegistry.register_tool(FilesystemTool)
