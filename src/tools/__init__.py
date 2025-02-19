from .registry import ToolRegistry
from .brave import BraveSearchTool
from .filesystem import FilesystemTool
from .alpha import AlphaApiTool
from .base import BaseTool
from ..config import config
import logging
from pathlib import Path

# Initialize logging
logger = logging.getLogger(__name__)

# Register available tools based on configuration
def register_configured_tools():
    # Get enabled servers from config
    enabled_servers = config.get_enabled_servers()
    
    # Register Brave Search if configured
    if 'brave-search' in enabled_servers:
        try:
            ToolRegistry.register("brave", BraveSearchTool())
            logger.info("Registered Brave Search tool")
        except Exception as e:
            logger.error(f"Failed to register Brave Search tool: {e}")
    
    # Register Filesystem tool
    try:
        ToolRegistry.register("filesystem", FilesystemTool())
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
                ToolRegistry.register("alpha", AlphaApiTool())
                logger.info("Registered Alpha API tool")
            else:
                logger.warning(f"Alpha API OpenAPI spec not found at {alpha_path}")
        except Exception as e:
            logger.error(f"Failed to register Alpha API tool: {e}")
    else:
        logger.info("Alpha API not configured in MCP servers")

# Register tools on module import
register_configured_tools()

__all__ = ['ToolRegistry', 'BaseTool']
