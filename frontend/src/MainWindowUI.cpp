#include <windows.h>
#include "MainWindow.h"
#include <string>
#include <algorithm>

// UI layout & chat rendering (render primitives are defined in MainWindowRender.cpp)

void MainWindow::DrawChatMessages(HDC hdc) {
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    
    // Calculate available area for messages (above input field)
    int inputHeight = 60;
    int marginBottom = 20; // Space between messages and input
    int headerH = 48;
    int messageAreaTop = headerH + 20;
    int messageAreaBottom = clientRect.bottom - inputHeight - marginBottom;
    
    // Message styling constants
    int messageMarginX = 36; // Horizontal margin from window edges
    int messageMarginY = 16; // Vertical spacing between messages
    int bubblePaddingX = 18; // Horizontal padding inside bubble
    int bubblePaddingY = 14; // Vertical padding inside bubble
    int bubbleRadius = 18; // Rounded corner radius
    int maxBubbleWidth = (int)((windowWidth_ - 2 * messageMarginX) * 0.75); // Max 75% of available width
    
    // Font for messages
    HFONT hMessageFont = CreateFontW(-22, 0, 0, 0, FW_MEDIUM, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    HFONT hAIMessageFont = CreateFontW(-24, 0, 0, 0, FW_MEDIUM, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    HFONT hMetaFont = CreateFontW(-14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    HGDIOBJ oldFont = SelectObject(hdc, hMessageFont);
    
    SetBkMode(hdc, TRANSPARENT);
    
    // Calculate total height needed for all messages
    int totalHeight = 0;
    for (const auto& msg : messages_) {
        RECT textRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
        DrawTextW(hdc, msg.text.c_str(), -1, &textRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
        totalHeight += textRect.bottom + 2 * bubblePaddingY + messageMarginY;
    }
    
    // Auto-scroll to bottom (show latest messages)
    int availableHeight = messageAreaBottom - messageAreaTop;
    if (totalHeight > availableHeight) {
        scrollOffset_ = totalHeight - availableHeight;
    } else {
        scrollOffset_ = 0;
    }
    
    int currentY = messageAreaTop - scrollOffset_;
    
    // Draw messages from oldest to newest
    for (const auto& msg : messages_) {
        if (currentY > messageAreaBottom) break; // Skip messages below visible area
        if (currentY + 50 < messageAreaTop) { // Skip messages above visible area
            // Estimate height and continue
            RECT testRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
            DrawTextW(hdc, msg.text.c_str(), -1, &testRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
            currentY += testRect.bottom + 2 * bubblePaddingY + messageMarginY;
            continue;
        }
        
        // Calculate text size
        RECT textRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
        DrawTextW(hdc, msg.text.c_str(), -1, &textRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
        int textWidth = textRect.right;
        int textHeight = textRect.bottom;
        
        int bubbleWidth = textWidth + 2 * bubblePaddingX;
        int bubbleHeight = textHeight + 2 * bubblePaddingY + 16; // space for timestamp
        
        RECT bubbleRect;
        RECT textDrawRect;

        // Avatar circle
        int avatarSize = 20;
        int avatarMargin = 8;
        int bubbleOffsetX = avatarSize + avatarMargin;

        if (msg.isUser) {
            bubbleRect.left = windowWidth_ - messageMarginX - bubbleWidth;
            bubbleRect.right = windowWidth_ - messageMarginX;
            bubbleRect.top = currentY;
            bubbleRect.bottom = currentY + bubbleHeight;

            // Bubble colors
            HBRUSH bubbleBrush = CreateSolidBrush(RGB(30, 37, 61));
            HPEN bubblePen = CreatePen(PS_SOLID, 1, RGB(65, 78, 110));
            HGDIOBJ oldBrush = SelectObject(hdc, bubbleBrush);
            HGDIOBJ oldPen = SelectObject(hdc, bubblePen);
            RoundRect(hdc, bubbleRect.left, bubbleRect.top, bubbleRect.right, bubbleRect.bottom, 
                     bubbleRadius, bubbleRadius);
            SelectObject(hdc, oldBrush);
            SelectObject(hdc, oldPen);
            DeleteObject(bubbleBrush);
            DeleteObject(bubblePen);

            // Text
            SetTextColor(hdc, RGB(236, 240, 255));
            textDrawRect = bubbleRect;
            textDrawRect.left += bubblePaddingX;
            textDrawRect.right -= bubblePaddingX;
            textDrawRect.top += bubblePaddingY;
            textDrawRect.bottom = textDrawRect.top + textHeight;
            DrawTextW(hdc, msg.text.c_str(), -1, &textDrawRect, DT_LEFT | DT_WORDBREAK);

            // Timestamp
            SelectObject(hdc, hMetaFont);
            SetTextColor(hdc, RGB(154, 163, 195));
            RECT metaRect = textDrawRect;
            metaRect.top = textDrawRect.bottom + 4;
            metaRect.bottom = bubbleRect.bottom - bubblePaddingY + 2;
            DrawTextW(hdc, msg.timestamp.c_str(), -1, &metaRect, DT_RIGHT | DT_VCENTER | DT_SINGLELINE);

            // Avatar (right)
            HBRUSH avatarBrush = CreateSolidBrush(RGB(74, 215, 255));
            HPEN avatarPen = CreatePen(PS_NULL, 0, RGB(74, 215, 255));
            oldBrush = SelectObject(hdc, avatarBrush);
            oldPen = SelectObject(hdc, avatarPen);
            int ax = bubbleRect.right + avatarMargin;
            int ay = bubbleRect.top + 4;
            Ellipse(hdc, ax, ay, ax + avatarSize, ay + avatarSize);
            SelectObject(hdc, oldBrush);
            SelectObject(hdc, oldPen);
            DeleteObject(avatarBrush);
            DeleteObject(avatarPen);
        } else {
            // AI message: left-aligned glass bubble
            SelectObject(hdc, hAIMessageFont);
            RECT aiTextRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
            DrawTextW(hdc, msg.text.c_str(), -1, &aiTextRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
            textWidth = aiTextRect.right;
            textHeight = aiTextRect.bottom;
            bubbleWidth = textWidth + 2 * bubblePaddingX;
            bubbleHeight = textHeight + 2 * bubblePaddingY + 16;

            bubbleRect.left = messageMarginX + bubbleOffsetX;
            bubbleRect.right = bubbleRect.left + bubbleWidth;
            bubbleRect.top = currentY;
            bubbleRect.bottom = currentY + bubbleHeight;

            HBRUSH bubbleBrush = CreateSolidBrush(RGB(24, 32, 48));
            HPEN bubblePen = CreatePen(PS_SOLID, 1, RGB(74, 215, 255));
            HGDIOBJ oldBrush = SelectObject(hdc, bubbleBrush);
            HGDIOBJ oldPen = SelectObject(hdc, bubblePen);
            RoundRect(hdc, bubbleRect.left, bubbleRect.top, bubbleRect.right, bubbleRect.bottom,
                      bubbleRadius, bubbleRadius);
            SelectObject(hdc, oldBrush);
            SelectObject(hdc, oldPen);
            DeleteObject(bubbleBrush);
            DeleteObject(bubblePen);

            // Avatar (left)
            HBRUSH avatarBrush = CreateSolidBrush(RGB(154, 107, 255));
            HPEN avatarPen = CreatePen(PS_NULL, 0, RGB(154, 107, 255));
            oldBrush = SelectObject(hdc, avatarBrush);
            oldPen = SelectObject(hdc, avatarPen);
            int ax = messageMarginX;
            int ay = bubbleRect.top + 4;
            Ellipse(hdc, ax, ay, ax + avatarSize, ay + avatarSize);
            SelectObject(hdc, oldBrush);
            SelectObject(hdc, oldPen);
            DeleteObject(avatarBrush);
            DeleteObject(avatarPen);

            // Text
            SetTextColor(hdc, RGB(232, 236, 255));
            textDrawRect = bubbleRect;
            textDrawRect.left += bubblePaddingX;
            textDrawRect.right -= bubblePaddingX;
            textDrawRect.top += bubblePaddingY;
            textDrawRect.bottom = textDrawRect.top + textHeight;
            DrawTextW(hdc, msg.text.c_str(), -1, &textDrawRect, DT_LEFT | DT_WORDBREAK);

            // Timestamp
            SelectObject(hdc, hMetaFont);
            SetTextColor(hdc, RGB(154, 163, 195));
            RECT metaRect = textDrawRect;
            metaRect.top = textDrawRect.bottom + 4;
            metaRect.bottom = bubbleRect.bottom - bubblePaddingY + 2;
            DrawTextW(hdc, msg.timestamp.c_str(), -1, &metaRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
        }
        
        currentY += bubbleHeight + messageMarginY;
    }
    
    SelectObject(hdc, oldFont);
    DeleteObject(hMessageFont);
    DeleteObject(hAIMessageFont);
    DeleteObject(hMetaFont);
}


void MainWindow::OnSize() {
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    windowWidth_ = clientRect.right - clientRect.left;
    windowHeight_ = clientRect.bottom - clientRect.top;

    // Layout input:
    // - Khi chưa có message: input nằm giữa màn hình, ngay dưới dòng title
    // - Khi đã có message: input nằm sát cạnh dưới
    // - Khi đang animate: dùng animCurrentY_ (di chuyển dần từ giữa -> dưới)
    bool initialLayout = messages_.empty() && !isAnimating_;

    int inputWidth = static_cast<int>(windowWidth_ * 0.7);
    int inputHeight = 60;
    int inputX = (windowWidth_ - inputWidth) / 2;
    int inputY;

    int centerY = windowHeight_ / 2 + 40;
    int bottomY = windowHeight_ - inputHeight - 20; // 20px from bottom
    if (centerY + inputHeight + 20 > windowHeight_) {
        centerY = bottomY; // fallback nếu cửa sổ quá nhỏ
    }

    if (isAnimating_) {
        animTargetY_ = bottomY;
        // Giữ currentY trong khoảng [centerY, bottomY]
        if (animCurrentY_ < centerY) animCurrentY_ = centerY;
        if (animCurrentY_ > bottomY) animCurrentY_ = bottomY;
        inputY = animCurrentY_;
    } else if (initialLayout) {
        inputY = centerY;
        animCurrentY_ = inputY;
        animTargetY_ = inputY;
    } else {
        inputY = bottomY;
        animCurrentY_ = inputY;
        animTargetY_ = inputY;
    }
    
    inputRect_.left = inputX;
    inputRect_.top = inputY;
    inputRect_.right = inputX + inputWidth;
    inputRect_.bottom = inputY + inputHeight;
    
    // Layout constants must match OnCreate
    int inputPaddingY = 16;
    int inputPaddingX = 50;
    int buttonMarginRight = 12;
    int gapTextToButton = 10;

    int buttonSize = inputHeight - 16;
    int buttonX = inputRect_.right - buttonMarginRight - buttonSize;
    int buttonY = inputY + (inputHeight - buttonSize) / 2;

    int editX = inputX + inputPaddingX;
    int editWidth = buttonX - gapTextToButton - editX;

    // Update input control position (keep visually centered)
    if (hChatInput_) {
        SetWindowPos(hChatInput_, NULL,
                     editX, inputY + inputPaddingY,
                     editWidth, inputHeight - 2 * inputPaddingY,
                     SWP_NOZORDER);
    }

    // Update send button position (keep aligned inside the right of input field)
    if (hSendButton_) {
        SetWindowPos(hSendButton_, NULL,
                     buttonX, buttonY,
                     buttonSize, buttonSize,
                     SWP_NOZORDER);
    }
    
    InvalidateRect(hwnd_, NULL, TRUE);
}

void MainWindow::OnCreate() {
    // Get module handle if hInstance_ is not set
    HINSTANCE hInst = hInstance_ ? hInstance_ : GetModuleHandle(NULL);
    
    // Create fonts
    hTitleFont_ = CreateFontW(-44, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    // Larger font for input text
    hInputFont_ = CreateFontW(-22, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    int width = clientRect.right - clientRect.left;
    int height = clientRect.bottom - clientRect.top;
    
    // Layout ban đầu giống OnSize: xét theo việc đã có message hay chưa và trạng thái animate
    bool initialLayout = messages_.empty() && !isAnimating_;

    int inputWidth = static_cast<int>(width * 0.7); // 70% of window width
    int inputHeight = 60;
    int inputX = (width - inputWidth) / 2;
    int inputY;

    int centerY = height / 2 + 40;
    int bottomY = height - inputHeight - 20; // 20px from bottom
    if (centerY + inputHeight + 20 > height) {
        centerY = bottomY;
    }

    if (isAnimating_) {
        animCurrentY_ = centerY;
        animTargetY_ = bottomY;
        inputY = animCurrentY_;
    } else if (initialLayout) {
        inputY = centerY;
        animCurrentY_ = inputY;
        animTargetY_ = inputY;
    } else {
        inputY = bottomY;
        animCurrentY_ = inputY;
        animTargetY_ = inputY;
    }
    
    inputRect_.left = inputX;
    inputRect_.top = inputY;
    inputRect_.right = inputX + inputWidth;
    inputRect_.bottom = inputY + inputHeight;
    
    // Layout constants inside the rounded input field
    int inputPaddingY = 16;          // vertical padding inside rounded rect
    int inputPaddingX = 50;          // left padding for text
    int buttonMarginRight = 12;      // space from right border to button
    int gapTextToButton = 10;        // gap between text area and button

    int buttonSize = inputHeight - 16; // slightly smaller than input rect height
    int buttonX = inputRect_.right - buttonMarginRight - buttonSize;
    int buttonY = inputY + (inputHeight - buttonSize) / 2;

    int editX = inputX + inputPaddingX;
    int editWidth = buttonX - gapTextToButton - editX;

    // Create chat input (single line, visually centered by padding)
    hChatInput_ = CreateWindowW(L"EDIT", L"",
        WS_CHILD | WS_VISIBLE | ES_LEFT | ES_AUTOHSCROLL,
        editX, inputY + inputPaddingY, editWidth, inputHeight - 2 * inputPaddingY,
        hwnd_, (HMENU)1001, hInst, NULL);
    
    if (!hChatInput_) {
        DWORD error = GetLastError();
        wchar_t errorMsg[256];
        swprintf_s(errorMsg, L"Failed to create input control\nError: %lu", error);
        MessageBoxW(hwnd_, errorMsg, L"Error", MB_OK | MB_ICONERROR);
    }
    
    // Set font and colors
    SendMessage(hChatInput_, WM_SETFONT, (WPARAM)hInputFont_, TRUE);
    
    // Subclass edit control to handle Ctrl+A
    if (hChatInput_) {
        originalEditProc_ = (WNDPROC)SetWindowLongPtrW(hChatInput_, GWLP_WNDPROC, (LONG_PTR)EditProc);
    }
    
    // Create hidden chat history for storing messages
    hChatHistory_ = CreateWindowW(L"EDIT", L"",
        WS_CHILD | ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL,
        0, 0, 0, 0,
        hwnd_, (HMENU)1002, hInst, NULL);
    
    // Clear initial text (Unicode-safe)
    SetWindowTextW(hChatInput_, L"");

    // Create send button inside the input field, aligned to the right
    hSendButton_ = CreateWindowW(
        L"BUTTON", L"", // we'll draw the arrow ourselves
        WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
        buttonX, buttonY, buttonSize, buttonSize,
        hwnd_, (HMENU)1003, hInst, NULL);

    if (hSendButton_) {
        SendMessage(hSendButton_, WM_SETFONT, (WPARAM)hInputFont_, TRUE);
    }
    
    // Update window
    UpdateWindow(hwnd_);
    
    // Delayed initialization
    PostMessage(hwnd_, WM_USER + 1, 0, 0);
}