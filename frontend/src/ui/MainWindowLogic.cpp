#include <windows.h>
#include "MainWindow.h"
#include "JsonParser.h"
#include "ErrorHandler.h"
#include <sstream>
#include <string>
#include <fstream>
#include <algorithm>
#include <cctype>
#include <vector>
#include <map>
#include "MainWindowHelpers.h"
#include <fstream>
// Logic & backend interaction for MainWindow (tách khỏi file MainWindow.cpp để dễ bảo trì)

namespace {
    std::string GetConfigPath() {
        char path[MAX_PATH] = {0};
        if (GetModuleFileNameA(NULL, path, MAX_PATH) == 0) {
            return "senai_frontend.config.json";
        }
        std::string exePath(path);
        size_t pos = exePath.find_last_of("\\/");
        std::string dir = (pos == std::string::npos) ? "" : exePath.substr(0, pos + 1);
        return dir + "senai_frontend.config.json";
    }
}
MainWindow::MainWindow() 
    : hwnd_(NULL), hInstance_(NULL), sessionId_("default_session"),
      // GDI objects are initialized as smart pointers (default to nullptr)
      windowWidth_(900), windowHeight_(700),
      hChatInput_(NULL), hChatHistory_(NULL), hSendButton_(NULL), hNewSessionButton_(NULL),
      originalEditProc_(NULL),
      sidebarWidth_(280), sidebarScrollOffset_(0), selectedConversationIndex_(-1),
      isSendButtonHover_(false), isNewSessionButtonHover_(false), sidebarVisible_(true),
      healthStatus_(HealthStatus::Checking), healthCheckTimerId_(0),
      isSettingsIconHover_(false), hoveredMessageIndex_(-1),
      hoveredCopyIconIndex_(-1), copiedMessageIndex_(-1), copyFeedbackTimerId_(0),
      hTooltipWindow_(NULL), tooltipMessageIndex_(-1),
      enableCtrlEnterToSend_(true), lastClickTime_(0), lastClickIndex_(-1),
      modelName_(L"") {
    configPath_ = GetConfigPath();
    // Generate session ID
    sessionId_ = "session_" + std::to_string(GetTickCount());
    
    // Read API key from .env file (searches multiple locations)
    std::string apiKey = ReadEnvFile("API_KEY");
    // Fallback to environment variable if .env file doesn't have it
    if (apiKey.empty()) {
        apiKey = GetEnvironmentVariableUtf8("API_KEY");
    }
    if (!apiKey.empty()) {
        httpClient_.setApiKey(apiKey);
    }
    
    // Load settings from config file (override defaults if present)
    LoadSettingsFromFile();
    
    // Initialize rects
    inputRect_ = {0, 0, 0, 0};
    newSessionButtonRect_ = {0, 0, 0, 0};
    sendButtonRect_ = {0, 0, 0, 0};
}

MainWindow::~MainWindow() {
    HideMessageTooltip();
    if (copyFeedbackTimerId_ && hwnd_) {
        KillTimer(hwnd_, copyFeedbackTimerId_);
    }
    // Smart pointers will automatically clean up GDI objects
    // No manual DeleteObject needed
    if (healthCheckTimerId_ && hwnd_) {
        KillTimer(hwnd_, healthCheckTimerId_);
    }
}

