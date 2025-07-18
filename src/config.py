import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class Config:
    # Application settings
    PAGE_TITLE = "MCP Client"
    DEFAULT_MODEL = "claude-3-5-sonnet-latest"  # Default Claude model

    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize config paths
        self.project_root = Path(__file__).parent.parent
        self.config_file = self.project_root / 'mcp_config.json'
        
        # Load MCP config
        self.mcp_config = self._load_mcp_config()
        
        # Initialize available models
        self._init_models()
        
        # Apply environment overrides
        self._apply_env_overrides()

    def _init_models(self):
        """Initialize available Claude models"""
        self.AVAILABLE_MODELS = (
            "claude-3-5-sonnet-latest"
        )
        
        # Validate default model
        if self.DEFAULT_MODEL not in self.AVAILABLE_MODELS:
            self.DEFAULT_MODEL = self.AVAILABLE_MODELS[1]  # Use Sonnet as fallback
            
    def _load_mcp_config(self) -> Dict[str, Any]:
        """Load MCP server configuration from JSON"""
        if not self.config_file.exists():
            return {"mcpServers": {}}
            
        with open(self.config_file) as f:
            return json.load(f)

    def _apply_env_overrides(self):
        """Apply environment variable overrides to server configs"""
        servers = self.mcp_config.get('mcpServers', {})
        
        for server_name, config in servers.items():
            prefix = f"{server_name.upper().replace('-', '_')}_"
            
            # Override enabled status
            if os.getenv(f"{prefix}ENABLED"):
                config['enabled'] = os.getenv(f"{prefix}ENABLED").lower() == 'true'
            
            # Override command
            if os.getenv(f"{prefix}COMMAND"):
                config['command'] = os.getenv(f"{prefix}COMMAND")
            
            # Override args
            if os.getenv(f"{prefix}ARGS"):
                config['args'] = os.getenv(f"{prefix}ARGS").split()
            
            # Add/override environment variables
            if 'env' not in config:
                config['env'] = {}
                
            # Special handling for API keys and paths
            if server_name == 'brave-search' and os.getenv('BRAVE_API_KEY'):
                config['env']['BRAVE_API_KEY'] = os.getenv('BRAVE_API_KEY')
            elif server_name == 'filesystem' and os.getenv('FILESYSTEM_PATHS'):
                paths = os.getenv('FILESYSTEM_PATHS').split(':')
                config['args'] = ['-y', '@modelcontextprotocol/server-filesystem'] + paths

    def get_server_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific server"""
        return self.mcp_config.get('mcpServers', {}).get(server_name)

    def get_enabled_servers(self) -> Dict[str, Dict[str, Any]]:
        """Get all enabled server configurations"""
        return {
            name: config 
            for name, config in self.mcp_config.get('mcpServers', {}).items() 
            if config.get('enabled', True)
        }

    @property
    def debug(self) -> bool:
        """Get debug mode status"""
        return os.getenv('DEBUG', 'false').lower() == 'true'

    @property
    def log_level(self) -> str:
        """Get logging level"""
        return os.getenv('LOG_LEVEL', 'INFO')

    @property 
    def anthropic_api_key(self) -> str:
        """Get Anthropic API key from environment"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return api_key

# Create global config instance
config = Config()