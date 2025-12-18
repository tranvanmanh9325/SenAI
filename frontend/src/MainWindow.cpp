#include <windows.h>
#include "MainWindow.h"
#include <sstream>
#include <commctrl.h>
#include <uxtheme.h>
#include <dwmapi.h>
#include <string>

// Helper functions to convert between UTF-16 (Windows wide) and UTF-8 (backend)
namespace {
    std::string WideToUtf8(const std::wstring& wstr) {
        if (wstr.empty()) return {};
        int sizeNeeded = WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), -1, nullptr, 0, nullptr, nullptr);
        if (sizeNeeded <= 0) return {};
        std::string result(sizeNeeded - 1, '\0'); // exclude terminating null
        WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), -1, result.data(), sizeNeeded - 1, nullptr, nullptr);
        return result;
    }

    std::wstring Utf8ToWide(const std::string& str) {
        if (str.empty()) return {};
        int sizeNeeded = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), -1, nullptr, 0);
        if (sizeNeeded <= 0) return {};
        std::wstring result(sizeNeeded - 1, L'\0'); // exclude terminating null
        MultiByteToWideChar(CP_UTF8, 0, str.c_str(), -1, result.data(), sizeNeeded - 1);
        return result;
    }
}

#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "uxtheme.lib")
#pragma comment(lib, "dwmapi.lib")

MainWindow::MainWindow() 
    : hwnd_(NULL), hInstance_(NULL), sessionId_("default_session"),
      hDarkBrush_(NULL), hInputBrush_(NULL), hInputPen_(NULL),
      hTitleFont_(NULL), hInputFont_(NULL),
      windowWidth_(900), windowHeight_(700), showPlaceholder_(true) {
    // Generate session ID
    sessionId_ = "session_" + std::to_string(GetTickCount());
    
    // Initialize input rect
    inputRect_ = {0, 0, 0, 0};
}

MainWindow::~MainWindow() {
    if (hDarkBrush_) DeleteObject(hDarkBrush_);
    if (hInputBrush_) DeleteObject(hInputBrush_);
    if (hInputPen_) DeleteObject(hInputPen_);
    if (hTitleFont_) DeleteObject(hTitleFont_);
    if (hInputFont_) DeleteObject(hInputFont_);
}

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
    
    // Create brushes and pens for dark theme
    hDarkBrush_ = CreateSolidBrush(RGB(18, 18, 18)); // Very dark gray
    hInputBrush_ = CreateSolidBrush(RGB(30, 30, 30)); // Dark gray for input
    hInputPen_ = CreatePen(PS_SOLID, 1, RGB(60, 60, 60)); // Border color
    
    hwnd_ = CreateWindowExW(
        0, // Remove WS_EX_LAYERED for now
        CLASS_NAME,
        L"SenAI",
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
            if (wParam == VK_RETURN && GetFocus() == hChatInput_) {
                SendChatMessage();
                return 0;
            }
            break;
            
        case WM_SIZE:
            OnSize();
            return 0;
            
        case WM_PAINT:
            OnPaint();
            return 0;
            
        case WM_ERASEBKGND:
            OnEraseBkgnd((HDC)wParam);
            return 1;
            
        case WM_CTLCOLOREDIT: {
            HDC hdc = (HDC)wParam;
            SetBkMode(hdc, TRANSPARENT);
            SetTextColor(hdc, RGB(255, 255, 255));
            return (LRESULT)GetStockObject(NULL_BRUSH); // Transparent background
        }
        case WM_CTLCOLORSTATIC: {
            HDC hdc = (HDC)wParam;
            SetBkColor(hdc, RGB(30, 30, 30));
            SetTextColor(hdc, RGB(255, 255, 255));
            return (LRESULT)hInputBrush_;
        }
            
        case WM_CLOSE:
            DestroyWindow(hwnd_);
            return 0;
            
        case WM_DESTROY:
            PostQuitMessage(0);
            return 0;
    }
    
    // Ensure we always call the wide-character default window procedure
    return DefWindowProcW(hwnd_, uMsg, wParam, lParam);
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
    
    // Create chat input (single line, will be visually centered by padding)
    int inputPaddingY = 16; // vertical padding inside rounded rect
    hChatInput_ = CreateWindowW(L"EDIT", L"",
        WS_CHILD | WS_VISIBLE | ES_LEFT | ES_AUTOHSCROLL,
        inputX + 50, inputY + inputPaddingY, inputWidth - 100, inputHeight - 2 * inputPaddingY,
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
    
    // Update window
    UpdateWindow(hwnd_);
    
    // Delayed initialization
    PostMessage(hwnd_, WM_USER + 1, 0, 0);
}

void MainWindow::OnCommand(WPARAM wParam) {
    if (LOWORD(wParam) == 1001) { // Chat input
        if (HIWORD(wParam) == EN_CHANGE) {
            wchar_t buffer[1024];
            GetWindowTextW(hChatInput_, buffer, static_cast<int>(sizeof(buffer) / sizeof(wchar_t)));
            showPlaceholder_ = (buffer[0] == L'\0');
            InvalidateRect(hwnd_, &inputRect_, FALSE);
        }
    }
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
    
    // Update input control position (keep visually centered)
    if (hChatInput_) {
        int inputPaddingY = 16;
        SetWindowPos(hChatInput_, NULL,
                     inputX + 50, inputY + inputPaddingY,
                     inputWidth - 100, inputHeight - 2 * inputPaddingY,
                     SWP_NOZORDER);
    }
    
    InvalidateRect(hwnd_, NULL, TRUE);
}

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
        // +50 giống với vị trí control EDIT, +3 để bù margin bên trong EDIT
        textRect.left += 53;
        textRect.right -= 50;

        const wchar_t* placeholder = L"Hỏi bất kỳ điều gì";
        DrawTextW(hdc, placeholder, -1, &textRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
    }
    
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
}

void MainWindow::SendChatMessage() {
    wchar_t buffer[1024];
    GetWindowTextW(hChatInput_, buffer, static_cast<int>(sizeof(buffer) / sizeof(wchar_t)));
    
    if (buffer[0] == L'\0') return;
    
    std::wstring wmessage(buffer);
    std::string message = WideToUtf8(wmessage);

    ClearEdit(hChatInput_);
    showPlaceholder_ = true;
    InvalidateRect(hwnd_, &inputRect_, FALSE);
    
    // Send message to backend
    std::string response = httpClient_.sendMessage(message, sessionId_);
    
    // Append to history (display using Unicode)
    std::wstring historyUser = L"Bạn: " + wmessage + L"\r\n";
    std::wstring historyAi = L"AI: " + Utf8ToWide(response) + L"\r\n\r\n";
    AppendTextToEdit(hChatHistory_, historyUser);
    AppendTextToEdit(hChatHistory_, historyAi);
}

void MainWindow::RefreshConversations() {
    std::string conversations = httpClient_.getConversations(sessionId_);
    ClearEdit(hChatHistory_);
    AppendTextToEdit(hChatHistory_, Utf8ToWide(conversations));
}

void MainWindow::RefreshTasks() {
    // Not used in new UI
}

void MainWindow::CreateTask() {
    // Not used in new UI
}

void MainWindow::AppendTextToEdit(HWND hEdit, const std::wstring& text) {
    int len = GetWindowTextLengthW(hEdit);
    SendMessageW(hEdit, EM_SETSEL, len, len);
    SendMessageW(hEdit, EM_REPLACESEL, FALSE, (LPARAM)text.c_str());
}

void MainWindow::ClearEdit(HWND hEdit) {
    SetWindowTextW(hEdit, L"");
}