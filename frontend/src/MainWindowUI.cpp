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
    
    // Draw title text
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(255, 255, 255));
    SelectObject(hdc, hTitleFont_);
    
    const wchar_t* titleText = L"Hôm nay bạn có ý tưởng gì?";
    RECT titleRect = {0, windowHeight_ / 2 - 150, windowWidth_, windowHeight_ / 2 - 100};
    DrawTextW(hdc, titleText, -1, &titleRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    
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

    // Background (circle)
    HBRUSH brush = CreateSolidBrush(RGB(255, 255, 255)); // white circle like screenshot
    HPEN pen = CreatePen(PS_SOLID, 1, RGB(200, 200, 200));
    HGDIOBJ oldBrush = SelectObject(hdc, brush);
    HGDIOBJ oldPen = SelectObject(hdc, pen);
    Ellipse(hdc, circleRect.left, circleRect.top, circleRect.right, circleRect.bottom);

    // Draw arrow in the center
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(0, 0, 0));
    HFONT oldFont = (HFONT)SelectObject(hdc, hInputFont_);
    DrawTextW(hdc, L"↑", -1, &circleRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);

    // Cleanup
    SelectObject(hdc, oldFont);
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
    DeleteObject(brush);
    DeleteObject(pen);
}

void MainWindow::OnSize() {
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    windowWidth_ = clientRect.right - clientRect.left;
    windowHeight_ = clientRect.bottom - clientRect.top;
    
    // Recalculate input field position (keep centered)
    int inputWidth = windowWidth_ * 0.7;
    int inputHeight = 60;
    int inputX = (windowWidth_ - inputWidth) / 2;
    int inputY = (windowHeight_ - inputHeight) / 2;
    
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
    
    // Calculate input field position (centered)
    int inputWidth = width * 0.7; // 70% of window width
    int inputHeight = 60;
    int inputX = (width - inputWidth) / 2;
    // Center vertically
    int inputY = (height - inputHeight) / 2;
    
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