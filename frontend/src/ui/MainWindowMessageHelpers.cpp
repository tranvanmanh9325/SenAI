#include "MainWindow.h"
#include "MainWindowHelpers.h"
#include <ctime>

// Helper functions for creating messages
ChatMessage MainWindow::CreateUserMessage(const std::wstring& text) {
    ChatMessage msg;
    msg.text = text;
    msg.isUser = true;
    msg.type = MessageType::User;
    msg.timestamp = GetCurrentTimeW();
    return msg;
}

ChatMessage MainWindow::CreateAIMessage(const std::wstring& text, const MessageMetadata& metadata) {
    ChatMessage msg;
    msg.text = text;
    msg.isUser = false;
    msg.type = MessageType::AI;
    msg.timestamp = GetCurrentTimeW();
    msg.metadata = metadata;
    return msg;
}

ChatMessage MainWindow::CreateSystemMessage(const std::wstring& text) {
    ChatMessage msg;
    msg.text = text;
    msg.isUser = false;
    msg.type = MessageType::System;
    msg.timestamp = GetCurrentTimeW();
    return msg;
}

ChatMessage MainWindow::CreateErrorMessage(const std::wstring& text, const MessageMetadata& metadata) {
    ChatMessage msg;
    msg.text = text;
    msg.isUser = false;
    msg.type = MessageType::Error;
    msg.timestamp = GetCurrentTimeW();
    msg.metadata = metadata;
    return msg;
}

ChatMessage MainWindow::CreateInfoMessage(const std::wstring& text) {
    ChatMessage msg;
    msg.text = text;
    msg.isUser = false;
    msg.type = MessageType::Info;
    msg.timestamp = GetCurrentTimeW();
    return msg;
}

ChatMessage MainWindow::CreateCodeMessage(const std::wstring& text, const MessageMetadata& metadata) {
    ChatMessage msg;
    msg.text = text;
    msg.isUser = false;
    msg.type = MessageType::Code;
    msg.timestamp = GetCurrentTimeW();
    msg.metadata = metadata;
    return msg;
}

// Convenience methods for adding messages
void MainWindow::AddUserMessage(const std::wstring& text) {
    chatViewState_.messages.push_back(CreateUserMessage(text));
    chatViewState_.autoScrollToBottom = true;
}

void MainWindow::AddAIMessage(const std::wstring& text, const MessageMetadata& metadata) {
    chatViewState_.messages.push_back(CreateAIMessage(text, metadata));
    chatViewState_.autoScrollToBottom = true;
}

void MainWindow::AddSystemMessage(const std::wstring& text) {
    chatViewState_.messages.push_back(CreateSystemMessage(text));
    chatViewState_.autoScrollToBottom = true;
}

void MainWindow::AddErrorMessage(const std::wstring& text, const MessageMetadata& metadata) {
    chatViewState_.messages.push_back(CreateErrorMessage(text, metadata));
    chatViewState_.autoScrollToBottom = true;
}

void MainWindow::AddInfoMessage(const std::wstring& text) {
    chatViewState_.messages.push_back(CreateInfoMessage(text));
    chatViewState_.autoScrollToBottom = true;
}

void MainWindow::AddCodeMessage(const std::wstring& text, const MessageMetadata& metadata) {
    chatViewState_.messages.push_back(CreateCodeMessage(text, metadata));
    chatViewState_.autoScrollToBottom = true;
}