#pragma once

// Sử dụng trực tiếp khai báo chuẩn từ Windows SDK
// để tránh xung đột kiểu dữ liệu (ví dụ HDC void* vs HDC__*).
#include <windows.h>

#include <string>
#include <cstdint>
#include <vector>
#include "HttpClient.h"

struct ChatMessage {
    std::wstring text;
    bool isUser; // true for user messages, false for AI messages
    std::wstring timestamp;
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
    void OnEraseBkgnd(HDC hdc);
    
    void SendChatMessage();
    void DrawInputField(HDC hdc);
    void DrawSendButton(HDC hdc, const RECT& rc);
    void DrawChatMessages(HDC hdc);
    void RefreshConversations();
    void RefreshTasks();
    void CreateTask();
    
    void AppendTextToEdit(HWND hEdit, const std::wstring& text);
    void ClearEdit(HWND hEdit);
    
    HWND hwnd_;
    HINSTANCE hInstance_;
    
    // Controls
    HWND hChatInput_;
    HWND hChatHistory_;
    HWND hSendButton_;
    
    // Colors and brushes
    HBRUSH hDarkBrush_;
    HBRUSH hInputBrush_;
    HPEN hInputPen_;
    HFONT hTitleFont_;
    HFONT hInputFont_;
    
    // Window dimensions
    int windowWidth_;
    int windowHeight_;
    
    HttpClient httpClient_;
    std::string sessionId_;
    
    // Input field position and size
    RECT inputRect_;
    bool showPlaceholder_;
    
    // Edit control subclassing
    WNDPROC originalEditProc_;
    
    // Chat messages
    std::vector<ChatMessage> messages_;
    int scrollOffset_; // For scrolling chat messages

    // Input animation state (center -> bottom)
    bool isAnimating_ = false;
    int animCurrentY_ = 0;
    int animTargetY_ = 0;
    int animStartY_ = 0;
    UINT_PTR animTimerId_ = 0;
};