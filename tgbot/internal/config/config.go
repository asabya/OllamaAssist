// Package config provides configuration management for the Telegram bot.
// It handles loading and managing configuration from environment variables
// and provides default values where appropriate.
package config

import (
	"os"
	"strconv"
)

// Config holds all configuration for the application.
// It centralizes all configurable parameters and provides
// type-safe access to configuration values.
type Config struct {
	// TelegramToken is the authentication token for the Telegram Bot API.
	// This token is required and must be obtained from BotFather.
	TelegramToken string

	// APIServerURL is the base URL for the OllamaAssist API server.
	// This URL is used for all API communications.
	APIServerURL string

	// DefaultConversationLimit specifies the maximum number of conversations
	// to return when listing conversations.
	DefaultConversationLimit int
}

// New creates a new Config instance with values from environment variables.
// It follows the following precedence:
// 1. Environment variable if set
// 2. Default value if environment variable is not set
//
// Required environment variables:
// - TELEGRAM_BOT_TOKEN: The Telegram bot token
//
// Optional environment variables:
// - API_SERVER_URL: The API server URL (default: http://localhost:8080)
// - DEFAULT_CONVERSATION_LIMIT: Max conversations to list (default: 10)
func New() *Config {
	return &Config{
		TelegramToken:            getEnvOrDefault("TELEGRAM_BOT_TOKEN", ""),
		APIServerURL:             getEnvOrDefault("API_SERVER_URL", "http://localhost:8080"),
		DefaultConversationLimit: getEnvIntOrDefault("DEFAULT_CONVERSATION_LIMIT", 10),
	}
}

// getEnvOrDefault retrieves an environment variable or returns a default value.
// If the environment variable is not set or is empty, the default value is returned.
func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvIntOrDefault retrieves an environment variable as integer or returns a default value.
// If the environment variable is not set, empty, or cannot be converted to an integer,
// the default value is returned.
func getEnvIntOrDefault(key string, defaultValue int) int {
	strValue := os.Getenv(key)
	if strValue == "" {
		return defaultValue
	}

	value, err := strconv.Atoi(strValue)
	if err != nil {
		return defaultValue
	}
	return value
}
