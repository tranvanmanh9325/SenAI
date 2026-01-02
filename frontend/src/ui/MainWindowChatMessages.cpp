#include <windows.h>
#include "MainWindow.h"
#include <string>
#include <algorithm>

// UI layout & chat rendering (render primitives are defined in MainWindowRender.cpp)

void MainWindow::DrawChatMessages(HDC hdc) {
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    
    // Calculate available area for messages (above input field)
    int inputHeight = 60;
    int marginBottom = 20; // Space between messages and input
    int headerH = 48;
    int sidebarOffset = sidebarVisible_ ? sidebarWidth_ : 0;
    int messageAreaTop = headerH + (searchVisible_ ? 50 : 20); // Account for search bar
    int messageAreaBottom = clientRect.bottom - inputHeight - marginBottom;
    int messageAreaLeft = sidebarOffset;
    int messageAreaRight = clientRect.right;
    
    // Message styling constants
    int messageMarginX = theme_.messageMarginX; // Horizontal margin from window edges
    int messageMarginY = theme_.messageMarginY; // Vertical spacing between messages
    
    // Margins cho user và AI messages riêng biệt
    int userMessageMarginRight = 32; // User messages cách bên phải một chút để dễ nhìn
    int aiMessageMarginLeft; // AI messages sát bên trái/sidebar
    
    if (sidebarVisible_) {
        aiMessageMarginLeft = 16; // Sát với sidebar
    } else {
        aiMessageMarginLeft = messageMarginX; // Dùng margin mặc định nếu không có sidebar
    }
    int bubblePaddingX = 16; // Horizontal padding inside bubble
    int bubblePaddingY = 12; // Vertical padding inside bubble
    int bubbleRadius = 18; // Rounded corner radius
    // Tính available width với margins riêng cho user và AI
    int availableWidth = messageAreaRight - messageAreaLeft - aiMessageMarginLeft - userMessageMarginRight;
    int maxBubbleWidth = (int)(availableWidth * 0.75); // Max 75% of available width
    
    // Use cached fonts instead of creating new ones each render
    HGDIOBJ oldFont = SelectObject(hdc, hMessageFont_->Get());
    
    SetBkMode(hdc, TRANSPARENT);
    
    // Calculate total height needed for all messages
    int totalHeight = 0;
    for (const auto& msg : chatViewState_.messages) {
        // Ensure we measure text with the correct font for each message type
        HFONT hCurrentFont = hMessageFont_->Get();
        if (msg.type == MessageType::Code) {
            hCurrentFont = hCodeFont_->Get();
        } else if (msg.type == MessageType::User) {
            hCurrentFont = hMessageFont_->Get();
        } else {
            hCurrentFont = hAIMessageFont_->Get();
        }
        SelectObject(hdc, hCurrentFont);

        RECT textRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
        DrawTextW(hdc, msg.text.c_str(), -1, &textRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);

        // Use the same bubble height formula as when drawing,
        // so that the last message never hides behind the input field.
        int textHeight = textRect.bottom;
        int bubbleHeight = textHeight + 2 * bubblePaddingY + 16; // +16 for timestamp row

        totalHeight += bubbleHeight + messageMarginY;
    }
    
    // Compute scrolling bounds
    int availableHeight = messageAreaBottom - messageAreaTop;
    int maxScroll = 0;
    if (totalHeight > availableHeight) {
        maxScroll = totalHeight - availableHeight;
    }

    // Auto-scroll to bottom only when enabled; otherwise clamp existing offset
    if (chatViewState_.autoScrollToBottom) {
        chatViewState_.scrollOffset = maxScroll;
    } else {
        if (chatViewState_.scrollOffset > maxScroll) chatViewState_.scrollOffset = maxScroll;
        if (chatViewState_.scrollOffset < 0) chatViewState_.scrollOffset = 0;
    }
    
    int currentY = messageAreaTop - chatViewState_.scrollOffset;
    
    // Draw messages from oldest to newest
    for (size_t msgIdx = 0; msgIdx < chatViewState_.messages.size(); msgIdx++) {
        const auto& msg = chatViewState_.messages[msgIdx];
        if (currentY > messageAreaBottom) break; // Skip messages below visible area
        if (currentY + 50 < messageAreaTop) { // Skip messages above visible area
            // Estimate height and continue
            HFONT hCurrentFont = hMessageFont_->Get();
            if (msg.type == MessageType::Code) {
                hCurrentFont = hCodeFont_->Get();
            } else if (msg.type == MessageType::User) {
                hCurrentFont = hMessageFont_->Get();
            } else {
                hCurrentFont = hAIMessageFont_->Get();
            }
            SelectObject(hdc, hCurrentFont);

            RECT testRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
            DrawTextW(hdc, msg.text.c_str(), -1, &testRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
            currentY += testRect.bottom + 2 * bubblePaddingY + messageMarginY;
            continue;
        }
        
        // Select correct font for this message and calculate text size
        HFONT hCurrentFont = hMessageFont_->Get();
        if (msg.type == MessageType::Code) {
            hCurrentFont = hCodeFont_->Get();
        } else if (msg.type == MessageType::User) {
            hCurrentFont = hMessageFont_->Get();
        } else {
            hCurrentFont = hAIMessageFont_->Get();
        }
        SelectObject(hdc, hCurrentFont);

        RECT textRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
        DrawTextW(hdc, msg.text.c_str(), -1, &textRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
        int textWidth = textRect.right;
        int textHeight = textRect.bottom;
        
        int bubbleWidth = textWidth + 2 * bubblePaddingX;
        int bubbleHeight = textHeight + 2 * bubblePaddingY + 16; // space for timestamp
        
        RECT bubbleRect;
        RECT textDrawRect;

        // Avatar circle
        int avatarSize = 20;
        int avatarMargin = 8;
        int bubbleOffsetX = avatarSize + avatarMargin;

        // Determine message type (use type field, fallback to isUser for backward compatibility)
        MessageType msgType = msg.type;
        if (msgType == MessageType::AI && msg.isUser) {
            msgType = MessageType::User; // Backward compatibility
        }
        
        // Calculate hover state once for this message
        bool isHovered = (hoveredMessageIndex_ >= 0 && 
                         static_cast<size_t>(hoveredMessageIndex_) < chatViewState_.messages.size() &&
                         static_cast<int>(msgIdx) == hoveredMessageIndex_);
        
        // Check if this is the current search result
        bool isCurrentSearchResult = (searchVisible_ && 
                                     currentSearchIndex_ >= 0 && 
                                     currentSearchIndex_ < static_cast<int>(searchResults_.size()) &&
                                     static_cast<int>(msgIdx) == searchResults_[currentSearchIndex_]);
        
        if (msgType == MessageType::User) {
            // User messages sát bên phải
            bubbleRect.left = messageAreaRight - userMessageMarginRight - bubbleWidth;
            bubbleRect.right = messageAreaRight - userMessageMarginRight;
            bubbleRect.top = currentY;
            bubbleRect.bottom = currentY + bubbleHeight;
            COLORREF bubbleFill = RGB(30, 37, 61);
            COLORREF bubbleBorder = RGB(65, 78, 110);
            if (isCurrentSearchResult) {
                bubbleFill = RGB(50, 60, 90); // Brighter for current search result
                bubbleBorder = RGB(255, 255, 100); // Yellow border for current search result
            } else if (isHovered) {
                bubbleFill = RGB(38, 45, 75); // Brighter on hover
                bubbleBorder = RGB(100, 130, 180); // Brighter border with glow effect
            }
            
            // Draw glow effect for hovered user bubbles
            if (isHovered) {
                RECT glowRect = bubbleRect;
                InflateRect(&glowRect, 3, 3);
                COLORREF glowColor = RGB(
                    GetRValue(bubbleBorder) / 3,
                    GetGValue(bubbleBorder) / 3,
                    GetBValue(bubbleBorder) / 3
                );
                auto glowPen = gdiManager_->CreatePen(PS_SOLID, 1, glowColor);
                HGDIOBJ oldGlowPen = SelectObject(hdc, glowPen->Get());
                HBRUSH oldGlowBrush = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
                RoundRect(hdc, glowRect.left, glowRect.top, glowRect.right, glowRect.bottom, 
                         bubbleRadius + 2, bubbleRadius + 2);
                SelectObject(hdc, oldGlowPen);
                SelectObject(hdc, oldGlowBrush);
                // Smart pointer automatically cleans up
            }
            
            auto bubbleBrush = gdiManager_->CreateSolidBrush(bubbleFill);
            auto bubblePen = gdiManager_->CreatePen(PS_SOLID, isHovered ? 2 : 1, bubbleBorder);
            HGDIOBJ oldBrush = SelectObject(hdc, bubbleBrush->Get());
            HGDIOBJ oldPen = SelectObject(hdc, bubblePen->Get());
            RoundRect(hdc, bubbleRect.left, bubbleRect.top, bubbleRect.right, bubbleRect.bottom, 
                     bubbleRadius, bubbleRadius);
            SelectObject(hdc, oldBrush);
            SelectObject(hdc, oldPen);
            // Smart pointers automatically clean up
            
            // Avatar with hover glow effect
            COLORREF avatarColor = isHovered ? RGB(120, 250, 255) : RGB(74, 215, 255);

            // Text
            SetTextColor(hdc, RGB(236, 240, 255));
            textDrawRect = bubbleRect;
            textDrawRect.left += bubblePaddingX;
            textDrawRect.right -= bubblePaddingX;
            textDrawRect.top += bubblePaddingY;
            textDrawRect.bottom = textDrawRect.top + textHeight;
            
            // Draw search highlights first (behind text)
            if (searchVisible_ && !searchQuery_.empty()) {
                DrawSearchHighlight(hdc, msg.text, textDrawRect, hMessageFont_->Get());
            }
            
            DrawTextW(hdc, msg.text.c_str(), -1, &textDrawRect, DT_LEFT | DT_WORDBREAK);

            // Timestamp
            SelectObject(hdc, hMetaFont_->Get());
            SetTextColor(hdc, RGB(154, 163, 195));
            RECT metaRect = textDrawRect;
            metaRect.top = textDrawRect.bottom + 4;
            metaRect.bottom = bubbleRect.bottom - bubblePaddingY + 2;
            DrawTextW(hdc, msg.timestamp.c_str(), -1, &metaRect, DT_RIGHT | DT_VCENTER | DT_SINGLELINE);

            // Avatar (right) with hover effect and glow
            int ax = bubbleRect.right + avatarMargin;
            if (ax > messageAreaRight) ax = messageAreaRight - avatarSize - 4; // Thêm 4px padding
            int ay = bubbleRect.top + 4;
            
            // Draw avatar glow on hover
            if (isHovered) {
                int glowSize = avatarSize + 6;
                int glowX = ax - 3;
                int glowY = ay - 3;
                COLORREF glowColor = RGB(
                    GetRValue(avatarColor) / 4,
                    GetGValue(avatarColor) / 4,
                    GetBValue(avatarColor) / 4
                );
                HBRUSH glowBrush = CreateSolidBrush(glowColor);
                HPEN glowPen = CreatePen(PS_NULL, 0, glowColor);
                HGDIOBJ oldGlowBrush = SelectObject(hdc, glowBrush);
                HGDIOBJ oldGlowPen = SelectObject(hdc, glowPen);
                Ellipse(hdc, glowX, glowY, glowX + glowSize, glowY + glowSize);
                SelectObject(hdc, oldGlowBrush);
                SelectObject(hdc, oldGlowPen);
                DeleteObject(glowBrush);
                DeleteObject(glowPen);
            }
            
            HBRUSH avatarBrush = CreateSolidBrush(avatarColor);
            HPEN avatarPen = CreatePen(PS_NULL, 0, avatarColor);
            oldBrush = SelectObject(hdc, avatarBrush);
            oldPen = SelectObject(hdc, avatarPen);
            Ellipse(hdc, ax, ay, ax + avatarSize, ay + avatarSize);
            SelectObject(hdc, oldBrush);
            SelectObject(hdc, oldPen);
            DeleteObject(avatarBrush);
            DeleteObject(avatarPen);
        } else {
            // AI / system message: left-aligned bubble
            SelectObject(hdc, hAIMessageFont_->Get());
            RECT aiTextRect = {0, 0, maxBubbleWidth - 2 * bubblePaddingX, 0};
            DrawTextW(hdc, msg.text.c_str(), -1, &aiTextRect, DT_LEFT | DT_WORDBREAK | DT_CALCRECT);
            textWidth = aiTextRect.right;
            textHeight = aiTextRect.bottom;
            bubbleWidth = textWidth + 2 * bubblePaddingX;
            bubbleHeight = textHeight + 2 * bubblePaddingY + 16;

            // Determine bubble style based on message type
            MessageType msgType = msg.type;
            if (msgType == MessageType::AI && msg.isUser) {
                msgType = MessageType::User; // Backward compatibility
            }
            
            bool isErrorBubble = (msgType == MessageType::Error);
            bool isLoadingBubble = (msgType == MessageType::Info);
            bool isSystemBubble = (msgType == MessageType::System);
            bool isCodeBubble = (msgType == MessageType::Code);
            
            // AI/System/Error/Code messages sát bên trái/sidebar
            // Code bubbles use different padding (more padding for better readability)
            int codePaddingX = isCodeBubble ? 24 : bubblePaddingX;
            int codePaddingY = isCodeBubble ? 18 : bubblePaddingY;
            if (isCodeBubble) {
                bubbleWidth = textWidth + 2 * codePaddingX;
                bubbleHeight = textHeight + 2 * codePaddingY + 16;
            }
            
            bubbleRect.left = messageAreaLeft + aiMessageMarginLeft + bubbleOffsetX;
            bubbleRect.right = bubbleRect.left + bubbleWidth;
            bubbleRect.top = currentY;
            bubbleRect.bottom = currentY + bubbleHeight;
            
            COLORREF bubbleFill, bubbleBorder, textColor;
            if (isCodeBubble) {
                bubbleFill = RGB(12, 12, 18);      // Very dark background for code (easier to read)
                bubbleBorder = RGB(80, 120, 160);   // Brighter border for code blocks
                textColor = RGB(220, 240, 255);    // Bright text for code
            } else if (isErrorBubble) {
                bubbleFill = RGB(48, 32, 24);      // Dark red/orange
                bubbleBorder = RGB(255, 196, 0);   // Yellow border
                textColor = RGB(255, 240, 200);
            } else if (isSystemBubble) {
                bubbleFill = RGB(30, 50, 70);      // More distinct blue-tinted for system info
                bubbleBorder = RGB(120, 200, 255);  // Brighter blue border
                textColor = RGB(210, 240, 255);    // Bright system text
            } else {
                bubbleFill = RGB(24, 32, 48);
                bubbleBorder = RGB(74, 215, 255);
                textColor = RGB(232, 236, 255);
            }
            
            // Highlight current search result
            if (isCurrentSearchResult) {
                bubbleFill = RGB(40, 50, 70); // Brighter for current search result
                bubbleBorder = RGB(255, 255, 100); // Yellow border for current search result
            }

            // Avatar (left) – đổi màu theo loại message
            COLORREF avatarColor = RGB(154, 107, 255);
            if (isErrorBubble) avatarColor = RGB(255, 120, 120);
            else if (isSystemBubble) avatarColor = RGB(100, 180, 255);
            else if (isCodeBubble) avatarColor = RGB(120, 150, 200);

            // Hover effect for AI/System/Error/Code bubbles with glow (isHovered already calculated above)
            if (isHovered) {
                // Brighten colors on hover with glow effect
                bubbleFill = RGB(
                    GetRValue(bubbleFill) + 8,
                    GetGValue(bubbleFill) + 8,
                    GetBValue(bubbleFill) + 8
                );
                bubbleBorder = RGB(
                    GetRValue(bubbleBorder) + 40,
                    GetGValue(bubbleBorder) + 40,
                    GetBValue(bubbleBorder) + 40
                );
                avatarColor = RGB(
                    GetRValue(avatarColor) + 40,
                    GetGValue(avatarColor) + 40,
                    GetBValue(avatarColor) + 40
                );
            }
            
            // Draw glow effect for hovered bubbles (subtle outer glow)
            if (isHovered) {
                RECT glowRect = bubbleRect;
                InflateRect(&glowRect, 3, 3);
                COLORREF glowColor = RGB(
                    GetRValue(bubbleBorder) / 3,
                    GetGValue(bubbleBorder) / 3,
                    GetBValue(bubbleBorder) / 3
                );
                auto glowPen = gdiManager_->CreatePen(PS_SOLID, 1, glowColor);
                HGDIOBJ oldGlowPen = SelectObject(hdc, glowPen->Get());
                HBRUSH oldGlowBrush = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
                RoundRect(hdc, glowRect.left, glowRect.top, glowRect.right, glowRect.bottom, 
                         bubbleRadius + 2, bubbleRadius + 2);
                SelectObject(hdc, oldGlowPen);
                SelectObject(hdc, oldGlowBrush);
                // Smart pointer automatically cleans up
            }
            
            auto bubbleBrush = gdiManager_->CreateSolidBrush(bubbleFill);
            auto bubblePen = gdiManager_->CreatePen(PS_SOLID, isHovered ? 2 : 1, bubbleBorder);
            HGDIOBJ oldBrush = SelectObject(hdc, bubbleBrush->Get());
            HGDIOBJ oldPen = SelectObject(hdc, bubblePen->Get());
            RoundRect(hdc, bubbleRect.left, bubbleRect.top, bubbleRect.right, bubbleRect.bottom,
                     bubbleRadius, bubbleRadius);
            SelectObject(hdc, oldBrush);
            SelectObject(hdc, oldPen);
            // Smart pointers automatically clean up
            
            // Apply hover effect to avatar (isHovered already declared above)
            if (isHovered) {
                avatarColor = RGB(
                    GetRValue(avatarColor) + 30,
                    GetGValue(avatarColor) + 30,
                    GetBValue(avatarColor) + 30
                );
            }
            
            // Draw avatar glow on hover for AI/System/Error/Code bubbles
            int ax = messageAreaLeft + aiMessageMarginLeft;
            int ay = bubbleRect.top + 4;
            if (isHovered) {
                int glowSize = avatarSize + 6;
                int glowX = ax - 3;
                int glowY = ay - 3;
                COLORREF glowColor = RGB(
                    GetRValue(avatarColor) / 4,
                    GetGValue(avatarColor) / 4,
                    GetBValue(avatarColor) / 4
                );
                HBRUSH glowBrush = CreateSolidBrush(glowColor);
                HPEN glowPen = CreatePen(PS_NULL, 0, glowColor);
                HGDIOBJ oldGlowBrush = SelectObject(hdc, glowBrush);
                HGDIOBJ oldGlowPen = SelectObject(hdc, glowPen);
                Ellipse(hdc, glowX, glowY, glowX + glowSize, glowY + glowSize);
                SelectObject(hdc, oldGlowBrush);
                SelectObject(hdc, oldGlowPen);
                DeleteObject(glowBrush);
                DeleteObject(glowPen);
            }
            
            HBRUSH avatarBrush = CreateSolidBrush(avatarColor);
            HPEN avatarPen = CreatePen(PS_NULL, 0, avatarColor);
            oldBrush = SelectObject(hdc, avatarBrush);
            oldPen = SelectObject(hdc, avatarPen);
            Ellipse(hdc, ax, ay, ax + avatarSize, ay + avatarSize);
            SelectObject(hdc, oldBrush);
            SelectObject(hdc, oldPen);
            DeleteObject(avatarBrush);
            DeleteObject(avatarPen);

            // Text (color already set above)
            if (isLoadingBubble) {
                textColor = RGB(154, 163, 195); // Dimmed for loading
            }
            SetTextColor(hdc, textColor);
            textDrawRect = bubbleRect;
            // Use code-specific padding for code bubbles
            if (isCodeBubble) {
                textDrawRect.left += codePaddingX;
                textDrawRect.right -= codePaddingX;
                textDrawRect.top += codePaddingY;
            } else {
                textDrawRect.left += bubblePaddingX;
                textDrawRect.right -= bubblePaddingX;
                textDrawRect.top += bubblePaddingY;
            }
            textDrawRect.bottom = textDrawRect.top + textHeight;
            // Use monospace font for code bubbles
            if (isCodeBubble) {
                SelectObject(hdc, hCodeFont_->Get());
            }
            
            // Draw search highlights first (behind text)
            if (searchVisible_ && !searchQuery_.empty()) {
                HFONT highlightFont = isCodeBubble ? hCodeFont_->Get() : hAIMessageFont_->Get();
                DrawSearchHighlight(hdc, msg.text, textDrawRect, highlightFont);
            }
            
            DrawTextW(hdc, msg.text.c_str(), -1, &textDrawRect, DT_LEFT | DT_WORDBREAK);

            // Timestamp
            SelectObject(hdc, hMetaFont_->Get());
            SetTextColor(hdc, RGB(154, 163, 195));
            RECT metaRect = textDrawRect;
            metaRect.top = textDrawRect.bottom + 4;
            metaRect.bottom = bubbleRect.bottom - bubblePaddingY + 2;
            DrawTextW(hdc, msg.timestamp.c_str(), -1, &metaRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
        }
        
        // Draw copy icon or checkmark when hovering over message or after copying
        int msgIndex = static_cast<int>(msgIdx);
        bool shouldShowIcon = (isHovered && msgIndex >= 0) || (copiedMessageIndex_ == msgIndex);
        if (shouldShowIcon && msgIndex >= 0) {
            RECT copyIconRect = GetCopyIconRect(msgIndex);
            if (copyIconRect.right > copyIconRect.left && copyIconRect.bottom > copyIconRect.top) {
                int iconSize = 16;
                bool isCopied = (copiedMessageIndex_ == msgIndex);
                
                if (isCopied) {
                    // Draw checkmark (smooth transition from copy icon)
                    COLORREF checkmarkColor = RGB(74, 215, 255); // Cyan color for checkmark
                    auto checkmarkPen = gdiManager_->CreatePen(PS_SOLID, 2, checkmarkColor);
                    HGDIOBJ oldCheckmarkPen = SelectObject(hdc, checkmarkPen->Get());
                    
                    // Draw checkmark (V shape) - centered in icon area
                    int iconX = copyIconRect.left;
                    int iconY = copyIconRect.top;
                    int checkX = iconX + 3;
                    int checkY = iconY + iconSize / 2;
                    int checkSize = 10;
                    
                    // Left part of checkmark
                    MoveToEx(hdc, checkX, checkY, NULL);
                    LineTo(hdc, checkX + 3, checkY + 3);
                    
                    // Right part of checkmark
                    MoveToEx(hdc, checkX + 3, checkY + 3, NULL);
                    LineTo(hdc, checkX + checkSize, checkY - 3);
                    
                    SelectObject(hdc, oldCheckmarkPen);
                    // Smart pointer automatically cleans up
                } else {
                    // Draw copy icon (simple rectangle with lines representing copy symbol)
                    COLORREF iconColor = RGB(154, 163, 195);
                    if (hoveredCopyIconIndex_ == msgIndex) {
                        iconColor = RGB(74, 215, 255); // Brighter when hovering icon
                    }
                    
                    auto iconPen = gdiManager_->CreatePen(PS_SOLID, 1, iconColor);
                    HGDIOBJ oldIconPen = SelectObject(hdc, iconPen->Get());
                    HBRUSH oldIconBrush = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
                    
                    // Draw copy icon: two overlapping rectangles
                    int iconX = copyIconRect.left;
                    int iconY = copyIconRect.top;
                    // Main rectangle
                    Rectangle(hdc, iconX, iconY, iconX + iconSize, iconY + iconSize);
                    // Overlapping rectangle (offset)
                    Rectangle(hdc, iconX + 3, iconY + 3, iconX + iconSize + 3, iconY + iconSize + 3);
                    
                    SelectObject(hdc, oldIconPen);
                    SelectObject(hdc, oldIconBrush);
                    // Smart pointer automatically cleans up
                }
            }
        }
        
        currentY += bubbleHeight + messageMarginY;
    }
    
    SelectObject(hdc, oldFont);
    // Fonts are managed by smart pointers, no manual cleanup needed
}