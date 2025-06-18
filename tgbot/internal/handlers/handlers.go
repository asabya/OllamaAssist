// Package handlers provides command and message handlers for the Telegram bot.
// It processes incoming messages, executes commands, and manages the interaction
// between users and the OllamaAssist API.
package handlers

import (
	"fmt"
	"strconv"
	"strings"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"github.com/madtank/OllamaAssist/tgbot/internal/api"
	"github.com/madtank/OllamaAssist/tgbot/internal/conversation"
)

// Handler manages bot command handling.
// It coordinates between the API client and conversation manager
// to process user messages and commands.
type Handler struct {
	// apiClient handles communication with the OllamaAssist API
	apiClient *api.Client
	// convManager manages conversation state and user sessions
	convManager *conversation.Manager
}

// NewHandler creates a new command handler.
// It initializes the handler with the necessary dependencies.
//
// Parameters:
// - apiClient: Client for communicating with the OllamaAssist API
// - convManager: Manager for handling conversation state
//
// Returns:
// - *Handler: A new handler instance
func NewHandler(apiClient *api.Client, convManager *conversation.Manager) *Handler {
	return &Handler{
		apiClient:   apiClient,
		convManager: convManager,
	}
}

// HandleStart handles the /start command.
// It either starts a new conversation or loads an existing one
// based on whether a conversation ID is provided as an argument.
//
// Parameters:
// - msg: The incoming Telegram message
//
// Returns:
// - tgbotapi.MessageConfig: The response message to send
func (h *Handler) HandleStart(msg *tgbotapi.Message) tgbotapi.MessageConfig {
	args := strings.Fields(msg.CommandArguments())

	if len(args) > 0 {
		// Load existing conversation
		session := &conversation.UserSession{
			ConversationID: args[0],
		}
		h.convManager.UpdateSession(msg.From.ID, session)
		return tgbotapi.NewMessage(msg.Chat.ID, fmt.Sprintf("Loaded conversation: %s", args[0]))
	}

	// Start new conversation
	req := api.ChatRequest{
		Input:  "/start",
		UserID: strconv.FormatInt(msg.From.ID, 10),
		Title:  "New Conversation",
	}

	resp, err := h.apiClient.SendMessage(req)
	if err != nil {
		return tgbotapi.NewMessage(msg.Chat.ID, "Error starting new conversation")
	}

	h.convManager.StartConversation(msg.From.ID, resp.ConversationID)
	return tgbotapi.NewMessage(msg.Chat.ID, resp.Output)
}

// HandleList handles the /list command.
// It retrieves and formats the list of recent conversations
// for the user to view.
//
// Parameters:
// - msg: The incoming Telegram message
//
// Returns:
// - tgbotapi.MessageConfig: The response message containing the conversation list
func (h *Handler) HandleList(msg *tgbotapi.Message) tgbotapi.MessageConfig {
	conversations, err := h.apiClient.GetConversations()
	if err != nil {
		return tgbotapi.NewMessage(msg.Chat.ID, "Error retrieving conversations")
	}

	if len(conversations) == 0 {
		return tgbotapi.NewMessage(msg.Chat.ID, "No conversations found")
	}

	var response strings.Builder
	response.WriteString("Recent conversations:\n\n")

	for _, conv := range conversations {
		response.WriteString(fmt.Sprintf("ID: %s\nTitle: %s\nCreated: %s\n\n",
			conv.ID, conv.Title, conv.CreatedAt.Format("2006-01-02 15:04:05")))
	}

	return tgbotapi.NewMessage(msg.Chat.ID, response.String())
}

// HandleMessage handles regular chat messages.
// It processes non-command messages, maintains conversation context,
// and communicates with the OllamaAssist API.
//
// Parameters:
// - msg: The incoming Telegram message
//
// Returns:
// - tgbotapi.MessageConfig: The AI's response message
func (h *Handler) HandleMessage(msg *tgbotapi.Message) tgbotapi.MessageConfig {
	session := h.convManager.GetSession(msg.From.ID)

	var conversationID string
	if session != nil {
		conversationID = session.ConversationID
	}

	req := api.ChatRequest{
		Input:          msg.Text,
		UserID:         strconv.FormatInt(msg.From.ID, 10),
		ConversationID: conversationID,
	}

	resp, err := h.apiClient.SendMessage(req)
	if err != nil {
		return tgbotapi.NewMessage(msg.Chat.ID, "Error processing message")
	}

	// If there was no session or no conversation ID, start a new conversation
	if conversationID == "" {
		h.convManager.StartConversation(msg.From.ID, resp.ConversationID)
	}

	return tgbotapi.NewMessage(msg.Chat.ID, resp.Output)
}

// HandleServers handles the /servers command.
// It retrieves and displays information about available AI tools
// and their capabilities.
//
// Parameters:
// - msg: The incoming Telegram message
//
// Returns:
// - tgbotapi.MessageConfig: The response message containing server information
func (h *Handler) HandleServers(msg *tgbotapi.Message) tgbotapi.MessageConfig {
	tools, err := h.apiClient.GetTools()
	if err != nil {
		return tgbotapi.NewMessage(msg.Chat.ID, "Error retrieving server information")
	}

	return tgbotapi.NewMessage(msg.Chat.ID, fmt.Sprintf("Available tools: %+v", tools))
}
