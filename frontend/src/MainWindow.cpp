#include <windows.h>
#include "MainWindow.h"
#include <sstream>
#include <commctrl.h>
#include <uxtheme.h>
#include <dwmapi.h>
#include <string>
#include <fstream>
#include <algorithm>
#include <cctype>
#include <vector>

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

    std::string GetEnvironmentVariable(const std::string& name) {
        // Convert to wide string for Windows API
        std::wstring wname = Utf8ToWide(name);
        wchar_t* buffer = nullptr;
        size_t size = 0;
        if (_wgetenv_s(&size, nullptr, 0, wname.c_str()) == 0 && size > 0) {
            buffer = new wchar_t[size];
            if (_wgetenv_s(&size, buffer, size, wname.c_str()) == 0) {
                std::string result = WideToUtf8(std::wstring(buffer));
                delete[] buffer;
                return result;
            }
            delete[] buffer;
        }
        return "";
    }

    // Trim whitespace from string
    std::string Trim(const std::string& str) {
        size_t first = str.find_first_not_of(" \t\n\r");
        if (first == std::string::npos) return "";
        size_t last = str.find_last_not_of(" \t\n\r");
        return str.substr(first, (last - first + 1));
    }

    // Get executable directory path
    std::string GetExecutableDirectory() {
        char buffer[MAX_PATH];
        DWORD length = GetModuleFileNameA(NULL, buffer, MAX_PATH);
        if (length == 0) {
            return "";
        }
        std::string exePath(buffer);
        size_t lastSlash = exePath.find_last_of("\\/");
        if (lastSlash != std::string::npos) {
            return exePath.substr(0, lastSlash + 1);
        }
        return "";
    }

    // Read .env file and get value for a key
    // Tries multiple locations: current directory, executable directory, and parent directories
    std::string ReadEnvFile(const std::string& key) {
        // List of possible .env file locations
        std::vector<std::string> envPaths = {
            ".env",                                    // Current directory
            GetExecutableDirectory() + ".env",         // Executable directory
            GetExecutableDirectory() + "../.env",     // Parent of executable directory
            GetExecutableDirectory() + "../../.env",   // Two levels up (for build/bin/)
            GetExecutableDirectory() + "../../../.env" // Three levels up
        };

        for (const auto& envPath : envPaths) {
            std::ifstream file(envPath);
            if (!file.is_open()) {
                continue;
            }

            std::string line;
            while (std::getline(file, line)) {
                // Skip empty lines and comments
                line = Trim(line);
                if (line.empty() || line[0] == '#') {
                    continue;
                }

                // Find the equals sign
                size_t pos = line.find('=');
                if (pos == std::string::npos) {
                    continue;
                }

                std::string fileKey = Trim(line.substr(0, pos));
                std::string value = Trim(line.substr(pos + 1));

                // Remove quotes if present
                if (!value.empty() && ((value[0] == '"' && value.back() == '"') || 
                                      (value[0] == '\'' && value.back() == '\''))) {
                    value = value.substr(1, value.length() - 2);
                }

                if (fileKey == key) {
                    file.close();
                    return value;
                }
            }

            file.close();
        }

        return "";
    }

    std::wstring GetCurrentTimeW() {
        SYSTEMTIME st;
        GetLocalTime(&st);
        wchar_t buf[16];
        swprintf_s(buf, L"%02d:%02d", st.wHour, st.wMinute);
        return std::wstring(buf);
    }
}

#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "uxtheme.lib")
#pragma comment(lib, "dwmapi.lib")

