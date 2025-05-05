"""
Dynamic MCP (Model Context Protocol) client that provides access to various server capabilities.
"""
import json
import os
import platform
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
import logging
import asyncio
from typing import Any, Optional, Dict

# Set up logging
logger = logging.getLogger(__name__)

async def mcp(server: str = None, tool: str = None, arguments: dict = None) -> Any:
    """
    Dynamic MCP client that adapts to available server capabilities.
    
    Args:
        server: Name of the MCP server to use
        tool: Name of the tool to execute or special commands:
              - 'list_available_servers': List available servers
              - 'tool_details': Get tool information for a server
        arguments: Dictionary of tool-specific arguments
    
    Returns:
        Tool execution results or discovery information
    """
    try:
        # Check multiple config locations
        possible_paths = [
            Path('mcp_config.json'),  # Current directory
            Path.home() / '.config' / 'autogen' / 'mcp_config.json',  # User config dir
            Path(os.getenv('MCP_CONFIG_PATH', 'mcp_config.json')),  # Environment variable
        ]

        config_path = None
        for path in possible_paths:
            if path.exists():
                config_path = path
                break

        if not config_path:
            paths_checked = '\n'.join(str(p) for p in possible_paths)
            raise FileNotFoundError(f"No configuration file found. Checked:\n{paths_checked}")

        # Get system-specific npx path
        system = platform.system()
        if system == "Darwin":  # macOS
            default_npx = Path("/opt/homebrew/bin/npx")
        elif system == "Windows":
            default_npx = Path(os.getenv("APPDATA")) / "npm/npx.cmd"
        else:  # Linux and others
            default_npx = Path("/usr/local/bin/npx")

        # Find npx in PATH if default doesn't exist
        npx_path = str(default_npx if default_npx.exists() else "npx")

        # Load config
        with open(config_path) as f:
            config_data = json.load(f)
            servers = config_data.get('mcpServers', {})

        # Handle list_available_servers
        if tool == 'list_available_servers':
            enabled_servers = [name for name, cfg in servers.items() if cfg.get('enabled', True)]
            return json.dumps(enabled_servers, indent=2)

        # Validate server
        if not server:
            raise ValueError("Server parameter required for tool operations")
        if server not in servers:
            raise ValueError(f"Server {server} not found")
        if not servers[server].get('enabled', True):
            raise ValueError(f"Server {server} is disabled in configuration")

        # Build server connection
        config = servers[server]
        server_type = config.get('type', 'stdio')  # Default to stdio for backward compatibility
        env = os.environ.copy()
        env.update(config.get('env', {}))

        arguments = arguments or {}
        # Connect to server and execute tool
        try:
            if server_type == 'stdio':
                command = npx_path if config['command'] == 'npx' else config['command']
                server_params = StdioServerParameters(
                    command=command,
                    args=config.get('args', []),
                    env=env
                )
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        try:
                            await session.initialize()

                            # Handle tool_details
                            if tool == 'tool_details':
                                result = await session.list_tools()
                                print(result)
                                return json.dumps([{
                                    'name': t.name,
                                    'description': t.description,
                                    'input_schema': t.inputSchema
                                } for t in result.tools], indent=2)

                            # Execute requested tool
                            if not tool:
                                raise ValueError("Tool name required")

                            return await session.call_tool(tool, arguments=arguments)

                        except asyncio.CancelledError:
                            logger.error(f"Operation cancelled for tool {tool}")
                            raise
                        except Exception as e:
                            logger.error(f"Error executing tool {tool}: {str(e)}", exc_info=True)
                            if isinstance(e, asyncio.exceptions.TimeoutError):
                                return {"error": "Operation timed out"}
                            return {"error": str(e)}
            elif server_type == 'sse':
                async with sse_client(url=config['url']) as (read, write):
                    async with ClientSession(read, write) as session:
                        try:
                            await session.initialize()

                            # Handle tool_details
                            if tool == 'tool_details':
                                result = await session.list_tools()
                                return json.dumps([{
                                    'name': t.name,
                                    'description': t.description,
                                    'input_schema': t.inputSchema
                                } for t in result.tools], indent=2)

                            # Execute requested tool
                            if not tool:
                                raise ValueError("Tool name required")

                            return await session.call_tool(tool, arguments=arguments)

                        except asyncio.CancelledError:
                            logger.error(f"Operation cancelled for tool {tool}")
                            raise
                        except Exception as e:
                            logger.error(f"Error executing tool {tool}: {str(e)}", exc_info=True)
                            if isinstance(e, asyncio.exceptions.TimeoutError):
                                return {"error": "Operation timed out"}
                            return {"error": str(e)}
            else:
                raise ValueError(f"Unsupported server type: {server_type}")

            

        except asyncio.exceptions.CancelledError:
            logger.error("MCP client operation cancelled")
            return {"error": "Operation cancelled"}
        except Exception as e:
            logger.error(f"Error in MCP client: {str(e)}", exc_info=True)
            return {"error": f"MCP client error: {str(e)}"}

    except Exception as e:
        logger.error(f"Fatal error in MCP client: {str(e)}", exc_info=True)
        return {"error": f"Fatal error: {str(e)}"}