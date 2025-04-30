import pytest
import json
import os
from pathlib import Path
import asyncio
from unittest.mock import patch, mock_open
from ..mcp_client import mcp

# Sample test configuration
TEST_CONFIG = {
    "mcpServers": {
        "test_server": {
            "enabled": True,
            "command": "npx",
            "args": ["@microsoft/mcp-server"],
            "env": {
                "TEST_ENV": "value"
            }
        },
        "alpha": {
            "command": "/opt/homebrew/bin/mcp-proxy",
            "args": ["http://127.0.0.1:8000/mcp"]
        },
        "disabled_server": {
            "enabled": False,
            "command": "npx",
            "args": []
        }
    }
}

@pytest.fixture
def mock_config_file(tmp_path):
    config_path = tmp_path / "mcp_config.json"
    with open(config_path, 'w') as f:
        json.dump(TEST_CONFIG, f)
    return config_path

@pytest.mark.asyncio
async def test_list_available_servers(mock_config_file):
    with patch('pathlib.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=json.dumps(TEST_CONFIG))):
        
        result = await mcp(tool='list_available_servers')
        servers = json.loads(result)
        
        assert isinstance(servers, list)
        assert "test_server" in servers
        assert "alpha" in servers
        assert "disabled_server" not in servers

@pytest.mark.asyncio
async def test_tool_details_invalid_server():
    with patch('pathlib.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=json.dumps(TEST_CONFIG))):
        
        result = await mcp(server="nonexistent_server", tool="tool_details")
        assert isinstance(result, dict)
        assert "error" in result
        assert "not found" in result["error"]

@pytest.mark.asyncio
async def test_disabled_server():
    with patch('pathlib.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=json.dumps(TEST_CONFIG))):
        
        result = await mcp(server="disabled_server", tool="tool_details")
        assert isinstance(result, dict)
        assert "error" in result
        assert "disabled" in result["error"]

@pytest.mark.asyncio
async def test_missing_server_parameter():
    with patch('pathlib.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=json.dumps(TEST_CONFIG))):
        
        result = await mcp(tool="some_tool")
        assert isinstance(result, dict)
        assert "error" in result
        assert "Server parameter required" in result["error"] 