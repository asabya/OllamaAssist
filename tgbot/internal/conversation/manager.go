// Package conversation provides conversation state management for the Telegram bot.
// It handles tracking active conversations, managing user sessions, and maintaining
// conversation context across multiple messages.
package conversation

import (
	"sync"
)

// UserSession represents an active user session.
// It contains information about the current conversation and user state.
type UserSession struct {
	// UserID identifies the user in the system
	UserID string
	// ConversationID links the session to a specific conversation
	ConversationID string
}

// Manager handles conversation state management.
// It provides thread-safe access to user sessions and conversation tracking.
// The manager uses a mutex to ensure safe concurrent access to the sessions map.
type Manager struct {
	// sessions maps Telegram user IDs to their active sessions
	sessions map[int64]*UserSession
	// mu protects concurrent access to the sessions map
	mu sync.RWMutex
}

// NewManager creates a new conversation manager.
// It initializes the sessions map and prepares the manager for use.
func NewManager() *Manager {
	return &Manager{
		sessions: make(map[int64]*UserSession),
	}
}

// StartConversation creates or updates a user session with a new conversation.
// It associates the given Telegram user ID with a conversation ID.
// If a session already exists for the user, it is overwritten.
//
// Parameters:
// - telegramUserID: The Telegram user's unique identifier
// - conversationID: The ID of the conversation to associate with the user
func (m *Manager) StartConversation(telegramUserID int64, conversationID string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.sessions[telegramUserID] = &UserSession{
		ConversationID: conversationID,
	}
}

// GetSession retrieves the current session for a user.
// It returns nil if no session exists for the given user ID.
//
// Parameters:
// - telegramUserID: The Telegram user's unique identifier
//
// Returns:
// - *UserSession: The user's current session, or nil if not found
func (m *Manager) GetSession(telegramUserID int64) *UserSession {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return m.sessions[telegramUserID]
}

// ClearSession removes a user's session.
// This is useful when ending a conversation or cleaning up inactive sessions.
//
// Parameters:
// - telegramUserID: The Telegram user's unique identifier
func (m *Manager) ClearSession(telegramUserID int64) {
	m.mu.Lock()
	defer m.mu.Unlock()

	delete(m.sessions, telegramUserID)
}

// UpdateSession updates a user's session with new data.
// It replaces the existing session data with the provided session.
//
// Parameters:
// - telegramUserID: The Telegram user's unique identifier
// - session: The new session data to store
func (m *Manager) UpdateSession(telegramUserID int64, session *UserSession) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.sessions[telegramUserID] = session
}
