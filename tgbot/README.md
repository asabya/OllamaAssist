# OllamaAssist Telegram Bot

A Telegram bot that interfaces with the OllamaAssist API to provide conversational AI capabilities through Telegram.

## Features

- Start new conversations or continue existing ones
- List and manage conversation history
- View available AI tools and capabilities
- Seamless integration with OllamaAssist API
- Conversation state management
- Error handling and graceful shutdown

## Prerequisites

- Go 1.21 or later
- Telegram Bot Token (obtain from [@BotFather](https://t.me/botfather))
- Access to OllamaAssist API server

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/madtank/OllamaAssist.git
   cd OllamaAssist/tgbot
   ```

2. Install dependencies:
   ```bash
   go mod tidy
   ```

## Configuration

The bot uses environment variables for configuration. Set the following variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | Required |
| `API_SERVER_URL` | OllamaAssist API server URL | http://localhost:8080 |
| `DEFAULT_CONVERSATION_LIMIT` | Number of conversations to show in list | 10 |

Example configuration:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export API_SERVER_URL="http://your-api-server:8080"
export DEFAULT_CONVERSATION_LIMIT=15
```

## Usage

1. Start the bot:
   ```bash
   go run main.go
   ```

2. Available commands in Telegram:
   - `/start` - Start a new conversation
   - `/start <conversation_id>` - Continue an existing conversation
   - `/list` - Show recent conversations
   - `/servers` - List available AI tools

### Example Interactions

1. Starting a new conversation:
   ```
   User: /start
   Bot: Started new conversation! How can I help you?
   ```

2. Continuing a conversation:
   ```
   User: /start abc123
   Bot: Loaded conversation: abc123
   ```

3. Listing conversations:
   ```
   User: /list
   Bot: Recent conversations:
   
   ID: abc123
   Title: Previous Chat
   Created: 2024-03-20 15:30:45
   
   ID: def456
   Title: Another Chat
   Created: 2024-03-20 14:20:30
   ```

## API Integration

The bot integrates with the following OllamaAssist API endpoints:

### Chat API
- **Endpoint**: `POST /chat`
- **Purpose**: Send and receive chat messages
- **Request Format**:
  ```json
  {
    "input": "Your message here",
    "conversation_id": "optional-id",
    "user_id": "optional-user-id",
    "title": "optional-title"
  }
  ```
- **Response Format**:
  ```json
  {
    "output": "AI response",
    "conversation_id": "conversation-uuid"
  }
  ```

### Conversations API
- **Endpoint**: `GET /conversations`
- **Purpose**: Retrieve conversation history
- **Response Format**:
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

### Tools API
- **Endpoint**: `GET /tools`
- **Purpose**: List available AI tools and capabilities
- **Response Format**:
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

## Error Handling

The bot includes comprehensive error handling:
- Connection errors with helpful messages
- API communication error recovery
- Graceful shutdown on system signals
- Invalid command handling

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 