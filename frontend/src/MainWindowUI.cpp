#include <windows.h>
#include "MainWindow.h"
#include <string>
#include <algorithm>

// UI Rendering and Layout functions for MainWindow

void MainWindow::OnPaint() {
    PAINTSTRUCT ps;
    HDC hdc = BeginPaint(hwnd_, &ps);
    
    // Fill background with dark color
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    FillRect(hdc, &clientRect, hDarkBrush_);
    
    // Draw chat messages if any exist
    if (!messages_.empty()) {
        DrawChatMessages(hdc);
    } else {
        // Draw title text only when no messages
        SetBkMode(hdc, TRANSPARENT);
        SetTextColor(hdc, RGB(255, 255, 255));
        SelectObject(hdc, hTitleFont_);
        
        const wchar_t* titleText = L"Hôm nay bạn có ý tưởng gì?";
        RECT titleRect = {0, windowHeight_ / 2 - 150, windowWidth_, windowHeight_ / 2 - 100};
        DrawTextW(hdc, titleText, -1, &titleRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    }
    
    // Draw input field
    DrawInputField(hdc);
    
    EndPaint(hwnd_, &ps);
}

void MainWindow::OnEraseBkgnd(HDC hdc) {
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    FillRect(hdc, &clientRect, hDarkBrush_);
}

void MainWindow::DrawInputField(HDC hdc) {
    // Draw rounded rectangle for input field
    HGDIOBJ oldBrush = SelectObject(hdc, hInputBrush_);
    HGDIOBJ oldPen = SelectObject(hdc, hInputPen_);
    
    // Draw rounded rectangle (simplified as rectangle with rounded corners)
    RoundRect(hdc, inputRect_.left, inputRect_.top, inputRect_.right, inputRect_.bottom, 30, 30);
    
    // Draw placeholder text if input is empty
    if (showPlaceholder_) {
        SetBkMode(hdc, TRANSPARENT);
        SetTextColor(hdc, RGB(150, 150, 150));
        SelectObject(hdc, hInputFont_);

        RECT textRect = inputRect_;
        // Khớp với layout của Edit và nút gửi
        int inputPaddingX = 50;
        int buttonMarginRight = 12;
        int gapTextToButton = 10;
        int inputHeight = inputRect_.bottom - inputRect_.top;
        int buttonSize = inputHeight - 16;
        int buttonX = inputRect_.right - buttonMarginRight - buttonSize;

        textRect.left = inputRect_.left + inputPaddingX + 3; // +3 để bù margin bên trong EDIT
        textRect.right = buttonX - gapTextToButton;

        const wchar_t* placeholder = L"Hỏi bất kỳ điều gì";
        DrawTextW(hdc, placeholder, -1, &textRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
    }
    
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
}

void MainWindow::DrawChatMessages(HDC hdc) {
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    
    // Calculate available area for messages (above input field)
    int inputHeight = 60;
    int marginBottom = 20; // Space between messages and input
    int messageAreaTop = 20;
    int messageAreaBottom = clientRect.bottom - inputHeight - marginBottom;
    
    // Message styling constants
    int messageMarginX = 40; // Horizontal margin from window edges
    int messageMarginY = 12; // Vertical spacing between messages
    int bubblePaddingX = 16; // Horizontal padding inside bubble
    int bubblePaddingY = 12; // Vertical padding inside bubble
    int bubbleRadius = 20; // Rounded corner radius
    int maxBubbleWidth = (int)((windowWidth_ - 2 * messageMarginX) * 0.7); // Max 70% of available width
    
    // Font for messages
    HFONT hMessageFont = CreateFontW(-18, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
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
        int bubbleHeight = textHeight + 2 * bubblePaddingY;
        
        RECT bubbleRect;
        
        if (msg.isUser) {
            // User message: right-aligned, in dark grey bubble
            bubbleRect.left = windowWidth_ - messageMarginX - bubbleWidth;
            bubbleRect.right = windowWidth_ - messageMarginX;
            bubbleRect.top = currentY;
            bubbleRect.bottom = currentY + bubbleHeight;
            
            // Draw rounded rectangle bubble
            HBRUSH bubbleBrush = CreateSolidBrush(RGB(50, 50, 50)); // Dark grey bubble
            HPEN bubblePen = CreatePen(PS_SOLID, 1, RGB(50, 50, 50));
            HGDIOBJ oldBrush = SelectObject(hdc, bubbleBrush);
            HGDIOBJ oldPen = SelectObject(hdc, bubblePen);
            
            RoundRect(hdc, bubbleRect.left, bubbleRect.top, bubbleRect.right, bubbleRect.bottom, 
                     bubbleRadius, bubbleRadius);
            
            SelectObject(hdc, oldBrush);
            SelectObject(hdc, oldPen);
            DeleteObject(bubbleBrush);
            DeleteObject(bubblePen);
            
            // Draw text in white
            SetTextColor(hdc, RGB(255, 255, 255));
            RECT textDrawRect = bubbleRect;
            textDrawRect.left += bubblePaddingX;
            textDrawRect.right -= bubblePaddingX;
            textDrawRect.top += bubblePaddingY;
            textDrawRect.bottom -= bubblePaddingY;
            DrawTextW(hdc, msg.text.c_str(), -1, &textDrawRect, DT_LEFT | DT_WORDBREAK);
        } else {
            // AI message: left-aligned, plain white text (no bubble)
            // Allow wider text for AI messages
            RECT aiTextRect = {0, 0, windowWidth_ - 2 * messageMarginX, 0};
            DrawTextW(hdc, msg.text.c_str(), -1, &aiTextRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
            int aiTextWidth = aiTextRect.right;
            int aiTextHeight = aiTextRect.bottom;
            
            bubbleRect.left = messageMarginX;
            bubbleRect.right = messageMarginX + aiTextWidth;
            bubbleRect.top = currentY;
            bubbleRect.bottom = currentY + aiTextHeight;
            
            // Draw text in white (no bubble)
            SetTextColor(hdc, RGB(255, 255, 255));
            RECT textDrawRect = bubbleRect;
            DrawTextW(hdc, msg.text.c_str(), -1, &textDrawRect, DT_LEFT | DT_WORDBREAK);
            bubbleHeight = aiTextHeight;
        }
        
        currentY += bubbleHeight + messageMarginY;
    }
    
    SelectObject(hdc, oldFont);
    DeleteObject(hMessageFont);
}

void MainWindow::DrawSendButton(HDC hdc, const RECT& rc) {
    // Ensure square region (circle)
    int size = (std::min)(rc.right - rc.left, rc.bottom - rc.top);
    int cx = (rc.left + rc.right) / 2;
    int cy = (rc.top + rc.bottom) / 2;
    RECT circleRect;
    circleRect.left   = cx - size / 2;
    circleRect.top    = cy - size / 2;
    circleRect.right  = cx + size / 2;
    circleRect.bottom = cy + size / 2;

    // Use high-resolution rendering (3x) for smooth anti-aliasing
    const int scale = 3;
    int highResSize = size * scale;
    
    // Create high-resolution memory DC for smooth rendering
    HDC hdcMem = CreateCompatibleDC(hdc);
    HBITMAP hbmMem = CreateCompatibleBitmap(hdc, highResSize, highResSize);
    HBITMAP hbmOld = (HBITMAP)SelectObject(hdcMem, hbmMem);
    
    // Fill background with dark color to match window
    RECT memRect = {0, 0, highResSize, highResSize};
    HBRUSH bgBrush = CreateSolidBrush(RGB(18, 18, 18));
    FillRect(hdcMem, &memRect, bgBrush);
    DeleteObject(bgBrush);
    
    // Enable high-quality rendering
    SetGraphicsMode(hdcMem, GM_ADVANCED);
    SetBkMode(hdcMem, TRANSPARENT);
    
    // Draw white circle with no border - perfectly smooth
    HBRUSH brush = CreateSolidBrush(RGB(255, 255, 255));
    HPEN pen = CreatePen(PS_NULL, 0, RGB(255, 255, 255)); // No visible border
    HGDIOBJ oldBrush = SelectObject(hdcMem, brush);
    HGDIOBJ oldPen = SelectObject(hdcMem, pen);
    
    // Draw circle at high resolution
    Ellipse(hdcMem, 0, 0, highResSize, highResSize);
    
    // Draw smooth arrow using polygon
    int arrowSize = (int)(highResSize * 0.35);
    int centerX = highResSize / 2;
    int centerY = highResSize / 2;
    
    // Create arrow as a filled polygon (pointing up)
    POINT arrowPoints[7];
    int arrowWidth = (int)(arrowSize * 0.6);
    int arrowHeight = arrowSize;
    
    // Arrow shape: triangle head + rectangular shaft
    arrowPoints[0].x = centerX;
    arrowPoints[0].y = centerY - arrowHeight / 2;
    arrowPoints[1].x = centerX - arrowWidth / 2;
    arrowPoints[1].y = centerY - arrowHeight / 2 + (int)(arrowHeight * 0.4);
    arrowPoints[2].x = centerX - (int)(arrowWidth * 0.25);
    arrowPoints[2].y = centerY - arrowHeight / 2 + (int)(arrowHeight * 0.4);
    arrowPoints[3].x = centerX - (int)(arrowWidth * 0.25);
    arrowPoints[3].y = centerY + arrowHeight / 2;
    arrowPoints[4].x = centerX + (int)(arrowWidth * 0.25);
    arrowPoints[4].y = centerY + arrowHeight / 2;
    arrowPoints[5].x = centerX + (int)(arrowWidth * 0.25);
    arrowPoints[5].y = centerY - arrowHeight / 2 + (int)(arrowHeight * 0.4);
    arrowPoints[6].x = centerX + arrowWidth / 2;
    arrowPoints[6].y = centerY - arrowHeight / 2 + (int)(arrowHeight * 0.4);
    
    // Draw dark arrow
    HBRUSH arrowBrush = CreateSolidBrush(RGB(0, 0, 0));
    HPEN arrowPen = CreatePen(PS_SOLID, 1, RGB(0, 0, 0));
    HGDIOBJ oldArrowBrush = SelectObject(hdcMem, arrowBrush);
    HGDIOBJ oldArrowPen = SelectObject(hdcMem, arrowPen);
    
    Polygon(hdcMem, arrowPoints, 7);
    
    // Cleanup arrow objects
    SelectObject(hdcMem, oldArrowBrush);
    SelectObject(hdcMem, oldArrowPen);
    DeleteObject(arrowBrush);
    DeleteObject(arrowPen);
    
    // Cleanup circle objects
    SelectObject(hdcMem, oldBrush);
    SelectObject(hdcMem, oldPen);
    DeleteObject(brush);
    DeleteObject(pen);
    
    // Scale down with high-quality interpolation for smooth anti-aliasing
    SetStretchBltMode(hdc, HALFTONE);
    SetBrushOrgEx(hdc, 0, 0, NULL);
    StretchBlt(hdc, circleRect.left, circleRect.top, size, size,
               hdcMem, 0, 0, highResSize, highResSize, SRCCOPY);
    
    // Cleanup memory DC
    SelectObject(hdcMem, hbmOld);
    DeleteObject(hbmMem);
    DeleteDC(hdcMem);
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
    hTitleFont_ = CreateFontW(-40, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
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