#include <windows.h>
#include "MainWindow.h"
#include <sstream>
#include <commctrl.h>
#include <uxtheme.h>
#include <dwmapi.h>
#include <windowsx.h> // GET_WHEEL_DELTA_WPARAM

#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "uxtheme.lib")
#pragma comment(lib, "dwmapi.lib")

bool MainWindow::Create(HINSTANCE hInstance) {
    hInstance_ = hInstance;
    
    // Initialize common controls
    INITCOMMONCONTROLSEX icex;
    icex.dwSize = sizeof(INITCOMMONCONTROLSEX);
    icex.dwICC = ICC_STANDARD_CLASSES;
    InitCommonControlsEx(&icex);
    
    const wchar_t CLASS_NAME[] = L"SenAIMainWindow";
    
    // Check if class is already registered
    WNDCLASSW wc = {};
    if (!GetClassInfoW(hInstance, CLASS_NAME, &wc)) {
        wc = {};
        wc.lpfnWndProc = WindowProc;
        wc.hInstance = hInstance;
        wc.lpszClassName = CLASS_NAME;
        wc.hbrBackground = NULL; // We'll paint our own background
        wc.hCursor = LoadCursor(NULL, IDC_ARROW);
        wc.hIcon = LoadIcon(NULL, IDI_APPLICATION);
        wc.style = CS_HREDRAW | CS_VREDRAW;
        
        if (!RegisterClassW(&wc)) {
            DWORD error = GetLastError();
            if (error != ERROR_CLASS_ALREADY_EXISTS) {
                return false;
            }
        }
    }
    
    // Initialize GDI Resource Manager
    gdiManager_ = std::make_unique<GDIResourceManager>();
    
    // Create and cache brushes and pens for dark/futuristic theme
    hDarkBrush_ = gdiManager_->CreateSolidBrush(theme_.colorBackground);
    hInputBrush_ = gdiManager_->CreateSolidBrush(theme_.colorInputInner);
    hInputPen_ = gdiManager_->CreatePen(PS_SOLID, 1, theme_.colorInputStroke);
    
    hwnd_ = CreateWindowExW(
        0, // Remove WS_EX_LAYERED for now
        CLASS_NAME,
        UiStrings::Get(IDS_APP_TITLE).c_str(),
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, windowWidth_, windowHeight_,
        NULL, NULL, hInstance, this
    );
    
    if (hwnd_ == NULL) {
        DWORD error = GetLastError();
        return false;
    }
    
    // Set window to dark mode (Windows 10/11)
    BOOL darkMode = TRUE;
    if (FAILED(DwmSetWindowAttribute(hwnd_, 20, &darkMode, sizeof(darkMode)))) {
        // Fallback for older Windows versions
        DwmSetWindowAttribute(hwnd_, 19, &darkMode, sizeof(darkMode)); // DWMWA_USE_IMMERSIVE_DARK_MODE (older)
    }
    
    // Ensure window is visible and on top
    ShowWindow(hwnd_, SW_SHOW);
    SetForegroundWindow(hwnd_);
    UpdateWindow(hwnd_);
    
    return true;
}

void MainWindow::Show(int nCmdShow) {
    if (hwnd_) {
        ShowWindow(hwnd_, SW_SHOW);
        SetForegroundWindow(hwnd_);
        BringWindowToTop(hwnd_);
        UpdateWindow(hwnd_);
        InvalidateRect(hwnd_, NULL, TRUE);
    }
}

