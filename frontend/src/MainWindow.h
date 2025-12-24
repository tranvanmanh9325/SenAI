#pragma once

// Sử dụng trực tiếp khai báo chuẩn từ Windows SDK
// để tránh xung đột kiểu dữ liệu (ví dụ HDC void* vs HDC__*).
#include <windows.h>

#include <string>
#include <cstdint>
#include <vector>
#include "HttpClient.h"
#include "UiStrings.h"

enum class MessageType {
    User,
    AI,
    System,
    Error,
    Info,
    Code
};

struct MessageMetadata {
    std::string rawJson;           // Raw JSON response from backend (if available)
    int tokenUsage = 0;            // Token count used for this message
    int latencyMs = 0;              // Response latency in milliseconds
    std::wstring modelName;         // Model name used (if available)
    
    MessageMetadata() {}
};

struct ChatMessage {
    std::wstring text;
    bool isUser; // true for user messages, false for AI messages (deprecated, use type instead)
    MessageType type; // Message type: User, AI, System, Error, Info, Code
    std::wstring timestamp;
    MessageMetadata metadata;       // Additional metadata for tooltip/future features
    
    ChatMessage() : isUser(false), type(MessageType::AI) {}
};

// State management for chat view UI
struct ChatViewState {
    std::vector<ChatMessage> messages;
    int scrollOffset = 0;           // For scrolling chat messages (pixels)
    bool autoScrollToBottom = true;  // When true, always keep view pinned to latest message
    bool showPlaceholder = true;     // Show placeholder text in input field
    
    // Input animation state (center -> bottom)
    bool isAnimating = false;
    int animCurrentY = 0;
    int animTargetY = 0;
    int animStartY = 0;
    UINT_PTR animTimerId_ = 0;  // Note: underscore suffix to match existing code style
    
    // Reset all state to initial values
    void Reset() {
        messages.clear();
        scrollOffset = 0;
        autoScrollToBottom = true;
        showPlaceholder = true;
        isAnimating = false;
        animCurrentY = 0;
        animTargetY = 0;
        animStartY = 0;
        if (animTimerId_ != 0) {
            // Note: Need HWND to kill timer, so this is handled externally
            animTimerId_ = 0;
        }
    }
};

struct ConversationInfo {
    int id;
    std::wstring sessionId;
    std::wstring preview; // First few words of user_message
    std::wstring timestamp; // Formatted created_at
    std::string rawSessionId; // UTF-8 session_id for API calls
};

// Nhóm hằng số theme/layout để dễ quản lý
struct UiTheme {
    // Colors
    COLORREF colorBackground   = RGB(0, 0, 0);
    COLORREF colorGrid         = RGB(25, 30, 40);
    COLORREF colorHeaderBg     = RGB(16, 22, 40);
    COLORREF colorHeaderLine   = RGB(74, 215, 255);
    COLORREF colorHeaderText   = RGB(232, 236, 255);
    COLORREF colorStatusBg     = RGB(50, 140, 80);
    COLORREF colorStatusBorder = RGB(90, 200, 120);
    COLORREF colorStatusText   = RGB(230, 255, 240);
    COLORREF colorInputOuter   = RGB(25, 36, 64);
    COLORREF colorInputInner   = RGB(18, 24, 42);
    COLORREF colorInputStroke  = RGB(74, 215, 255);
    COLORREF colorInputInnerStroke = RGB(60, 90, 130);
    COLORREF colorPlaceholder  = RGB(154, 163, 195);

    // Layout
    int headerHeight   = 48;
    int inputHeight    = 60;
    int inputRadius    = 28;
    int messageMarginX = 36;
    int messageMarginY = 16;
};

class MainWindow {
public:
    MainWindow();
    ~MainWindow();
    
