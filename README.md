# Cog

Your AI Companion, Engineered for Intelligence

A powerful AI assistant that combines multiple leading language models with the Model Context Protocol (MCP) for advanced tool usage and automation. This project provides both a command-line interface and REST API for interacting with AI models while giving them access to various tools and capabilities.

## 🌟 Key Features

- **Multiple LLM Support**: 
  - Anthropic
  - OpenAI
  - xAI
- **Advanced Tool Usage**: Full MCP (Model Context Protocol) integration for powerful tool capabilities
- **Multiple Interfaces**: 
  - Interactive CLI for direct usage
  - REST API for programmatic access
- **Conversation Management**: Persistent storage and retrieval of chat histories
- **Dynamic Tool Discovery**: Automatic detection and integration of MCP-compatible tools
- **Usage Tracking**: Built-in monitoring of model usage and performance

## 🧠 Understanding the Core Concepts

### Large Language Models (LLMs)

1. **Anthropic**
   - Advanced reasoning capabilities
   - Extensive tool integration support
   - Configurable parameters

2. **OpenAI**
   - State-of-the-art performance
   - Robust tool handling
   - Advanced configuration options

3. **X.AI**
   - Latest AI technology
   - Custom API endpoint support
   - Flexible deployment options

Each provider can be configured with:
- Custom temperature settings
- Token limit adjustments
- API key configuration
- Provider-specific parameters

### Model Context Protocol (MCP)
MCP is a universal protocol that standardizes how AI models interact with tools and services:
- **Tool Definition**: Tools describe their capabilities and requirements in a standard format
- **Structured Communication**: Models and tools communicate through a defined protocol
- **Dynamic Discovery**: Tools can be added or removed without changing the core system
- **Language Agnostic**: Works with any programming language or framework

## 🏗️ Architecture

### Core Components

1. **API Server** (`api_server.py`):
   - FastAPI-based REST API
   - Handles chat requests and responses
   - Manages conversation state
   - Provides tool listing and usage endpoints

2. **CLI Interface** (`cli_chat.py`):
   - Interactive command-line interface
   - Direct model interaction
   - Tool exploration and usage
   - Conversation saving/loading

3. **Memory Management** (`src/memory_manager.py`):
   - Persistent storage of conversations
   - Chat history retrieval
   - Context window management
   - Message formatting and processing

4. **LLM Integration** (`src/llm_factory.py`, `src/llm_helper.py`):
   - Model initialization and configuration
   - Response parsing and formatting
   - Tool integration with models
   - Usage tracking and monitoring

6. **Database Layer** (`src/database.py`):
   - SQLAlchemy ORM
   - Message storage
   - Conversation tracking
   - Usage statistics

### Data Flow

1. User sends a message through any interface (rest API/CLI)
2. Message is processed by the agent system
3. LLM receives the message with context and available tools
4. Model decides if tool usage is needed
5. If tools are needed, requests are sent through MCP
6. Results are incorporated into the model's response
7. Final response is returned to the user
8. Conversation is saved to the database

## 🚀 Getting Started

### Prerequisites

1. **System Requirements**:
   - Python 3.9+
   - API keys for desired providers:
     - ANTHROPIC_API_KEY
     - OPENAI_API_KEY
     - GROK_API_KEY
   - Sufficient storage for conversation history

2. **API Keys Setup**:
   ```bash
   # Add to your environment or .env file
   export ANTHROPIC_API_KEY=your_anthropic_key_here
   export OPENAI_API_KEY=your_openai_key_here
   export GROK_API_KEY=your_grok_key_here
   ```

### Installation

1. **Clone and Setup**:
   ```bash
   git clone https://github.com/madtank/OllamaAssist.git
   cd OllamaAssist
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configuration**:
   Create a `.env` file:
   ```properties
   # LLM API Keys
   ANTHROPIC_API_KEY=your_anthropic_key_here
   OPENAI_API_KEY=your_openai_key_here
   GROK_API_KEY=your_grok_key_here
   ```

3. **LLM Configuration**:
   Configure your preferred provider in `config.json`:
   ```json
   {
     "llm": {
       "provider": "anthropic",  // or "openai" or "grok"
       "settings": {
         "temperature": 0,
         "max_tokens": 4096
       }
     }
   }
   ```

## 🎯 Usage

### CLI Interface
The command-line interface provides an interactive way to chat with the AI:

```bash
python cli_chat.py
```

Features:
- Interactive chat session
- Tool exploration and usage
- Conversation saving/loading
- Command history
- Real-time responses

Available commands:
```bash
/help     - Show available commands
/tools    - List available tools
/save     - Save current conversation
/load     - Load a saved conversation
/clear    - Start a new conversation
/exit     - Exit the application
```

### API Server
Run the API server for programmatic access:

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

### API Endpoints

1. **Chat** (`POST /chat`):
   ```json
   {
     "input": "Your message here",
     "conversation_id": "optional-id",
     "user_id": "optional-user-id",
     "title": "optional-title"
   }
   ```
   Response:
   ```json
   {
     "output": "AI response",
     "conversation_id": "conversation-uuid"
   }
   ```

2. **Tools** (`GET /tools`):
   - Lists available tools and their capabilities
   ```json
   {
     "tools": [
       {
         "name": "tool_name",
         "description": "Tool description",
         "parameters": {
           "param1": {"type": "string", "description": "..."},
           "param2": {"type": "integer", "description": "..."}
         }
       }
     ]
   }
   ```

3. **Conversations** (`GET /conversations`):
   - Retrieves conversation history
   ```json
   {
     "conversations": [
       {
         "id": "conversation-uuid",
         "title": "Conversation title",
         "created_at": "timestamp",
         "messages": [...]
       }
     ]
   }
   ```

## 🔧 Development

### Adding New Tools

1. Create an MCP-compatible tool:
   ```python
   from mcp_core import MCPTool
   
   class MyTool(MCPTool):
       name = "my_tool"
       description = "Tool description"
       
       async def execute(self, **kwargs):
           # Tool implementation
           pass
   ```

2. Add to `mcp_config.json`:
   ```json
   {
     "mcpServers": {
       "my-tool": {
         "command": "python",
         "args": ["my_tool.py"]
       }
     }
   }
   ```

### Testing

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_tools.py

# Run with coverage
coverage run -m pytest
coverage report
```

## 📚 Advanced Topics

### Context Window Management
The system maintains a sliding window of conversation history to:
- Prevent context overflow
- Maintain relevant information
- Optimize model performance

### Tool Chaining
Models can use multiple tools in sequence to:
- Break down complex tasks
- Combine tool capabilities
- Handle multi-step operations

### Error Handling
The system includes robust error handling for:
- Tool failures
- Model errors
- Network issues
- Invalid inputs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [MCP](https://modelcontextprotocol.io) for the universal tool protocol
- [FastAPI](https://fastapi.tiangolo.com/) for the API server
- [LangChain](https://langchain.com/) for the agent framework
- [Anthropic](https://anthropic.com) for Claude
- [OpenAI](https://openai.com) for GPT-4
- [X.AI](https://x.ai) for Grok
- [madtank](https://github.com/madtank/OllamaAssist.git) for the initial idea