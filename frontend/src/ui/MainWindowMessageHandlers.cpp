#include <windows.h>
#include <windowsx.h>
#include "MainWindow.h"
#include "UiConstants.h"
#include "UiConfig.h"

// Message handling functions extracted from MainWindow.cpp
// This file handles window messages and delegates to appropriate handlers

// Handle mouse wheel scrolling for sidebar
void MainWindow::HandleSidebarMouseWheel(WPARAM wParam) {
    using namespace UiConstants;
    
    POINT pt;
    GetCursorPos(&pt);
    ScreenToClient(hwnd_, &pt);

    if (!sidebarVisible_ || pt.x < 0 || pt.x >= sidebarWidth_) {
        return;
    }

    int delta = GET_WHEEL_DELTA_WPARAM(wParam);
    int step = (delta / WHEEL_DELTA) * Sidebar::SCROLL_PIXELS_PER_NOTCH;

    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    int headerH = theme_.headerHeight;

    int itemHeight = Sidebar::ITEM_HEIGHT;
    int titleTop = (newSessionButtonRect_.bottom > 0)
        ? newSessionButtonRect_.bottom + Sidebar::SPACING_AFTER_BUTTON
        : headerH + Sidebar::SPACING_FROM_HEADER;
    int titleHeight = Sidebar::TITLE_HEIGHT;
    int startY = titleTop + titleHeight + Sidebar::SPACING_AFTER_TITLE;

    int visibleHeight = clientRect.bottom - startY;
    if (visibleHeight < 0) visibleHeight = 0;

    int contentHeight = itemHeight * static_cast<int>(conversations_.size());
    int maxScroll = (contentHeight > visibleHeight) ? (contentHeight - visibleHeight) : 0;

    sidebarScrollOffset_ -= step;
    if (sidebarScrollOffset_ < 0) sidebarScrollOffset_ = 0;
    if (sidebarScrollOffset_ > maxScroll) sidebarScrollOffset_ = maxScroll;

    // Only invalidate sidebar region to avoid flickering
    RECT sidebarRect = { 0, headerH, sidebarWidth_, clientRect.bottom };
    InvalidateRect(hwnd_, &sidebarRect, FALSE);
}

// Handle mouse wheel scrolling for chat messages
void MainWindow::HandleChatMouseWheel(WPARAM wParam) {
    using namespace UiConstants;
    
    int delta = GET_WHEEL_DELTA_WPARAM(wParam);
    int step = (delta / WHEEL_DELTA) * Input::CHAT_SCROLL_PIXELS_PER_NOTCH;

    // Wheel up = move content up => decrease scrollOffset_
    chatViewState_.scrollOffset -= step;
    if (chatViewState_.scrollOffset < 0) chatViewState_.scrollOffset = 0;

    // User is manually scrolling; stop auto-pinning to bottom
    chatViewState_.autoScrollToBottom = false;

    // Only invalidate chat messages region, avoid input & send button to prevent flickering
    RECT chatRect;
    int headerH = theme_.headerHeight;
    int contentLeft = sidebarVisible_ ? sidebarWidth_ : 0;

    chatRect.left = contentLeft;
    chatRect.top = headerH;
    chatRect.right = windowWidth_;
    // Limit bottom to just above input field
    chatRect.bottom = inputRect_.top > 0 ? inputRect_.top - Spacing::INPUT_TOP_MARGIN : windowHeight_;

    // Ensure rect is valid before painting
    if (chatRect.bottom < chatRect.top) {
        chatRect.bottom = chatRect.top;
    }

    InvalidateRect(hwnd_, &chatRect, FALSE);
}

// Handle timer events
void MainWindow::HandleTimer(WPARAM wParam) {
    using namespace UiConstants;
    
    if (wParam == Animation::TIMER_ID_COPY_FEEDBACK) {
        // Copy feedback timer - reset checkmark back to copy icon
        if (copiedMessageIndex_ >= 0) {
            RECT iconRect = GetCopyIconRect(copiedMessageIndex_);
            InflateRect(&iconRect, Message::ICON_INFLATE_SIZE, Message::ICON_INFLATE_SIZE);
            InvalidateRect(hwnd_, &iconRect, FALSE);
            copiedMessageIndex_ = -1;
        }
        if (copyFeedbackTimerId_ != 0) {
            KillTimer(hwnd_, copyFeedbackTimerId_);
            copyFeedbackTimerId_ = 0;
        }
        return;
    }
    
    if (wParam == Animation::TIMER_ID_INPUT && chatViewState_.isAnimating) {
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
                return;
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
        return;
    }
    
    if (wParam == Animation::TIMER_ID_HEALTH_CHECK) {
        // Health check timer
        CheckHealthStatus();
        return;
    }
}

