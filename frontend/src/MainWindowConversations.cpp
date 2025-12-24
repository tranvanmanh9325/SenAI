#include <windows.h>
#include "MainWindow.h"
#include "MainWindowHelpers.h"

#include <algorithm>
#include <map>
#include <string>
#include <vector>

// Conversation/task refresh and hover utilities split from MainWindowLogic.cpp

void MainWindow::RefreshConversations() {
    std::string conversationsJson = httpClient_.getConversations(""); // Get all conversations
    conversations_.clear();
    
    // Simple JSON array parsing (basic implementation)
    // Expected format: [{"id":1,"user_message":"...","session_id":"...","created_at":"..."}, ...]
    if (conversationsJson.empty() || conversationsJson.find("Error:") == 0) {
        return; // Error or empty
    }
    
    // Group conversations by session_id
    std::map<std::string, ConversationInfo> sessionMap;
    
    size_t pos = 0;
    while ((pos = conversationsJson.find("\"session_id\"", pos)) != std::string::npos) {
        // Find the session_id value
        size_t colonPos = conversationsJson.find(':', pos);
        if (colonPos == std::string::npos) break;
        
        size_t quoteStart = conversationsJson.find('"', colonPos);
        if (quoteStart == std::string::npos) break;
        quoteStart++;
        size_t quoteEnd = conversationsJson.find('"', quoteStart);
        if (quoteEnd == std::string::npos) break;
        
        std::string sessionId = conversationsJson.substr(quoteStart, quoteEnd - quoteStart);
        
        // Find id
        size_t idStart = conversationsJson.rfind("\"id\"", pos);
        if (idStart != std::string::npos) {
            size_t idColon = conversationsJson.find(':', idStart);
            if (idColon != std::string::npos) {
                size_t idValueStart = idColon + 1;
                while (idValueStart < conversationsJson.length() && 
                       (conversationsJson[idValueStart] == ' ' || conversationsJson[idValueStart] == '\t')) {
                    idValueStart++;
                }
                size_t idValueEnd = idValueStart;
                while (idValueEnd < conversationsJson.length() && 
                       conversationsJson[idValueEnd] >= '0' && conversationsJson[idValueEnd] <= '9') {
                    idValueEnd++;
                }
                int id = std::stoi(conversationsJson.substr(idValueStart, idValueEnd - idValueStart));
                
                // Find user_message preview
                size_t msgStart = conversationsJson.find("\"user_message\"", pos);
                std::wstring preview = L"Cuộc trò chuyện";
                if (msgStart != std::string::npos) {
                    size_t msgColon = conversationsJson.find(':', msgStart);
                    if (msgColon != std::string::npos) {
                        size_t msgQuoteStart = conversationsJson.find('"', msgColon);
                        if (msgQuoteStart != std::string::npos) {
                            msgQuoteStart++;
                            size_t msgQuoteEnd = conversationsJson.find('"', msgQuoteStart);
                            if (msgQuoteEnd != std::string::npos) {
                                std::string msg = conversationsJson.substr(msgQuoteStart, msgQuoteEnd - msgQuoteStart);
                                preview = Utf8ToWide(msg);
                                if (preview.length() > 40) {
                                    preview = preview.substr(0, 37) + L"...";
                                }
                            }
                        }
                    }
                }
                
                // Find created_at
                size_t dateStart = conversationsJson.find("\"created_at\"", pos);
                std::wstring timestamp = L"";
                if (dateStart != std::string::npos) {
                    size_t dateColon = conversationsJson.find(':', dateStart);
                    if (dateColon != std::string::npos) {
                        size_t dateQuoteStart = conversationsJson.find('"', dateColon);
                        if (dateQuoteStart != std::string::npos) {
                            dateQuoteStart++;
                            size_t dateQuoteEnd = conversationsJson.find('"', dateQuoteStart);
                            if (dateQuoteEnd != std::string::npos) {
                                std::string dateStr = conversationsJson.substr(dateQuoteStart, dateQuoteEnd - dateQuoteStart);
                                // Format: "2024-01-01T12:00:00" -> "01/01 12:00"
                                if (dateStr.length() >= 16) {
                                    timestamp = Utf8ToWide(dateStr.substr(5, 5) + " " + dateStr.substr(11, 5));
                                }
                            }
                        }
                    }
                }
                
                // Only add if session_id not already in map (keep latest)
                if (sessionMap.find(sessionId) == sessionMap.end() || sessionMap[sessionId].id < id) {
                    ConversationInfo info;
                    info.id = id;
                    info.sessionId = Utf8ToWide(sessionId);
                    info.preview = preview;
                    info.timestamp = timestamp.empty() ? L"Mới" : timestamp;
                    info.rawSessionId = sessionId;
                    sessionMap[sessionId] = info;
                }
            }
        }
        
        pos = quoteEnd + 1;
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
    
    // Parse conversations and add to messages_ in chronological order
    // Simple parsing: find each conversation object and extract user_message and ai_response
    size_t pos = 0;
    std::vector<std::pair<std::wstring, std::wstring>> tempMessages; // (user, ai)
    
    while ((pos = conversationsJson.find("\"user_message\"", pos)) != std::string::npos) {
        // Extract user_message với xử lý escape sequences
        size_t msgColon = conversationsJson.find(':', pos);
        if (msgColon == std::string::npos) break;
        size_t msgQuoteStart = conversationsJson.find('"', msgColon);
        if (msgQuoteStart == std::string::npos) break;
        msgQuoteStart++;
        
        // Parse string với xử lý escape sequences
        std::string userMsg;
        bool escaped = false;
        size_t i = msgQuoteStart;
        while (i < conversationsJson.length()) {
            char c = conversationsJson[i];
            if (escaped) {
                switch (c) {
                    case 'n': userMsg += '\n'; break;
                    case 'r': userMsg += '\r'; break;
                    case 't': userMsg += '\t'; break;
                    case '\\': userMsg += '\\'; break;
                    case '"': userMsg += '"'; break;
                    case '/': userMsg += '/'; break;
                    case 'b': userMsg += '\b'; break;
                    case 'f': userMsg += '\f'; break;
                    case 'u': {
                        // Skip unicode escape \uXXXX
                        if (i + 4 < conversationsJson.length()) {
                            i += 4;
                        }
                        break;
                    }
                    default: userMsg += c; break;
                }
                escaped = false;
            } else {
                if (c == '\\') {
                    escaped = true;
                } else if (c == '"') {
                    break; // End of string
                } else {
                    userMsg += c;
                }
            }
            i++;
        }
        
        // Extract ai_response với xử lý escape sequences
        size_t aiStart = conversationsJson.find("\"ai_response\"", i);
        std::string aiMsg = "";
        if (aiStart != std::string::npos) {
            size_t aiColon = conversationsJson.find(':', aiStart);
            if (aiColon != std::string::npos) {
                size_t aiQuoteStart = conversationsJson.find('"', aiColon);
                if (aiQuoteStart != std::string::npos) {
                    aiQuoteStart++;
                    
                    // Parse ai_response string với escape sequences
                    escaped = false;
                    i = aiQuoteStart;
                    while (i < conversationsJson.length()) {
                        char c = conversationsJson[i];
                        if (escaped) {
                            switch (c) {
                                case 'n': aiMsg += '\n'; break;
                                case 'r': aiMsg += '\r'; break;
                                case 't': aiMsg += '\t'; break;
                                case '\\': aiMsg += '\\'; break;
                                case '"': aiMsg += '"'; break;
                                case '/': aiMsg += '/'; break;
                                case 'b': aiMsg += '\b'; break;
                                case 'f': aiMsg += '\f'; break;
                                case 'u': {
                                    if (i + 4 < conversationsJson.length()) {
                                        i += 4;
                                    }
                                    break;
                                }
                                default: aiMsg += c; break;
                            }
                            escaped = false;
                        } else {
                            if (c == '\\') {
                                escaped = true;
                            } else if (c == '"') {
                                break; // End of string
                            } else {
                                aiMsg += c;
                            }
                        }
                        i++;
                    }
                }
            }
        }
        
        tempMessages.push_back({Utf8ToWide(userMsg), Utf8ToWide(aiMsg)});
        pos = i + 1;
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
    
    // Parse response
    if (healthResponse.empty() || healthResponse.find("Error:") == 0) {
        healthStatus_ = HealthStatus::Offline;
    } else {
        UpdateModelNameFromHealth(healthResponse);
        // Check if response contains "status": "healthy"
        if (healthResponse.find("\"status\"") != std::string::npos &&
            healthResponse.find("\"healthy\"") != std::string::npos) {
            healthStatus_ = HealthStatus::Online;
        } else {
            healthStatus_ = HealthStatus::Offline;
        }
    }
    
    // Redraw status badge
    InvalidateRect(hwnd_, NULL, FALSE);
}

void MainWindow::UpdateMessageHover(int x, int y) {
    // Calculate which message bubble is being hovered
    int newHoveredIndex = -1;
    
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
        HFONT testFont = CreateFontW(-22, 0, 0, 0, FW_MEDIUM, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
        HDC hdc = GetDC(hwnd_);
        SelectObject(hdc, testFont);
        DrawTextW(hdc, msg.text.c_str(), -1, &testRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
        DeleteObject(testFont);
        ReleaseDC(hwnd_, hdc);
        
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
        
        if (x >= bubbleRect.left && x <= bubbleRect.right &&
            y >= bubbleRect.top && y <= bubbleRect.bottom) {
            newHoveredIndex = static_cast<int>(i);
            break;
        }
        
        currentY += bubbleHeight + messageMarginY;
    }
    
    if (newHoveredIndex != hoveredMessageIndex_) {
        hoveredMessageIndex_ = newHoveredIndex;
        InvalidateRect(hwnd_, NULL, FALSE); // Redraw to show hover effect
    }
}