// Package api provides client implementation for the OllamaAssist API.
// It handles all communication with the API server, including request/response
// handling, error management, and data type conversions.
package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// Client handles communication with the API server.
// It provides methods for all supported API operations and
// manages the underlying HTTP client configuration.
type Client struct {
	// baseURL is the root URL for the API server
	baseURL string
	// httpClient is the configured HTTP client with timeout
	httpClient *http.Client
}

// ChatRequest represents a chat request to the API.
// It contains all parameters that can be sent to the chat endpoint.
type ChatRequest struct {
	// Input is the user's message or command
	Input string `json:"input"`
	// ConversationID is optional and links the message to an existing conversation
	ConversationID string `json:"conversation_id,omitempty"`
	// UserID is optional and identifies the user sending the message
	UserID string `json:"user_id,omitempty"`
	// Title is optional and can be used to name a new conversation
	Title string `json:"title,omitempty"`
}

// ChatResponse represents the response from the chat API.
// It contains the AI's response and conversation tracking information.
type ChatResponse struct {
	// Output is the AI's response message
	Output string `json:"output"`
	// ConversationID uniquely identifies the conversation
	ConversationID string `json:"conversation_id"`
}

// Conversation represents a chat conversation.
// It contains metadata and the messages in the conversation.
type Conversation struct {
	// ID uniquely identifies the conversation
	ID string `json:"id"`
	// Title is the user-friendly name of the conversation
	Title string `json:"title"`
	// CreatedAt is the timestamp when the conversation started
	CreatedAt time.Time `json:"created_at"`
	// Messages contains all messages in the conversation
	Messages []Message `json:"messages"`
}

// Message represents a chat message.
// It contains the content and metadata about the message.
type Message struct {
	// Role identifies who sent the message (e.g., "user" or "assistant")
	Role string `json:"role"`
	// Content is the actual message text
	Content string `json:"content"`
	// Timestamp indicates when the message was sent
	Timestamp time.Time `json:"timestamp"`
}

// NewClient creates a new API client.
// It configures the client with the provided base URL and
// sets up the HTTP client with appropriate timeout settings.
func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: time.Second * 30,
		},
	}
}

// SendMessage sends a chat message to the API.
// It handles the HTTP request/response cycle and error handling.
//
// Returns:
// - ChatResponse: Contains the AI's response and conversation ID
// - error: Any error that occurred during the request
func (c *Client) SendMessage(req ChatRequest) (*ChatResponse, error) {
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("error marshaling request: %w", err)
	}

	resp, err := c.httpClient.Post(
		c.baseURL+"/chat",
		"application/json",
		bytes.NewBuffer(jsonData),
	)
	if err != nil {
		return nil, fmt.Errorf("error sending request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var chatResp ChatResponse
	if err := json.NewDecoder(resp.Body).Decode(&chatResp); err != nil {
		return nil, fmt.Errorf("error decoding response: %w", err)
	}

	return &chatResp, nil
}

// GetConversations retrieves the list of conversations.
// It fetches the conversation history from the API server.
//
// Returns:
// - []Conversation: List of conversations with their metadata
// - error: Any error that occurred during the request
func (c *Client) GetConversations() ([]Conversation, error) {
	resp, err := c.httpClient.Get(c.baseURL + "/conversations")
	if err != nil {
		return nil, fmt.Errorf("error getting conversations: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var result struct {
		Conversations []Conversation `json:"conversations"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("error decoding response: %w", err)
	}

	return result.Conversations, nil
}

// GetTools retrieves the list of available tools.
// It fetches the tool definitions and capabilities from the API server.
//
// Returns:
// - map[string]interface{}: Tool definitions and their parameters
// - error: Any error that occurred during the request
func (c *Client) GetTools() (map[string]interface{}, error) {
	resp, err := c.httpClient.Get(c.baseURL + "/tools")
	if err != nil {
		return nil, fmt.Errorf("error getting tools: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("error decoding response: %w", err)
	}

	return result, nil
}