// Handle keyboard shortcuts
void MainWindow::HandleKeyDown(WPARAM wParam) {
    using namespace UiConstants;
    
    if (wParam == VK_ESCAPE) {
        // If search bar is visible, close it first
        if (searchVisible_) {
            HideSearchBar();
            return;
        }
        // If input has focus, clear it
        if (GetFocus() == hChatInput_) {
            ClearEdit(hChatInput_);
            chatViewState_.showPlaceholder = true;
            InvalidateRect(hwnd_, &inputRect_, FALSE);
            return;
        } else {
            // Esc outside input -> confirm exit with custom dark theme dialog
            if (ShowExitConfirmationDialog()) {
                PostMessage(hwnd_, WM_CLOSE, 0, 0);
            }
            return;
        }
    }
    
    if (wParam == 'L' && (GetKeyState(VK_CONTROL) & 0x8000)) {
        // Ctrl+L -> focus input
        SetFocus(hChatInput_);
        return;
    }
    
    if (wParam == 'F' && (GetKeyState(VK_CONTROL) & 0x8000)) {
        // Ctrl+F -> toggle search bar
        if (searchVisible_) {
            HideSearchBar();
        } else {
            ShowSearchBar();
        }
        return;
    }
    
    // Ctrl+Enter handling is done in EditProc
}

// Handle left mouse button down
void MainWindow::HandleLeftButtonDown(LPARAM lParam) {
    using namespace UiConstants;
    
    POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };
    
    // Check if click is on settings icon
    if (PtInRect(&settingsIconRect_, pt)) {
        HandleSettingsIconClick();
        return;
    }

    // Check click on search buttons (if search bar is visible)
    if (searchVisible_) {
        if (PtInRect(&searchPrevButtonRect_, pt)) {
            NavigateToSearchResult(-1);
            return;
        }
        if (PtInRect(&searchNextButtonRect_, pt)) {
            NavigateToSearchResult(1);
            return;
        }
        if (PtInRect(&searchCloseButtonRect_, pt)) {
            HideSearchBar();
            return;
        }
    }
    
    // Check click on custom send button
    if (sendButtonRect_.right > sendButtonRect_.left &&
        sendButtonRect_.bottom > sendButtonRect_.top &&
        PtInRect(&sendButtonRect_, pt)) {
        SendChatMessage();
        return;
    }
    
    // Check click on copy icon
    if (hoveredCopyIconIndex_ >= 0 && 
        static_cast<size_t>(hoveredCopyIconIndex_) < chatViewState_.messages.size()) {
        RECT copyIconRect = GetCopyIconRect(hoveredCopyIconIndex_);
        if (PtInRect(&copyIconRect, pt)) {
            CopyMessageToClipboard(hoveredCopyIconIndex_);
            return;
        }
    }
    
    // Check double-click on message bubble to copy
    DWORD currentTime = GetTickCount();
    if (hoveredMessageIndex_ >= 0 && 
        static_cast<size_t>(hoveredMessageIndex_) < chatViewState_.messages.size()) {
        if (lastClickIndex_ == hoveredMessageIndex_ && 
            (currentTime - lastClickTime_) < Interaction::DOUBLE_CLICK_WINDOW_MS) {
            CopyMessageToClipboard(hoveredMessageIndex_);
            lastClickTime_ = 0;
            lastClickIndex_ = -1;
            return;
        } else {
            lastClickTime_ = currentTime;
            lastClickIndex_ = hoveredMessageIndex_;
        }
    }
    
    // Check if click is in sidebar
    if (sidebarVisible_ && pt.x >= 0 && pt.x < sidebarWidth_) {
        int headerH = theme_.headerHeight;

        // Hit test "Chat Mới" button
        if (newSessionButtonRect_.right > newSessionButtonRect_.left &&
            newSessionButtonRect_.bottom > newSessionButtonRect_.top &&
            PtInRect(&newSessionButtonRect_, pt)) {
            // Reuse existing logic via WM_COMMAND 1004
            SendMessage(hwnd_, WM_COMMAND, MAKELONG(1004, BN_CLICKED), 0);
            return;
        }
        
        int itemHeight = Sidebar::ITEM_HEIGHT;
        int titleTop = (newSessionButtonRect_.bottom > 0)
            ? newSessionButtonRect_.bottom + Sidebar::SPACING_AFTER_BUTTON
            : headerH + Sidebar::SPACING_FROM_HEADER;
        int titleHeight = Sidebar::TITLE_HEIGHT;
        int startY = titleTop + titleHeight + Sidebar::SPACING_AFTER_TITLE;
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
}