void MainWindow::OnCommand(WPARAM wParam) {
    switch (LOWORD(wParam)) {
        case 1001: // Chat input
            if (HIWORD(wParam) == EN_CHANGE) {
                wchar_t buffer[1024];
                GetWindowTextW(hChatInput_, buffer, static_cast<int>(sizeof(buffer) / sizeof(wchar_t)));
                bool newShowPlaceholder = (buffer[0] == L'\0');

                // Chỉ vẽ lại phần placeholder khi trạng thái thay đổi
                // Không invalidate toàn bộ inputRect_ để tránh flicker
                if (newShowPlaceholder != chatViewState_.showPlaceholder) {
                    chatViewState_.showPlaceholder = newShowPlaceholder;
                    // Chỉ invalidate phần placeholder, không invalidate edit control
                    RECT placeholderRect = inputRect_;
                    InflateRect(&placeholderRect, -2, -2);
                    int inputPaddingX = 50;
                    int buttonMarginRight = 12;
                    int gapTextToButton = 10;
                    int inputHeight = placeholderRect.bottom - placeholderRect.top;
                    int buttonSize = inputHeight - 12;
                    int buttonX = placeholderRect.right - buttonMarginRight - buttonSize;
                    placeholderRect.left = placeholderRect.left + inputPaddingX + 2;
                    placeholderRect.right = buttonX - gapTextToButton;
                    InvalidateRect(hwnd_, &placeholderRect, FALSE);
                }
            }
            break;
        case 1004: // New conversation button
            if (HIWORD(wParam) == BN_CLICKED) {
                // Tạo session mới và reset UI
                sessionId_ = "session_" + std::to_string(GetTickCount());
                
                // Kill animation timer if active
                if (chatViewState_.animTimerId_ != 0 && hwnd_) {
                    KillTimer(hwnd_, chatViewState_.animTimerId_);
                }
                
                // Reset chat view state
                chatViewState_.Reset();

                // Clear hidden history and load conversations cho session mới (nếu backend dùng)
                ClearEdit(hChatHistory_);
                RefreshConversations();

                // Đưa input về layout ban đầu (OnSize sẽ tính lại)
                OnSize();
                InvalidateRect(hwnd_, NULL, TRUE);
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
    chatViewState_.showPlaceholder = true;
    InvalidateRect(hwnd_, &inputRect_, FALSE);
    
    // Add user message using helper function
    AddUserMessage(wmessage);

    // Thêm bubble trạng thái "AI đang trả lời..." để user thấy ngay
    AddInfoMessage(UiStrings::Get(IDS_AI_LOADING_MESSAGE));

    // Giữ view ở cuối và vẽ lại ngay để hiện bubble loading
    InvalidateRect(hwnd_, NULL, FALSE);
    UpdateWindow(hwnd_);

    // Gửi message tới backend (blocking call)
    std::string response = httpClient_.sendMessage(message, sessionId_);

    // Chuẩn bị text hiển thị cho AI / lỗi
    std::wstring aiText;
    bool isError = false;
    MessageMetadata metadata;
    
    if (!response.empty() && response.rfind("Error:", 0) == 0) {
        isError = true;
        metadata.rawJson = response;
        
        // Use ErrorHandler to get user-friendly message
        ErrorInfo error(ErrorCategory::Network, ErrorSeverity::Error, response);
        error.context = "MainWindow::SendChatMessage";
        error.technicalDetails = response;
        ErrorHandler::GetInstance().LogError(error);
        
        aiText = ErrorHandler::GetInstance().GetUserFriendlyMessage(error);
    } else {
        aiText = Utf8ToWide(response);
        if (aiText.empty()) {
            aiText = UiStrings::Get(IDS_BACKEND_NO_CONTENT);
        }
        metadata.rawJson = response;
    }

    // Ghi đè bubble "đang trả lời" bằng nội dung thật
    if (!chatViewState_.messages.empty()) {
        ChatMessage& lastMsg = chatViewState_.messages.back();
        lastMsg.text = aiText;
        lastMsg.isUser = false;
        lastMsg.type = isError ? MessageType::Error : MessageType::AI;
        lastMsg.timestamp = GetCurrentTimeW();
        lastMsg.metadata = metadata;
    } else {
        // Fallback (không nên xảy ra)
        if (isError) {
            AddErrorMessage(aiText, metadata);
        } else {
            AddAIMessage(aiText, metadata);
        }
    }

    // Sau khi đã có messages, khởi động animation đưa input xuống dưới
    chatViewState_.animStartY = chatViewState_.animCurrentY;
    // Target sẽ được tính trong OnSize dựa trên windowHeight_; tạm cập nhật
    chatViewState_.isAnimating = true;
    if (chatViewState_.animTimerId_ != 0) {
        KillTimer(hwnd_, chatViewState_.animTimerId_);
    }
    chatViewState_.animTimerId_ = SetTimer(hwnd_, 1, 15, NULL); // 15ms ~ 60fps
    
    // Redraw window to show new messages (no background erase to avoid flicker)
    InvalidateRect(hwnd_, NULL, FALSE);
}

void MainWindow::LoadSettingsFromFile() {
    std::ifstream in(configPath_);
    if (!in.is_open()) return;
    std::string content((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    in.close();
    if (content.empty()) return;
    
    std::string baseUrl = JsonParser::GetString(content, "baseUrl");
    std::string apiKey = JsonParser::GetString(content, "apiKey");
    if (!baseUrl.empty()) {
        httpClient_.setBaseUrl(baseUrl);
    }
    if (!apiKey.empty()) {
        httpClient_.setApiKey(apiKey);
    }
    
    // Load Ctrl+Enter setting
    std::string ctrlEnterStr = JsonParser::GetString(content, "ctrlEnterToSend");
    if (!ctrlEnterStr.empty()) {
        enableCtrlEnterToSend_ = (ctrlEnterStr == "true" || ctrlEnterStr == "1");
    }
}

void MainWindow::SaveSettingsToFile(const std::string& baseUrl, const std::string& apiKey, bool ctrlEnterEnabled) {
    std::ofstream out(configPath_, std::ios::trunc);
    if (!out.is_open()) return;
    out << "{\n"
        << "  \"baseUrl\": \"" << baseUrl << "\",\n"
        << "  \"apiKey\": \"" << apiKey << "\",\n"
        << "  \"ctrlEnterToSend\": \"" << (ctrlEnterEnabled ? "true" : "false") << "\"\n"
        << "}\n";
    out.close();
}

void MainWindow::UpdateModelNameFromHealth(const std::string& healthJson) {
    // Model name is nested in "llm.model" according to backend health endpoint
    std::string model = JsonParser::GetNestedString(healthJson, "llm.model");
    if (!model.empty()) {
        modelName_ = Utf8ToWide(model);
    } else {
        // Fallback: try top-level "model" field (for backward compatibility)
        model = JsonParser::GetString(healthJson, "model");
        if (!model.empty()) {
            modelName_ = Utf8ToWide(model);
        } else {
            // Clear model name if not found
            modelName_ = L"";
        }
    }
}