int MainWindow::Run() {
    MSG msg = {};
    // Use explicit wide-character message APIs to avoid ANSI conversions
    while (GetMessageW(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return 0;
}

LRESULT CALLBACK MainWindow::WindowProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    MainWindow* pThis = nullptr;
    
    if (uMsg == WM_NCCREATE) {
        CREATESTRUCT* pCreate = (CREATESTRUCT*)lParam;
        pThis = (MainWindow*)pCreate->lpCreateParams;
        SetWindowLongPtr(hwnd, GWLP_USERDATA, (LONG_PTR)pThis);
        // Set hwnd_ immediately
        if (pThis) {
            pThis->hwnd_ = hwnd;
        }
        // Return TRUE to allow window creation
        return TRUE;
    } else {
        pThis = (MainWindow*)GetWindowLongPtr(hwnd, GWLP_USERDATA);
    }
    
    if (pThis) {
        return pThis->HandleMessage(uMsg, wParam, lParam);
    }
    
    // Fallback to wide-character default window procedure
    return DefWindowProcW(hwnd, uMsg, wParam, lParam);
}

LRESULT CALLBACK MainWindow::EditProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    MainWindow* pThis = (MainWindow*)GetWindowLongPtr(GetParent(hwnd), GWLP_USERDATA);
    
    if (uMsg == WM_KEYDOWN) {
        // Handle Ctrl+A to select all text
        if (wParam == 'A' && (GetKeyState(VK_CONTROL) & 0x8000)) {
            SendMessageW(hwnd, EM_SETSEL, 0, -1);
            return 0;
        }
        // Handle Ctrl+Enter to send message (if enabled)
        if (wParam == VK_RETURN && pThis && (GetKeyState(VK_CONTROL) & 0x8000)) {
            if (pThis->enableCtrlEnterToSend_) {
                pThis->SendChatMessage();
                return 0;
            }
        }
        // Handle Enter to send message (only if Ctrl+Enter is disabled)
        if (wParam == VK_RETURN && pThis) {
            if (!pThis->enableCtrlEnterToSend_) {
                pThis->SendChatMessage();
                return 0;
            }
            // If Ctrl+Enter is enabled, Enter should insert newline (default behavior)
        }
    }
    
    // Handle focus changes to update placeholder visibility
    if (uMsg == WM_SETFOCUS || uMsg == WM_KILLFOCUS) {
        if (pThis) {
            // Invalidate input field to redraw placeholder
            InvalidateRect(pThis->hwnd_, &pThis->inputRect_, FALSE);
        }
    }
    
    // Handle paint to ensure placeholder is visible when edit is empty
    if (uMsg == WM_PAINT && pThis) {
        // Let edit control paint first
        LRESULT result = 0;
        if (pThis->originalEditProc_) {
            result = CallWindowProcW(pThis->originalEditProc_, hwnd, uMsg, wParam, lParam);
        } else {
            result = DefWindowProcW(hwnd, uMsg, wParam, lParam);
        }
        
        // After edit control paints, check if we need to draw placeholder
        if (pThis->chatViewState_.showPlaceholder && GetFocus() != hwnd) {
            wchar_t buffer[1024] = {0};
            GetWindowTextW(hwnd, buffer, static_cast<int>(sizeof(buffer) / sizeof(wchar_t)));
            if (buffer[0] == L'\0') {
                // Draw placeholder on top
                HDC hdc = GetDC(hwnd);
                SetBkMode(hdc, TRANSPARENT);
                SetTextColor(hdc, pThis->theme_.colorPlaceholder);
                SelectObject(hdc, pThis->hInputFont_->Get());
                
                RECT clientRect;
                GetClientRect(hwnd, &clientRect);
                clientRect.left += 2; // Padding
                
                DrawTextW(hdc, UiStrings::Get(IDS_INPUT_PLACEHOLDER).c_str(), -1, &clientRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
                ReleaseDC(hwnd, hdc);
            }
        }
        
        return result;
    }
    
    // Call original window procedure
    if (pThis && pThis->originalEditProc_) {
        return CallWindowProcW(pThis->originalEditProc_, hwnd, uMsg, wParam, lParam);
    }
    
    return DefWindowProcW(hwnd, uMsg, wParam, lParam);
}

LRESULT MainWindow::HandleMessage(UINT uMsg, WPARAM wParam, LPARAM lParam) {
    switch (uMsg) {
        case WM_CREATE:
            OnCreate();
            return 0;
            
        case WM_USER + 1:
            // Delayed initialization
            RefreshConversations();
            return 0;
            
        case WM_COMMAND:
            OnCommand(wParam);
            return 0;
            
        case WM_KEYDOWN:
            // Global shortcuts
            if (wParam == VK_ESCAPE) {
                // If input has focus, clear it
                if (GetFocus() == hChatInput_) {
                    ClearEdit(hChatInput_);
                    chatViewState_.showPlaceholder = true;
                    InvalidateRect(hwnd_, &inputRect_, FALSE);
                    return 0;
                } else {
                    // Esc outside input -> confirm exit with custom dark theme dialog
                    if (ShowExitConfirmationDialog()) {
                        PostMessage(hwnd_, WM_CLOSE, 0, 0);
                    }
                    return 0;
                }
            }
            if (wParam == 'L' && (GetKeyState(VK_CONTROL) & 0x8000)) {
                // Ctrl+L -> focus input
                SetFocus(hChatInput_);
                return 0;
            }
            // Ctrl+Enter handling is done in EditProc
            break;
            
        case WM_SIZE:
            OnSize();
            return 0;
            
        case WM_PAINT:
            OnPaint();
            return 0;

        case WM_MOUSEWHEEL: {
            POINT pt;
            GetCursorPos(&pt);
            ScreenToClient(hwnd_, &pt);

            // Sidebar scroll when mouse is over sidebar
            if (sidebarVisible_ && pt.x >= 0 && pt.x < sidebarWidth_) {
                int delta = GET_WHEEL_DELTA_WPARAM(wParam);
                int pixelsPerNotch = 50;
                int step = (delta / WHEEL_DELTA) * pixelsPerNotch;

                RECT clientRect;
                GetClientRect(hwnd_, &clientRect);
                int headerH = theme_.headerHeight;
                int sidebarH = clientRect.bottom - headerH;

                int itemHeight = 75;
                int titleTop = (newSessionButtonRect_.bottom > 0)
                    ? newSessionButtonRect_.bottom + 12
                    : headerH + 12;
                int titleHeight = 28;
                int startY = titleTop + titleHeight + 12;

                int visibleHeight = clientRect.bottom - startY;
                if (visibleHeight < 0) visibleHeight = 0;

                int contentHeight = itemHeight * static_cast<int>(conversations_.size());
                int maxScroll = (contentHeight > visibleHeight) ? (contentHeight - visibleHeight) : 0;

                sidebarScrollOffset_ -= step;
                if (sidebarScrollOffset_ < 0) sidebarScrollOffset_ = 0;
                if (sidebarScrollOffset_ > maxScroll) sidebarScrollOffset_ = maxScroll;

                // Chỉ vẽ lại vùng sidebar, tránh ảnh hưởng nút gửi / input để giảm nhấp nháy
                RECT sidebarRect = { 0, headerH, sidebarWidth_, clientRect.bottom };
                InvalidateRect(hwnd_, &sidebarRect, FALSE);
                return 0;
            }

            // Scroll chat messages with mouse wheel
            int delta = GET_WHEEL_DELTA_WPARAM(wParam); // positive when wheel scrolled up
            int pixelsPerNotch = 60; // tune for desired speed
            int step = (delta / WHEEL_DELTA) * pixelsPerNotch;

            // Wheel up = move content up => decrease scrollOffset_
            chatViewState_.scrollOffset -= step;
            if (chatViewState_.scrollOffset < 0) chatViewState_.scrollOffset = 0;

            // User is manually scrolling; stop auto-pinning to bottom
            chatViewState_.autoScrollToBottom = false;

            // Chỉ invalid vùng chat messages, tránh đụng vào input & nút gửi để tránh nhấp nháy
            RECT chatRect;
            int headerH2 = theme_.headerHeight;
            int contentLeft = sidebarVisible_ ? sidebarWidth_ : 0;

            chatRect.left = contentLeft;
            chatRect.top = headerH2;
            chatRect.right = windowWidth_;
            // Giới hạn dưới ngay phía trên ô input
            chatRect.bottom = inputRect_.top > 0 ? inputRect_.top - 4 : windowHeight_;

            // Đảm bảo rect hợp lệ trước khi vẽ
            if (chatRect.bottom < chatRect.top) {
                chatRect.bottom = chatRect.top;
            }

            InvalidateRect(hwnd_, &chatRect, FALSE);
            return 0;
        }

        case WM_TIMER:
            if (wParam == 3) {
                // Copy feedback timer - reset checkmark back to copy icon
                if (copiedMessageIndex_ >= 0) {
                    RECT iconRect = GetCopyIconRect(copiedMessageIndex_);
                    InflateRect(&iconRect, 4, 4);
                    InvalidateRect(hwnd_, &iconRect, FALSE);
                    copiedMessageIndex_ = -1;
                }
                if (copyFeedbackTimerId_ != 0) {
                    KillTimer(hwnd_, copyFeedbackTimerId_);
                    copyFeedbackTimerId_ = 0;
                }
                return 0;
            }
            if (wParam == 1 && chatViewState_.isAnimating) {
                // Animate input Y toward target with smooth easing interpolation
                int remaining = chatViewState_.animTargetY - chatViewState_.animCurrentY;
                if (remaining != 0) {
                    // Smooth ease-in-out interpolation: t^2 * (3 - 2*t) for smooth acceleration/deceleration
                    // Calculate progress: 0.0 to 1.0
                    int totalDistance = chatViewState_.animTargetY - chatViewState_.animStartY;
                    if (totalDistance == 0) {
                        chatViewState_.animCurrentY = chatViewState_.animTargetY;
                        chatViewState_.isAnimating = false;
                        if (chatViewState_.animTimerId_ != 0) {
                            KillTimer(hwnd_, chatViewState_.animTimerId_);
                            chatViewState_.animTimerId_ = 0;
                        }
                        OnSize();
                        return 0;
                    }
                    
                    float progress = static_cast<float>(chatViewState_.animCurrentY - chatViewState_.animStartY) / static_cast<float>(totalDistance);
                    // Clamp progress to [0, 1]
                    if (progress < 0.0f) progress = 0.0f;
                    if (progress > 1.0f) progress = 1.0f;
                    
                    // Smoothstep interpolation: t^2 * (3 - 2*t)
                    float smoothProgress = progress * progress * (3.0f - 2.0f * progress);
                    
                    // Calculate new position
                    int newY = chatViewState_.animStartY + static_cast<int>(smoothProgress * totalDistance);
                    
                    // Ensure we don't overshoot
                    if ((totalDistance > 0 && newY >= chatViewState_.animTargetY) ||
                        (totalDistance < 0 && newY <= chatViewState_.animTargetY)) {
                        chatViewState_.animCurrentY = chatViewState_.animTargetY;
                        chatViewState_.isAnimating = false;
                        if (chatViewState_.animTimerId_ != 0) {
                            KillTimer(hwnd_, chatViewState_.animTimerId_);
                            chatViewState_.animTimerId_ = 0;
                        }
                    } else {
                        chatViewState_.animCurrentY = newY;
                    }
                    
                    // Re-layout controls at new position
                    OnSize();
                }
                return 0;
            }
            if (wParam == 2) {
                // Health check timer
                CheckHealthStatus();
                return 0;
            }
            break;
            
        case WM_ERASEBKGND:
            return OnEraseBkgnd((HDC)wParam);

        case WM_LBUTTONDOWN: {
            POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };
            
            // Check if click is on settings icon
            if (PtInRect(&settingsIconRect_, pt)) {
                HandleSettingsIconClick();
                return 0;
            }

            // Check click on custom send button (vẽ trực tiếp, không dùng child window)
            if (sendButtonRect_.right > sendButtonRect_.left &&
                sendButtonRect_.bottom > sendButtonRect_.top &&
                PtInRect(&sendButtonRect_, pt)) {
                SendChatMessage();
                return 0;
            }
            
            // Check click on copy icon
            if (hoveredCopyIconIndex_ >= 0 && 
                static_cast<size_t>(hoveredCopyIconIndex_) < chatViewState_.messages.size()) {
                RECT copyIconRect = GetCopyIconRect(hoveredCopyIconIndex_);
                if (PtInRect(&copyIconRect, pt)) {
                    CopyMessageToClipboard(hoveredCopyIconIndex_);
                    return 0;
                }
            }
            
            // Check double-click on message bubble to copy
            DWORD currentTime = GetTickCount();
            if (hoveredMessageIndex_ >= 0 && 
                static_cast<size_t>(hoveredMessageIndex_) < chatViewState_.messages.size()) {
                if (lastClickIndex_ == hoveredMessageIndex_ && 
                    (currentTime - lastClickTime_) < 500) { // 500ms double-click window
                    CopyMessageToClipboard(hoveredMessageIndex_);
                    lastClickTime_ = 0;
                    lastClickIndex_ = -1;
                    return 0;
                } else {
                    lastClickTime_ = currentTime;
                    lastClickIndex_ = hoveredMessageIndex_;
                }
            }
            
            // Check if click is in sidebar
            if (sidebarVisible_ && pt.x >= 0 && pt.x < sidebarWidth_) {
                int headerH = theme_.headerHeight;

                // Hit test nút "Chat Mới" (vẽ custom, không dùng child window)
                if (newSessionButtonRect_.right > newSessionButtonRect_.left &&
                    newSessionButtonRect_.bottom > newSessionButtonRect_.top &&
                    PtInRect(&newSessionButtonRect_, pt)) {
                    // Tái sử dụng logic cũ qua WM_COMMAND 1004
                    SendMessage(hwnd_, WM_COMMAND, MAKELONG(1004, BN_CLICKED), 0);
                    return 0;
                }
                int itemHeight = 75;
                // Align click hit-test with rendered layout:
                // - button top = headerH + 12
                // - button height = 34
                // - title top = buttonBottom + 12
                // - title height = 28
                // - list starts at titleBottom + 12
                int titleTop = (newSessionButtonRect_.bottom > 0)
                    ? newSessionButtonRect_.bottom + 12
                    : headerH + 12;
                int titleHeight = 28;
                int startY = titleTop + titleHeight + 12;
                int clickY = pt.y;
                
                if (clickY >= startY) {
                    int itemIndex = (clickY - startY + sidebarScrollOffset_) / itemHeight;
                    if (itemIndex >= 0 && static_cast<size_t>(itemIndex) < conversations_.size()) {
                        LoadConversationBySessionId(conversations_[itemIndex].rawSessionId);
                        selectedConversationIndex_ = itemIndex;
                        InvalidateRect(hwnd_, NULL, TRUE);
                    }
                }
            }
            break;
        }

        case WM_MOUSEMOVE: {
            POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };

            // Track hover state for custom send button (không dùng child window)
            if (sendButtonRect_.right > sendButtonRect_.left &&
                sendButtonRect_.bottom > sendButtonRect_.top) {
                bool hovering = PtInRect(&sendButtonRect_, pt);
                if (hovering != isSendButtonHover_) {
                    isSendButtonHover_ = hovering;
                    InvalidateRect(hwnd_, &sendButtonRect_, FALSE);
                }
            }

            // Track hover state for "Chat Mới" button (custom drawn)
            if (newSessionButtonRect_.right > newSessionButtonRect_.left &&
                newSessionButtonRect_.bottom > newSessionButtonRect_.top) {
                bool hovering = PtInRect(&newSessionButtonRect_, pt);
                if (hovering != isNewSessionButtonHover_) {
                    isNewSessionButtonHover_ = hovering;
                    InvalidateRect(hwnd_, &newSessionButtonRect_, FALSE);
                }
            }
            
            // Track hover state for settings icon
            bool settingsHovering = PtInRect(&settingsIconRect_, pt);
            if (settingsHovering != isSettingsIconHover_) {
                isSettingsIconHover_ = settingsHovering;
                InvalidateRect(hwnd_, &settingsIconRect_, FALSE);
            }

            // Track hover state for sidebar conversation items
            if (sidebarVisible_ && pt.x >= 0 && pt.x < sidebarWidth_) {
                int headerH = theme_.headerHeight;
                int itemHeight = 75;
                int titleTop = (newSessionButtonRect_.bottom > 0)
                    ? newSessionButtonRect_.bottom + 12
                    : headerH + 12;
                int titleHeight = 28;
                int startY = titleTop + titleHeight + 12;

                int offsetY = pt.y - startY + sidebarScrollOffset_;
                int newHover = -1;
                if (offsetY >= 0) {
                    int idx = offsetY / itemHeight;
                    if (idx >= 0 && static_cast<size_t>(idx) < conversations_.size()) {
                        newHover = idx;
                    }
                }
                if (newHover != hoveredConversationIndex_) {
                    hoveredConversationIndex_ = newHover;
                    InvalidateRect(hwnd_, NULL, FALSE);
                }
            } else {
                if (hoveredConversationIndex_ != -1) {
                    hoveredConversationIndex_ = -1;
                    InvalidateRect(hwnd_, NULL, FALSE);
                }
            }
            
            // Update message hover (this also handles tooltip)
            UpdateMessageHover(pt.x, pt.y);
            
            break;
        }
        
        case WM_MOUSELEAVE: {
            // Hide tooltip when mouse leaves window
            HideMessageTooltip();
            int oldHovered = hoveredMessageIndex_;
            int oldCopyHovered = hoveredCopyIconIndex_;
            hoveredMessageIndex_ = -1;
            hoveredCopyIconIndex_ = -1;
            if (oldHovered != -1 || oldCopyHovered != -1) {
                InvalidateRect(hwnd_, NULL, FALSE);
            }
            break;
        }
            
        case WM_CTLCOLOREDIT: {
            HDC hdc = (HDC)wParam;
            // Set background color to match input field inner color
            SetBkColor(hdc, theme_.colorInputInner);
            SetTextColor(hdc, RGB(255, 255, 255));
            // Return input brush để edit control có cùng màu với input field
            return (LRESULT)hInputBrush_->Get();
        }
        case WM_CTLCOLORBTN: {
            HDC hdc = (HDC)wParam;
            SetBkMode(hdc, TRANSPARENT);
            SetTextColor(hdc, RGB(255, 255, 255));
            return (LRESULT)GetStockObject(NULL_BRUSH); // Let our custom painting handle background
        }
        case WM_DRAWITEM: {
            // Không còn dùng owner-draw cho nút gửi và "Chat Mới"
            break;
        }
        case WM_CTLCOLORSTATIC: {
            HDC hdc = (HDC)wParam;
            SetBkColor(hdc, RGB(30, 30, 30));
            SetTextColor(hdc, RGB(255, 255, 255));
            return (LRESULT)hInputBrush_->Get();
        }
            
        case WM_CLOSE:
            DestroyWindow(hwnd_);
            return 0;
            
        case WM_DESTROY:
            HideMessageTooltip();
            if (copyFeedbackTimerId_ != 0) {
                KillTimer(hwnd_, copyFeedbackTimerId_);
                copyFeedbackTimerId_ = 0;
            }
            PostQuitMessage(0);
            return 0;
    }
    
    // Ensure we always call the wide-character default window procedure
    return DefWindowProcW(hwnd_, uMsg, wParam, lParam);
}

// Logic functions (OnCommand, SendChatMessage, RefreshConversations, etc.)
// are implemented in MainWindowLogic.cpp to keep this file focused on
// window creation and message routing.