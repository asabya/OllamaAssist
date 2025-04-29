from typing import Any, Dict, ClassVar, Literal, Type
import logging
from pydantic import BaseModel, Field, ConfigDict
from langchain.tools import StructuredTool
from ..mcp_client import mcp

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class FileSystemInput(BaseModel):
    """Input schema for Filesystem tool"""
    command: Literal["read", "write", "list", "delete"] = Field(
        description="Command to execute (read/write/list/delete)"
    )
    path: str = Field(
        description="File or directory path"
    )
    content: str = Field(
        description="Content to write (only for write command)",
        default=""
    )

class FileSystemTool(StructuredTool):
    """Filesystem tool for file operations"""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Tool configuration
    name: str = "filesystem"
    description: str = "Perform filesystem operations (read/write/list/delete)"
    args_schema: Type[BaseModel] = FileSystemInput
    
    # Tool-specific constants
    OPERATIONS: ClassVar[Dict[str, str]] = {
        "read": "API-read_file_api_file_read_get",
        "write": "API-write_file_api_file_write_post",
        "list": "API-list_directory_api_file_list_get",
        "delete": "API-delete_file_api_file_delete_delete"
    }
    
    async def _arun(self, command: str, path: str, content: str = "") -> Any:
        """Execute filesystem operations"""
        logger.info(f"Filesystem request - Command: {command}, Path: {path}")
        
        try:
            # Map command to operation ID
            operation_id = self.OPERATIONS.get(command.lower())
            if not operation_id:
                return {"error": f"Invalid command: {command}"}
            
            # Prepare arguments based on command
            arguments = {"path": path}
            if command.lower() == "write":
                arguments["content"] = content
            
            # Call filesystem operation through MCP
            response = await mcp(
                server="filesystem",
                tool=operation_id,
                arguments=arguments
            )
            
            logger.info(f"Filesystem operation completed: {command}")
            
            # Handle string response
            if isinstance(response, str):
                return response
            
            # Handle object response with content attribute
            if hasattr(response, 'content'):
                for content in response.content:
                    if content.type == 'text':
                        return content.text
            
            return response
            
        except Exception as e:
            error_msg = f"Filesystem error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

    def get_prompt(self) -> str:
        """Return the tool-specific prompt"""
        return ""  # Filesystem tool doesn't have a specific prompt
