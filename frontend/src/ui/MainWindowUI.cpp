#include <windows.h>
#include "MainWindow.h"
#include <string>
#include <algorithm>
void MainWindow::OnSize() {
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    windowWidth_ = clientRect.right - clientRect.left;
    windowHeight_ = clientRect.bottom - clientRect.top;

    // Layout input:
    // - Khi chưa có message: input nằm giữa màn hình, ngay dưới dòng title
    // - Khi đã có message: input nằm sát cạnh dưới
    // - Khi đang animate: dùng animCurrentY (di chuyển dần từ giữa -> dưới)
    bool initialLayout = chatViewState_.messages.empty() && !chatViewState_.isAnimating;

    // Main content area: when sidebar hiển thị thì phần nội dung bắt đầu từ sidebarWidth_
    int contentLeft = sidebarVisible_ ? sidebarWidth_ : 0;
    int contentWidth = windowWidth_ - contentLeft;
    if (contentWidth < 0) contentWidth = 0;

    int inputWidth = static_cast<int>(contentWidth * 0.7);
    int inputHeight = 60;
    int inputX = contentLeft + (contentWidth - inputWidth) / 2;
    int inputY;

    int centerY = windowHeight_ / 2 + 40;
    int bottomY = windowHeight_ - inputHeight - 20; // 20px from bottom
    if (centerY + inputHeight + 20 > windowHeight_) {
        centerY = bottomY; // fallback nếu cửa sổ quá nhỏ
    }

    if (chatViewState_.isAnimating) {
        chatViewState_.animTargetY = bottomY;
        // Giữ currentY trong khoảng [centerY, bottomY]
        if (chatViewState_.animCurrentY < centerY) chatViewState_.animCurrentY = centerY;
        if (chatViewState_.animCurrentY > bottomY) chatViewState_.animCurrentY = bottomY;
        inputY = chatViewState_.animCurrentY;
    } else if (initialLayout) {
        inputY = centerY;
        chatViewState_.animCurrentY = inputY;
        chatViewState_.animTargetY = inputY;
    } else {
        inputY = bottomY;
        chatViewState_.animCurrentY = inputY;
        chatViewState_.animTargetY = inputY;
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

    // Update logical send button rect (custom drawn, không dùng child window để tránh nhấp nháy)
    sendButtonRect_.left   = buttonX;
    sendButtonRect_.top    = buttonY;
    sendButtonRect_.right  = buttonX + buttonSize;
    sendButtonRect_.bottom = buttonY + buttonSize;

    int editX = inputX + inputPaddingX;
    int editWidth = buttonX - gapTextToButton - editX;

    // Update input control position (keep visually centered)
    if (hChatInput_) {
        SetWindowPos(hChatInput_, NULL,
                     editX, inputY + inputPaddingY,
                     editWidth, inputHeight - 2 * inputPaddingY,
                     SWP_NOZORDER);
    }

    // Cập nhật rect cho nút "Chat Mới" trong sidebar (vẽ custom, không dùng child window)
    {
        int headerH = theme_.headerHeight;
        int marginX = 16;
        int marginY = 12;
        int newBtnHeight = 34;
        int newBtnWidth = sidebarWidth_ - marginX * 2;
        if (newBtnWidth < 140) newBtnWidth = 140; // minimal width for readability
        newSessionButtonRect_.left = marginX;
        newSessionButtonRect_.top = headerH + marginY;
        newSessionButtonRect_.right = newSessionButtonRect_.left + newBtnWidth;
        newSessionButtonRect_.bottom = newSessionButtonRect_.top + newBtnHeight;
    }
    
    // Update search bar position if visible
    if (searchVisible_) {
        int headerH = theme_.headerHeight;
        int searchBarHeight = 40;
        int searchBarY = headerH + 2;
        int sidebarOffset = sidebarVisible_ ? sidebarWidth_ : 0;
        int searchBarLeft = sidebarOffset + 16;
        int searchBarWidth = windowWidth_ - sidebarOffset - 32;
        int searchBarRight = searchBarLeft + searchBarWidth;
        
        searchBarRect_.left = searchBarLeft;
        searchBarRect_.top = searchBarY;
        searchBarRect_.right = searchBarRight;
        searchBarRect_.bottom = searchBarY + searchBarHeight;
        
        // Reposition search edit control
        if (hSearchEdit_) {
            SetWindowPos(hSearchEdit_, NULL,
                searchBarLeft + 8, searchBarY + 8, searchBarWidth - 200, 24,
                SWP_NOZORDER);
        }
        
        // Update button rects
        int buttonWidth = 40;
        int buttonHeight = 28;
        int buttonY = searchBarY + 6;
        int buttonSpacing = 5;
        
        searchCloseButtonRect_.right = searchBarRight - 8;
        searchCloseButtonRect_.left = searchCloseButtonRect_.right - buttonWidth;
        searchCloseButtonRect_.top = buttonY;
        searchCloseButtonRect_.bottom = buttonY + buttonHeight;
        
        searchNextButtonRect_.right = searchCloseButtonRect_.left - buttonSpacing;
        searchNextButtonRect_.left = searchNextButtonRect_.right - buttonWidth;
        searchNextButtonRect_.top = buttonY;
        searchNextButtonRect_.bottom = buttonY + buttonHeight;
        
        searchPrevButtonRect_.right = searchNextButtonRect_.left - buttonSpacing;
        searchPrevButtonRect_.left = searchPrevButtonRect_.right - buttonWidth;
        searchPrevButtonRect_.top = buttonY;
        searchPrevButtonRect_.bottom = buttonY + buttonHeight;
    }
    
    // Redraw without erasing background to avoid flicker
    InvalidateRect(hwnd_, NULL, FALSE);
}

void MainWindow::OnCreate() {
    // Get module handle if hInstance_ is not set
    HINSTANCE hInst = hInstance_ ? hInstance_ : GetModuleHandle(NULL);
    
    // Create and cache fonts using resource manager
    hTitleFont_ = gdiManager_->CreateFont(-44, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    // Larger font for input text
    hInputFont_ = gdiManager_->CreateFont(-22, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    // Cache commonly used fonts for rendering
    hMessageFont_ = gdiManager_->CreateFont(-20, 0, 0, 0, FW_MEDIUM, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    hAIMessageFont_ = gdiManager_->CreateFont(-22, 0, 0, 0, FW_MEDIUM, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    hCodeFont_ = gdiManager_->CreateFont(-18, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Consolas");
    
    hMetaFont_ = gdiManager_->CreateFont(-14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    hSidebarTitleFont_ = gdiManager_->CreateFont(-18, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    hSidebarItemFont_ = gdiManager_->CreateFont(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    hSidebarMetaFont_ = gdiManager_->CreateFont(-13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    int width = clientRect.right - clientRect.left;
    int height = clientRect.bottom - clientRect.top;
    
    // Layout ban đầu giống OnSize: xét theo việc đã có message hay chưa và trạng thái animate
    bool initialLayout = chatViewState_.messages.empty() && !chatViewState_.isAnimating;

    // Main content area: khi có sidebar thì nội dung chính bắt đầu từ sidebarWidth_
    int contentLeft = sidebarVisible_ ? sidebarWidth_ : 0;
    int contentWidth = width - contentLeft;
    if (contentWidth < 0) contentWidth = 0;

    int inputWidth = static_cast<int>(contentWidth * 0.7); // 70% of main content width
    int inputHeight = 60;
    int inputX = contentLeft + (contentWidth - inputWidth) / 2;
    int inputY;

    int centerY = height / 2 + 40;
    int bottomY = height - inputHeight - 20; // 20px from bottom
    if (centerY + inputHeight + 20 > height) {
        centerY = bottomY;
    }

    if (chatViewState_.isAnimating) {
        chatViewState_.animCurrentY = centerY;
        chatViewState_.animTargetY = bottomY;
        inputY = chatViewState_.animCurrentY;
    } else if (initialLayout) {
        inputY = centerY;
        chatViewState_.animCurrentY = inputY;
        chatViewState_.animTargetY = inputY;
    } else {
        inputY = bottomY;
        chatViewState_.animCurrentY = inputY;
        chatViewState_.animTargetY = inputY;
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

    // Initialize logical send button rect
    sendButtonRect_.left   = buttonX;
    sendButtonRect_.top    = buttonY;
    sendButtonRect_.right  = buttonX + buttonSize;
    sendButtonRect_.bottom = buttonY + buttonSize;

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
        swprintf_s(errorMsg, UiStrings::Get(IDS_ERROR_INPUT_CREATE_FAILED).c_str(), error);
        MessageBoxW(hwnd_, errorMsg, UiStrings::Get(IDS_ERROR_DIALOG_TITLE).c_str(), MB_OK | MB_ICONERROR);
    }
    
    // Set font and colors
    SendMessage(hChatInput_, WM_SETFONT, (WPARAM)hInputFont_->Get(), TRUE);
    
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

    // Khởi tạo rect cho nút "Chat Mới" trong sidebar (vẽ custom, không tạo child window)
    {
        int headerH = theme_.headerHeight;
        int marginX = 16;
        int marginY = 12;
        int newBtnHeight = 34;
        int newBtnWidth = sidebarWidth_ - marginX * 2;
        if (newBtnWidth < 140) newBtnWidth = 140;
        newSessionButtonRect_.left = marginX;
        newSessionButtonRect_.top = headerH + marginY;
        newSessionButtonRect_.right = newSessionButtonRect_.left + newBtnWidth;
        newSessionButtonRect_.bottom = newSessionButtonRect_.top + newBtnHeight;
    }
    
    // Update window
    UpdateWindow(hwnd_);
    
    // Start health check timer (check every 10 seconds)
    healthCheckTimerId_ = SetTimer(hwnd_, 2, 10000, NULL);
    // Initial health check
    CheckHealthStatus();
    
    // Delayed initialization
    PostMessage(hwnd_, WM_USER + 1, 0, 0);
}