    bool Create(HINSTANCE hInstance);
    void Show(int nCmdShow);
    int Run();
    
private:
    static LRESULT CALLBACK WindowProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam);
    static LRESULT CALLBACK EditProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam);
    LRESULT HandleMessage(UINT uMsg, WPARAM wParam, LPARAM lParam);
    
    void OnCreate();
    void OnCommand(WPARAM wParam);
    void OnSize();
    void OnPaint();
    BOOL OnEraseBkgnd(HDC hdc);
    
    void SendChatMessage();
    void DrawInputField(HDC hdc);
    void DrawSendButton(HDC hdc, const RECT& rc);
    void DrawNewSessionButton(HDC hdc, const RECT& rc, bool isPressed);
    void DrawChatMessages(HDC hdc);
    void DrawSidebar(HDC hdc);
    void DrawStatusBadge(HDC hdc, const RECT& headerRect, RECT* outBadgeRect = nullptr, int titleEndX = 0);
    void RefreshConversations();
    void LoadConversationBySessionId(const std::string& sessionId);
    void RefreshTasks();
    void CreateTask();
    
    void AppendTextToEdit(HWND hEdit, const std::wstring& text);
    void ClearEdit(HWND hEdit);
    
    // Helper functions for creating messages
    ChatMessage CreateUserMessage(const std::wstring& text);
    ChatMessage CreateAIMessage(const std::wstring& text, const MessageMetadata& metadata = MessageMetadata());
    ChatMessage CreateSystemMessage(const std::wstring& text);
    ChatMessage CreateErrorMessage(const std::wstring& text, const MessageMetadata& metadata = MessageMetadata());
    ChatMessage CreateInfoMessage(const std::wstring& text);
    ChatMessage CreateCodeMessage(const std::wstring& text, const MessageMetadata& metadata = MessageMetadata());
    
    // Convenience methods for adding messages
    void AddUserMessage(const std::wstring& text);
    void AddAIMessage(const std::wstring& text, const MessageMetadata& metadata = MessageMetadata());
    void AddSystemMessage(const std::wstring& text);
    void AddErrorMessage(const std::wstring& text, const MessageMetadata& metadata = MessageMetadata());
    void AddInfoMessage(const std::wstring& text);
    void AddCodeMessage(const std::wstring& text, const MessageMetadata& metadata = MessageMetadata());
    
    HWND hwnd_;
    HINSTANCE hInstance_;
    
    // Controls
    HWND hChatInput_;
    HWND hChatHistory_;
    HWND hSendButton_;
    HWND hNewSessionButton_;
    
    // Colors and brushes
    HBRUSH hDarkBrush_;
    HBRUSH hInputBrush_;
    HPEN hInputPen_;
    HFONT hTitleFont_;
    HFONT hInputFont_;
    
    // Window dimensions
    int windowWidth_;
    int windowHeight_;

    // Theme config
    UiTheme theme_;
    UiStrings uiStrings_;
    
    HttpClient httpClient_;
    std::string sessionId_;
    std::string configPath_;   // Path to config file
    std::wstring modelName_;   // Current model name from backend health
    
    // Input field position and size
    RECT inputRect_;
    RECT newSessionButtonRect_;
    RECT sendButtonRect_;
    
    // Edit control subclassing
    WNDPROC originalEditProc_;
    
    // Chat view state (consolidated UI state)
    ChatViewState chatViewState_;
    
    // Sidebar conversations list
    std::vector<ConversationInfo> conversations_;
    int sidebarWidth_ = 280;     // Width of sidebar panel
    int sidebarScrollOffset_ = 0; // Scroll offset for sidebar
    int selectedConversationIndex_ = -1; // Currently selected conversation

    // UI state
    bool isSendButtonHover_ = false;
    bool isNewSessionButtonHover_ = false;
    bool sidebarVisible_ = true; // Toggle sidebar visibility
    
    // Health check state
    enum class HealthStatus {
        Checking,  // Đang kiểm tra
        Online,     // Kết nối OK
        Offline     // Lỗi kết nối
    };
    HealthStatus healthStatus_ = HealthStatus::Checking;
    UINT_PTR healthCheckTimerId_ = 0;
    void CheckHealthStatus();
    
    // Settings icon state
    bool isSettingsIconHover_ = false;
    RECT settingsIconRect_;
    void DrawSettingsIcon(HDC hdc);
    void HandleSettingsIconClick();
    void ShowSettingsDialog();
    static LRESULT CALLBACK SettingsDlgProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam);
    
    // Config load/save
    void LoadSettingsFromFile();
    void SaveSettingsToFile(const std::string& baseUrl, const std::string& apiKey);
    void UpdateModelNameFromHealth(const std::string& healthJson);
    
    // Hover tracking for messages
    int hoveredMessageIndex_ = -1; // Index of hovered message bubble
    void UpdateMessageHover(int x, int y);

    // Hover tracking for sidebar items
    int hoveredConversationIndex_ = -1;
};