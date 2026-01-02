#include <windows.h>
#include "MainWindow.h"
#include "UiConstants.h"
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
    
    using namespace UiConstants;
    using namespace UiConfig;
    
    UIConfig config = GetDefaultConfig();
    const wchar_t* CLASS_NAME = config.window.className.c_str();
    
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
        CW_USEDEFAULT, CW_USEDEFAULT, 
        config.window.defaultWidth, config.window.defaultHeight,
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
        // Handle search edit control Enter key
        if (pThis && hwnd == pThis->hSearchEdit_ && wParam == VK_RETURN) {
            if (!pThis->searchResults_.empty()) {
                pThis->NavigateToSearchResult(1); // Navigate to next result
            }
            return 0;
        }
        
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
            HandleKeyDown(wParam);
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
                HandleSidebarMouseWheel(wParam);
                return 0;
            }

            // Scroll chat messages with mouse wheel
            HandleChatMouseWheel(wParam);
            return 0;
        }

        case WM_TIMER:
            HandleTimer(wParam);
            break;
            
        case WM_ERASEBKGND:
            return OnEraseBkgnd((HDC)wParam);

        case WM_LBUTTONDOWN:
            HandleLeftButtonDown(lParam);
            break;

        case WM_MOUSEMOVE:
            HandleMouseMove(lParam);
            break;
        
        case WM_MOUSELEAVE:
            HandleMouseLeave();
            break;
            
        case WM_CTLCOLOREDIT: {
            HDC hdc = (HDC)wParam;
            HWND hEdit = (HWND)lParam;
            // Set background color to match input field inner color
            SetBkColor(hdc, theme_.colorInputInner);
            SetTextColor(hdc, RGB(255, 255, 255));
            // For search edit, use darker background
            if (hEdit == hSearchEdit_) {
                SetBkColor(hdc, RGB(20, 28, 50));
            }
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