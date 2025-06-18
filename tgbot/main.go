package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"github.com/madtank/OllamaAssist/tgbot/internal/api"
	"github.com/madtank/OllamaAssist/tgbot/internal/config"
	"github.com/madtank/OllamaAssist/tgbot/internal/conversation"
	"github.com/madtank/OllamaAssist/tgbot/internal/handlers"
)

func main() {
	// Load configuration
	cfg := config.New()
	if cfg.TelegramToken == "" {
		log.Fatal("TELEGRAM_BOT_TOKEN is required")
	}

	// Initialize components
	apiClient := api.NewClient(cfg.APIServerURL)
	convManager := conversation.NewManager()
	handler := handlers.NewHandler(apiClient, convManager)

	// Create bot instance
	bot, err := tgbotapi.NewBotAPI(cfg.TelegramToken)
	if err != nil {
		log.Fatalf("Error creating bot: %v", err)
	}

	bot.Debug = true
	log.Printf("Authorized on account %s", bot.Self.UserName)

	// Set up update configuration
	updateConfig := tgbotapi.NewUpdate(0)
	updateConfig.Timeout = 60

	// Get updates channel
	updates := bot.GetUpdatesChan(updateConfig)

	// Set up graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		log.Println("Shutting down...")
		bot.StopReceivingUpdates()
		os.Exit(0)
	}()

	// Handle updates
	for update := range updates {
		if update.Message == nil {
			continue
		}

		var msg tgbotapi.MessageConfig

		// Handle commands
		if update.Message.IsCommand() {
			switch update.Message.Command() {
			case "start":
				msg = handler.HandleStart(update.Message)
			case "list":
				msg = handler.HandleList(update.Message)
			case "servers":
				msg = handler.HandleServers(update.Message)
			default:
				msg = tgbotapi.NewMessage(update.Message.Chat.ID, "Unknown command")
			}
		} else {
			// Handle regular messages
			msg = handler.HandleMessage(update.Message)
		}

		msg.ReplyToMessageID = update.Message.MessageID

		if _, err := bot.Send(msg); err != nil {
			log.Printf("Error sending message: %v", err)
		}
	}
}
