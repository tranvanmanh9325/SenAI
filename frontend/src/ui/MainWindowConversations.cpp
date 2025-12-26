#include <windows.h>
#include <commctrl.h>
#include "MainWindow.h"
#include "MainWindowHelpers.h"
#include "JsonParser.h"
#include <nlohmann/json.hpp>

#include <algorithm>
#include <map>
#include <string>
#include <vector>

// Conversation/task refresh and hover utilities split from MainWindowLogic.cpp

void MainWindow::RefreshConversations() {
    std::string conversationsJson = httpClient_.getConversations(""); // Get all conversations
    conversations_.clear();
    
    // Check for errors
    if (conversationsJson.empty() || conversationsJson.find("Error:") == 0) {
        return; // Error or empty
    }
    
    // Parse JSON array using JsonParser
    std::vector<nlohmann::json> conversationsArray = JsonParser::ParseArray(conversationsJson);
    if (conversationsArray.empty()) {
        return; // Failed to parse or empty array
    }
    
    // Group conversations by session_id
    std::map<std::string, ConversationInfo> sessionMap;
    
    try {
        for (const auto& conv : conversationsArray) {
            if (!conv.is_object()) {
                continue;
            }
            
            // Extract fields using nlohmann/json
            std::string sessionId;
            int id = 0;
            std::string userMessage;
            std::string createdAt;
            
            if (conv.contains("session_id") && conv["session_id"].is_string()) {
                sessionId = conv["session_id"].get<std::string>();
            }
            
            if (conv.contains("id") && conv["id"].is_number_integer()) {
                id = conv["id"].get<int>();
            } else if (conv.contains("id") && conv["id"].is_number_unsigned()) {
                id = static_cast<int>(conv["id"].get<unsigned int>());
            }
            
            if (conv.contains("user_message") && conv["user_message"].is_string()) {
                userMessage = conv["user_message"].get<std::string>();
            }
            
            if (conv.contains("created_at") && conv["created_at"].is_string()) {
                createdAt = conv["created_at"].get<std::string>();
            }
            
            if (sessionId.empty()) {
                continue; // Skip conversations without session_id
            }
            
            // Create preview from user_message
            std::wstring preview = UiStrings::Get(IDS_CONVERSATION_PREVIEW_DEFAULT);
            if (!userMessage.empty()) {
                preview = Utf8ToWide(userMessage);
                if (preview.length() > 40) {
                    preview = preview.substr(0, 37) + L"...";
                }
            }
            
            // Format timestamp: "2024-01-01T12:00:00" -> "01/01 12:00"
            std::wstring timestamp = L"";
            if (!createdAt.empty() && createdAt.length() >= 16) {
                timestamp = Utf8ToWide(createdAt.substr(5, 5) + " " + createdAt.substr(11, 5));
            }
            
            // Only add if session_id not already in map (keep latest)
            if (sessionMap.find(sessionId) == sessionMap.end() || sessionMap[sessionId].id < id) {
                ConversationInfo info;
                info.id = id;
                info.sessionId = Utf8ToWide(sessionId);
                info.preview = preview;
                info.timestamp = timestamp.empty() ? UiStrings::Get(IDS_CONVERSATION_NEW) : timestamp;
                info.rawSessionId = sessionId;
                sessionMap[sessionId] = info;
            }
        }
    } catch (const std::exception& e) {
        // Log error and return empty list
        JsonParser::LogError("Error parsing conversations: " + std::string(e.what()));
        return;
    }
    
    // Convert map to vector and sort by id (newest first)
    for (const auto& pair : sessionMap) {
        conversations_.push_back(pair.second);
    }
    std::sort(conversations_.begin(), conversations_.end(), 
              [](const ConversationInfo& a, const ConversationInfo& b) { return a.id > b.id; });
    
    // Update selected index if current session exists
    selectedConversationIndex_ = -1;
    for (size_t i = 0; i < conversations_.size(); i++) {
        if (conversations_[i].rawSessionId == sessionId_) {
            selectedConversationIndex_ = static_cast<int>(i);
            break;
        }
    }
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

void MainWindow::LoadConversationBySessionId(const std::string& sessionId) {
    // Load all conversations for this session
    std::string conversationsJson = httpClient_.getConversations(sessionId);
    
    if (conversationsJson.empty() || conversationsJson.find("Error:") == 0) {
        return;
    }
    
    chatViewState_.messages.clear();
    
    // Parse conversations using JsonParser
    std::vector<nlohmann::json> conversationsArray = JsonParser::ParseArray(conversationsJson);
    if (conversationsArray.empty()) {
        return; // Failed to parse or empty array
    }
    
    std::vector<std::pair<std::wstring, std::wstring>> tempMessages; // (user, ai)
    
    try {
        for (const auto& conv : conversationsArray) {
            if (!conv.is_object()) {
                continue;
            }
            
            // Extract user_message
            std::string userMsg;
            if (conv.contains("user_message") && conv["user_message"].is_string()) {
                userMsg = conv["user_message"].get<std::string>();
            }
            
            // Extract ai_response
            std::string aiMsg;
            if (conv.contains("ai_response") && conv["ai_response"].is_string()) {
                aiMsg = conv["ai_response"].get<std::string>();
            }
            
            tempMessages.push_back({Utf8ToWide(userMsg), Utf8ToWide(aiMsg)});
        }
    } catch (const std::exception& e) {
        // Log error and return
        JsonParser::LogError("Error parsing conversation messages: " + std::string(e.what()));
        return;
    }
    
    // Add messages in order (oldest first) using helper functions
    for (const auto& pair : tempMessages) {
        AddUserMessage(pair.first);
        
        if (!pair.second.empty()) {
            AddAIMessage(pair.second);
        }
    }
    
    sessionId_ = sessionId;
    
    // Kill animation timer if active
    if (chatViewState_.animTimerId_ != 0) {
        KillTimer(hwnd_, chatViewState_.animTimerId_);
    }
    
    // Reset animation state và đảm bảo input ở dưới cùng khi đã có messages
    chatViewState_.scrollOffset = 0;
    chatViewState_.autoScrollToBottom = true;
    chatViewState_.isAnimating = false;
    chatViewState_.animCurrentY = 0;
    chatViewState_.animTargetY = 0;
    chatViewState_.animStartY = 0;
    chatViewState_.animTimerId_ = 0;
    
    // Gọi OnSize() để cập nhật layout input (sẽ đặt input ở dưới cùng vì messages_ không rỗng)
    OnSize();
    InvalidateRect(hwnd_, NULL, TRUE);
}

void MainWindow::CheckHealthStatus() {
    // Set status to checking
    healthStatus_ = HealthStatus::Checking;
    InvalidateRect(hwnd_, NULL, FALSE); // Redraw status badge
    
    // Call health check endpoint
    std::string healthResponse = httpClient_.checkHealth();
    
    // Parse response using JsonParser
    if (healthResponse.empty() || healthResponse.find("Error:") == 0) {
        healthStatus_ = HealthStatus::Offline;
    } else {
        UpdateModelNameFromHealth(healthResponse);
        // Check if response contains "status": "healthy"
        std::string status = JsonParser::GetString(healthResponse, "status");
        if (status == "healthy") {
            healthStatus_ = HealthStatus::Online;
        } else {
            healthStatus_ = HealthStatus::Offline;
        }
    }
    
    // Redraw status badge
    InvalidateRect(hwnd_, NULL, FALSE);
}

RECT MainWindow::GetMessageBubbleRect(int messageIndex) {
    RECT result = {0, 0, 0, 0};
    if (messageIndex < 0 || static_cast<size_t>(messageIndex) >= chatViewState_.messages.size()) {
        return result;
    }
    
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    int headerH = theme_.headerHeight;
    int sidebarOffset = sidebarVisible_ ? sidebarWidth_ : 0;
    int messageAreaTop = headerH + 20;
    int messageAreaLeft = sidebarOffset;
    int messageAreaRight = clientRect.right;
    int userMessageMarginRight = 32;
    int aiMessageMarginLeft = sidebarVisible_ ? 16 : theme_.messageMarginX;
    int avatarSize = 20;
    int avatarMargin = 8;
    int bubbleOffsetX = avatarSize + avatarMargin;
    int bubblePaddingX = 18;
    int bubblePaddingY = 14;
    int maxBubbleWidth = (int)((messageAreaRight - messageAreaLeft - aiMessageMarginLeft - userMessageMarginRight) * 0.75);
    
    int currentY = messageAreaTop - chatViewState_.scrollOffset;
    int messageMarginY = theme_.messageMarginY;
    
    for (int i = 0; i <= messageIndex && static_cast<size_t>(i) < chatViewState_.messages.size(); i++) {
        const auto& msg = chatViewState_.messages[i];
        
        // Estimate bubble size
        RECT testRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
        auto testFont = gdiManager_->CreateFont(-22, 0, 0, 0, FW_MEDIUM, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
        HDC hdc = GetDC(hwnd_);
        SelectObject(hdc, testFont->Get());
        DrawTextW(hdc, msg.text.c_str(), -1, &testRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
        ReleaseDC(hwnd_, hdc);
        // Smart pointer automatically cleans up
        
        int bubbleWidth = testRect.right + 2 * bubblePaddingX;
        int bubbleHeight = testRect.bottom + 2 * bubblePaddingY + 16;
        
        if (i == messageIndex) {
            if (msg.type == MessageType::User || (msg.type == MessageType::AI && msg.isUser)) {
                result.left = messageAreaRight - userMessageMarginRight - bubbleWidth;
                result.right = messageAreaRight - userMessageMarginRight;
            } else {
                result.left = messageAreaLeft + aiMessageMarginLeft + bubbleOffsetX;
                result.right = result.left + bubbleWidth;
            }
            result.top = currentY;
            result.bottom = currentY + bubbleHeight;
            break;
        }
        
        currentY += bubbleHeight + messageMarginY;
    }
    
    return result;
}

RECT MainWindow::GetCopyIconRect(int messageIndex) {
    RECT result = {0, 0, 0, 0};
    RECT bubbleRect = GetMessageBubbleRect(messageIndex);
    if (bubbleRect.right == 0 && bubbleRect.bottom == 0) {
        return result;
    }
    
    // Check if this is a user message or AI message to position icon correctly
    if (messageIndex >= 0 && static_cast<size_t>(messageIndex) < chatViewState_.messages.size()) {
        const auto& msg = chatViewState_.messages[messageIndex];
        bool isUserMsg = (msg.type == MessageType::User || (msg.type == MessageType::AI && msg.isUser));
        
        int iconSize = 16;
        int iconPadding = 8;  // Space between bubble and icon
        int iconTopOffset = 20;  // Offset from top of bubble (lower position)
        
        if (isUserMsg) {
            // User messages: icon on the left side of bubble (bên trái bubble)
            result.left = bubbleRect.left - iconSize - iconPadding;
            result.top = bubbleRect.top + iconTopOffset;
        } else {
            // AI messages: icon on the right side of bubble (bên phải bubble)
            result.left = bubbleRect.right + iconPadding;
            result.top = bubbleRect.top + iconTopOffset;
        }
        
        result.right = result.left + iconSize;
        result.bottom = result.top + iconSize;
    }
    
    return result;
}

void MainWindow::CopyMessageToClipboard(int messageIndex) {
    if (messageIndex < 0 || static_cast<size_t>(messageIndex) >= chatViewState_.messages.size()) {
        return;
    }
    
    const auto& msg = chatViewState_.messages[messageIndex];
    std::wstring textToCopy = msg.text;
    
    // Open clipboard
    if (!OpenClipboard(hwnd_)) {
        return;
    }
    
    // Clear clipboard
    EmptyClipboard();
    
    // Allocate memory for text
    size_t textLen = textToCopy.length();
    HGLOBAL hMem = GlobalAlloc(GMEM_MOVEABLE, (textLen + 1) * sizeof(wchar_t));
    if (hMem) {
        wchar_t* pMem = (wchar_t*)GlobalLock(hMem);
        if (pMem) {
            wcscpy_s(pMem, textLen + 1, textToCopy.c_str());
            GlobalUnlock(hMem);
            SetClipboardData(CF_UNICODETEXT, hMem);
        }
    }
    
    CloseClipboard();
    
    // Show checkmark feedback
    // Kill existing timer if any
    if (copyFeedbackTimerId_ != 0) {
        KillTimer(hwnd_, copyFeedbackTimerId_);
        copyFeedbackTimerId_ = 0;
    }
    
    // Set copied message index to show checkmark
    copiedMessageIndex_ = messageIndex;
    
    // Invalidate the message area to redraw with checkmark
    RECT iconRect = GetCopyIconRect(messageIndex);
    InflateRect(&iconRect, 4, 4); // Add some padding for smooth animation area
    InvalidateRect(hwnd_, &iconRect, FALSE);
    
    // Set timer to reset checkmark back to copy icon after 2 seconds
    copyFeedbackTimerId_ = SetTimer(hwnd_, 3, 2000, NULL);
}

void MainWindow::ShowMessageTooltip(int messageIndex, int x, int y) {
    if (messageIndex < 0 || static_cast<size_t>(messageIndex) >= chatViewState_.messages.size()) {
        HideMessageTooltip();
        return;
    }
    
    // Only show tooltip if it's not already showing for this message
    if (tooltipMessageIndex_ == messageIndex && hTooltipWindow_ != NULL) {
        return;
    }
    
    HideMessageTooltip();
    
    const auto& msg = chatViewState_.messages[messageIndex];
    const auto& metadata = msg.metadata;
    
    // Build tooltip text
    std::wstring tooltipText = L"";
    if (metadata.tokenUsage > 0) {
        tooltipText += L"Tokens: " + std::to_wstring(metadata.tokenUsage) + L"\n";
    }
    if (metadata.latencyMs > 0) {
        tooltipText += L"Latency: " + std::to_wstring(metadata.latencyMs) + L"ms\n";
    }
    if (!metadata.modelName.empty()) {
        tooltipText += L"Model: " + metadata.modelName;
    }
    
    if (tooltipText.empty()) {
        return; // No metadata to show
    }
    
    // Remove trailing newline
    if (!tooltipText.empty() && tooltipText.back() == L'\n') {
        tooltipText.pop_back();
    }
    
    // Create tooltip window
    hTooltipWindow_ = CreateWindowExW(
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
        TOOLTIPS_CLASSW,
        NULL,
        WS_POPUP | TTS_NOPREFIX | TTS_ALWAYSTIP,
        CW_USEDEFAULT, CW_USEDEFAULT,
        CW_USEDEFAULT, CW_USEDEFAULT,
        hwnd_,
        NULL,
        GetModuleHandle(NULL),
        NULL
    );
    
    if (hTooltipWindow_) {
        // Set tooltip info
        TOOLINFOW ti = {0};
        ti.cbSize = sizeof(TOOLINFOW);
        ti.uFlags = TTF_TRACK | TTF_ABSOLUTE;
        ti.hwnd = hwnd_;
        ti.lpszText = const_cast<LPWSTR>(tooltipText.c_str());
        
        SendMessageW(hTooltipWindow_, TTM_ADDTOOLW, 0, (LPARAM)&ti);
        SendMessageW(hTooltipWindow_, TTM_TRACKPOSITION, 0, MAKELPARAM(x + 10, y + 10));
        SendMessageW(hTooltipWindow_, TTM_TRACKACTIVATE, TRUE, (LPARAM)&ti);
        
        tooltipMessageIndex_ = messageIndex;
    }
}

void MainWindow::HideMessageTooltip() {
    if (hTooltipWindow_) {
        DestroyWindow(hTooltipWindow_);
        hTooltipWindow_ = NULL;
    }
    tooltipMessageIndex_ = -1;
}

void MainWindow::UpdateMessageHover(int x, int y) {
    // Calculate which message bubble is being hovered
    int newHoveredIndex = -1;
    int newHoveredCopyIconIndex = -1;
    
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    int headerH = theme_.headerHeight;
    int sidebarOffset = sidebarVisible_ ? sidebarWidth_ : 0;
    int messageAreaTop = headerH + 20;
    int messageAreaLeft = sidebarOffset;
    int messageAreaRight = clientRect.right;
    int userMessageMarginRight = 32;
    int aiMessageMarginLeft = sidebarVisible_ ? 16 : theme_.messageMarginX;
    int avatarSize = 20;
    int avatarMargin = 8;
    int bubbleOffsetX = avatarSize + avatarMargin;
    int bubblePaddingX = 18;
    int bubblePaddingY = 14;
    int maxBubbleWidth = (int)((messageAreaRight - messageAreaLeft - aiMessageMarginLeft - userMessageMarginRight) * 0.75);
    
    int currentY = messageAreaTop - chatViewState_.scrollOffset;
    int messageMarginY = theme_.messageMarginY;
    
    for (size_t i = 0; i < chatViewState_.messages.size(); i++) {
        const auto& msg = chatViewState_.messages[i];
        
        // Estimate bubble size (simplified)
        RECT testRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
        auto testFont = gdiManager_->CreateFont(-22, 0, 0, 0, FW_MEDIUM, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
        HDC hdc = GetDC(hwnd_);
        SelectObject(hdc, testFont->Get());
        DrawTextW(hdc, msg.text.c_str(), -1, &testRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
        ReleaseDC(hwnd_, hdc);
        // Smart pointer automatically cleans up
        
        int bubbleWidth = testRect.right + 2 * bubblePaddingX;
        int bubbleHeight = testRect.bottom + 2 * bubblePaddingY + 16;
        
        RECT bubbleRect;
        if (msg.type == MessageType::User || (msg.type == MessageType::AI && msg.isUser)) {
            bubbleRect.left = messageAreaRight - userMessageMarginRight - bubbleWidth;
            bubbleRect.right = messageAreaRight - userMessageMarginRight;
        } else {
            bubbleRect.left = messageAreaLeft + aiMessageMarginLeft + bubbleOffsetX;
            bubbleRect.right = bubbleRect.left + bubbleWidth;
        }
        bubbleRect.top = currentY;
        bubbleRect.bottom = currentY + bubbleHeight;
        
        // Check if hovering over copy icon
        RECT copyIconRect = GetCopyIconRect(static_cast<int>(i));
        if (x >= copyIconRect.left && x <= copyIconRect.right &&
            y >= copyIconRect.top && y <= copyIconRect.bottom) {
            newHoveredCopyIconIndex = static_cast<int>(i);
            newHoveredIndex = static_cast<int>(i); // Also highlight bubble
        } else if (x >= bubbleRect.left && x <= bubbleRect.right &&
                   y >= bubbleRect.top && y <= bubbleRect.bottom) {
            newHoveredIndex = static_cast<int>(i);
            // Show tooltip with metadata
            ShowMessageTooltip(static_cast<int>(i), x, y);
        }
        
        currentY += bubbleHeight + messageMarginY;
    }
    
    // Hide tooltip if not hovering any message
    if (newHoveredIndex == -1) {
        HideMessageTooltip();
    }
    
    bool needsRedraw = false;
    if (newHoveredIndex != hoveredMessageIndex_) {
        hoveredMessageIndex_ = newHoveredIndex;
        needsRedraw = true;
    }
    if (newHoveredCopyIconIndex != hoveredCopyIconIndex_) {
        hoveredCopyIconIndex_ = newHoveredCopyIconIndex;
        needsRedraw = true;
    }
    
    if (needsRedraw) {
        InvalidateRect(hwnd_, NULL, FALSE); // Redraw to show hover effect
    }
}