// Handle mouse move
void MainWindow::HandleMouseMove(LPARAM lParam) {
    POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };

    // Track hover state for custom send button
    if (sendButtonRect_.right > sendButtonRect_.left &&
        sendButtonRect_.bottom > sendButtonRect_.top) {
        bool hovering = PtInRect(&sendButtonRect_, pt);
        if (hovering != isSendButtonHover_) {
            isSendButtonHover_ = hovering;
            InvalidateRect(hwnd_, &sendButtonRect_, FALSE);
        }
    }

    // Track hover state for "Chat Mới" button
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
    
    // Track hover state for search buttons
    if (searchVisible_) {
        bool prevHovering = PtInRect(&searchPrevButtonRect_, pt);
        bool nextHovering = PtInRect(&searchNextButtonRect_, pt);
        bool closeHovering = PtInRect(&searchCloseButtonRect_, pt);
        
        if (prevHovering != isSearchPrevButtonHover_) {
            isSearchPrevButtonHover_ = prevHovering;
            InvalidateRect(hwnd_, &searchPrevButtonRect_, FALSE);
        }
        if (nextHovering != isSearchNextButtonHover_) {
            isSearchNextButtonHover_ = nextHovering;
            InvalidateRect(hwnd_, &searchNextButtonRect_, FALSE);
        }
        if (closeHovering != isSearchCloseButtonHover_) {
            isSearchCloseButtonHover_ = closeHovering;
            InvalidateRect(hwnd_, &searchCloseButtonRect_, FALSE);
        }
    }

    // Track hover state for sidebar conversation items
    if (sidebarVisible_ && pt.x >= 0 && pt.x < sidebarWidth_) {
        using namespace UiConstants;
        
        int headerH = theme_.headerHeight;
        int itemHeight = Sidebar::ITEM_HEIGHT;
        int titleTop = (newSessionButtonRect_.bottom > 0)
            ? newSessionButtonRect_.bottom + Sidebar::SPACING_AFTER_BUTTON
            : headerH + Sidebar::SPACING_FROM_HEADER;
        int titleHeight = Sidebar::TITLE_HEIGHT;
        int startY = titleTop + titleHeight + Sidebar::SPACING_AFTER_TITLE;

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
}

// Handle mouse leave
void MainWindow::HandleMouseLeave() {
    // Hide tooltip when mouse leaves window
    HideMessageTooltip();
    int oldHovered = hoveredMessageIndex_;
    int oldCopyHovered = hoveredCopyIconIndex_;
    hoveredMessageIndex_ = -1;
    hoveredCopyIconIndex_ = -1;
    
    // Reset search button hover states
    bool needInvalidate = false;
    if (isSearchPrevButtonHover_) {
        isSearchPrevButtonHover_ = false;
        needInvalidate = true;
    }
    if (isSearchNextButtonHover_) {
        isSearchNextButtonHover_ = false;
        needInvalidate = true;
    }
    if (isSearchCloseButtonHover_) {
        isSearchCloseButtonHover_ = false;
        needInvalidate = true;
    }
    
    if (oldHovered != -1 || oldCopyHovered != -1 || needInvalidate) {
        InvalidateRect(hwnd_, NULL, FALSE);
    }
}