MainWindow::MainWindow() 
    : hwnd_(NULL), hInstance_(NULL), sessionId_("default_session"),
      hDarkBrush_(NULL), hInputBrush_(NULL), hInputPen_(NULL),
      hTitleFont_(NULL), hInputFont_(NULL),
      windowWidth_(900), windowHeight_(700), showPlaceholder_(true),
      hChatInput_(NULL), hChatHistory_(NULL), hSendButton_(NULL),
      originalEditProc_(NULL), scrollOffset_(0) {
    // Generate session ID
    sessionId_ = "session_" + std::to_string(GetTickCount());
    
    // Read API key from .env file (searches multiple locations)
    std::string apiKey = ReadEnvFile("API_KEY");
    // Fallback to environment variable if .env file doesn't have it
    if (apiKey.empty()) {
        apiKey = GetEnvironmentVariable("API_KEY");
    }
    if (!apiKey.empty()) {
        httpClient_.setApiKey(apiKey);
    }
    
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
    
    // Create brushes and pens for dark/futuristic theme
    hDarkBrush_ = CreateSolidBrush(RGB(11, 16, 33)); // Deep navy background
    hInputBrush_ = CreateSolidBrush(RGB(20, 26, 44)); // Dark glass base
    hInputPen_ = CreatePen(PS_SOLID, 1, RGB(74, 215, 255)); // Cyan outline
    
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

LRESULT CALLBACK MainWindow::EditProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    MainWindow* pThis = (MainWindow*)GetWindowLongPtr(GetParent(hwnd), GWLP_USERDATA);
    
    if (uMsg == WM_KEYDOWN) {
        // Handle Ctrl+A to select all text
        if (wParam == 'A' && (GetKeyState(VK_CONTROL) & 0x8000)) {
            SendMessageW(hwnd, EM_SETSEL, 0, -1);
            return 0;
        }
        // Handle Enter to send message
        if (wParam == VK_RETURN && pThis) {
            pThis->SendChatMessage();
            return 0;
        }
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

        case WM_TIMER:
            if (wParam == 1 && isAnimating_) {
                // Animate input Y toward target
                int step = 12; // px per tick
                if (animCurrentY_ < animTargetY_) {
                    animCurrentY_ = (std::min)(animCurrentY_ + step, animTargetY_);
                }
                // Re-layout controls at new position
                OnSize();
                if (animCurrentY_ >= animTargetY_) {
                    isAnimating_ = false;
                    if (animTimerId_) {
                        KillTimer(hwnd_, animTimerId_);
                        animTimerId_ = 0;
                    }
                }
                return 0;
            }
            break;
            
        case WM_ERASEBKGND:
            OnEraseBkgnd((HDC)wParam);
            return 1;
            
        case WM_CTLCOLOREDIT: {
            HDC hdc = (HDC)wParam;
            SetBkMode(hdc, TRANSPARENT);
            SetTextColor(hdc, RGB(255, 255, 255));
            return (LRESULT)GetStockObject(NULL_BRUSH); // Transparent background
        }
        case WM_CTLCOLORBTN: {
            HDC hdc = (HDC)wParam;
            SetBkColor(hdc, RGB(30, 30, 30));
            SetTextColor(hdc, RGB(255, 255, 255));
            return (LRESULT)hInputBrush_;
        }
        case WM_DRAWITEM: {
            if (wParam == 1003) { // Send button
                LPDRAWITEMSTRUCT dis = (LPDRAWITEMSTRUCT)lParam;
                DrawSendButton(dis->hDC, dis->rcItem);
                return TRUE;
            }
            break;
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

void MainWindow::OnCommand(WPARAM wParam) {
    switch (LOWORD(wParam)) {
        case 1001: // Chat input
            if (HIWORD(wParam) == EN_CHANGE) {
                wchar_t buffer[1024];
                GetWindowTextW(hChatInput_, buffer, static_cast<int>(sizeof(buffer) / sizeof(wchar_t)));
                showPlaceholder_ = (buffer[0] == L'\0');
                InvalidateRect(hwnd_, &inputRect_, FALSE);
            }
            break;
        case 1003: // Send button
            if (HIWORD(wParam) == BN_CLICKED) {
                SendChatMessage();
            }
            break;
        default:
            break;
    }
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
    
    // Add user message to vector
    ChatMessage userMsg;
    userMsg.text = wmessage;
    userMsg.isUser = true;
    userMsg.timestamp = GetCurrentTimeW();
    messages_.push_back(userMsg);
    
    // Send message to backend
    std::string response = httpClient_.sendMessage(message, sessionId_);
    
    // Add AI response to vector
    ChatMessage aiMsg;
    aiMsg.text = Utf8ToWide(response);
    aiMsg.isUser = false;
    aiMsg.timestamp = GetCurrentTimeW();
    messages_.push_back(aiMsg);

    // Sau khi đã có messages, khởi động animation đưa input xuống dưới
    animStartY_ = animCurrentY_;
    // Target sẽ được tính trong OnSize dựa trên windowHeight_; tạm cập nhật
    isAnimating_ = true;
    if (animTimerId_) {
        KillTimer(hwnd_, animTimerId_);
    }
    animTimerId_ = SetTimer(hwnd_, 1, 15, NULL); // 15ms ~ 60fps
    
    // Redraw window to show new messages
    InvalidateRect(hwnd_, NULL, TRUE);
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