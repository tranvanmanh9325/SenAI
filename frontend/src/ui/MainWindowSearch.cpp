#include <windows.h>
#include <windowsx.h>
#include "MainWindow.h"
#include "UiConstants.h"
#include <algorithm>
#include <cctype>
#include <cwctype>
#include <string>

// Search functionality implementation

// Case-insensitive string comparison helper
bool CaseInsensitiveContains(const std::wstring& text, const std::wstring& query) {
    if (query.empty()) return false;
    if (text.length() < query.length()) return false;
    
    for (size_t i = 0; i <= text.length() - query.length(); ++i) {
        bool match = true;
        for (size_t j = 0; j < query.length(); ++j) {
            if (towlower(text[i + j]) != towlower(query[j])) {
                match = false;
                break;
            }
        }
        if (match) return true;
    }
    return false;
}

// Find all matches in text (returns pairs of start and end positions)
std::vector<std::pair<size_t, size_t>> MainWindow::FindTextMatches(const std::wstring& text, const std::wstring& query) {
    std::vector<std::pair<size_t, size_t>> matches;
    if (query.empty() || text.empty()) return matches;
    
    std::wstring lowerText = text;
    std::wstring lowerQuery = query;
    std::transform(lowerText.begin(), lowerText.end(), lowerText.begin(), towlower);
    std::transform(lowerQuery.begin(), lowerQuery.end(), lowerQuery.begin(), towlower);
    
    size_t pos = 0;
    while ((pos = lowerText.find(lowerQuery, pos)) != std::wstring::npos) {
        matches.push_back({pos, pos + query.length()});
        pos += query.length();
    }
    
    return matches;
}

// Show search bar
void MainWindow::ShowSearchBar() {
    if (searchVisible_) return;
    
    searchVisible_ = true;
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    
    int headerH = theme_.headerHeight;
    int searchBarHeight = 40;
    int searchBarY = headerH + 2;
    
    // Calculate search bar position (below header, spanning full width)
    int sidebarOffset = sidebarVisible_ ? sidebarWidth_ : 0;
    int searchBarLeft = sidebarOffset + 16;
    int searchBarWidth = clientRect.right - sidebarOffset - 32;
    int searchBarRight = searchBarLeft + searchBarWidth;
    
    searchBarRect_.left = searchBarLeft;
    searchBarRect_.top = searchBarY;
    searchBarRect_.right = searchBarRight;
    searchBarRect_.bottom = searchBarY + searchBarHeight;
    
    // Create search edit control
    HINSTANCE hInst = hInstance_ ? hInstance_ : GetModuleHandle(NULL);
    hSearchEdit_ = CreateWindowW(L"EDIT", L"",
        WS_CHILD | WS_VISIBLE | ES_LEFT | ES_AUTOHSCROLL,
        searchBarLeft + 8, searchBarY + 8, searchBarWidth - 200, 24,
        hwnd_, (HMENU)2001, hInst, NULL);
    
    if (hSearchEdit_) {
        SendMessage(hSearchEdit_, WM_SETFONT, (WPARAM)hInputFont_->Get(), TRUE);
        SetWindowTextW(hSearchEdit_, L"");
    }
    
    // Calculate button positions (custom drawn, no Windows controls)
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
    
    // Set focus to search edit
    if (hSearchEdit_) {
        SetFocus(hSearchEdit_);
    }
    
    // Invalidate search bar area
    RECT invalidateRect = searchBarRect_;
    invalidateRect.bottom += 4; // Include some space below
    InvalidateRect(hwnd_, &invalidateRect, FALSE);
}

// Hide search bar
void MainWindow::HideSearchBar() {
    if (!searchVisible_) return;
    
    searchVisible_ = false;
    searchQuery_.clear();
    searchResults_.clear();
    currentSearchIndex_ = -1;
    
    if (hSearchEdit_) {
        DestroyWindow(hSearchEdit_);
        hSearchEdit_ = NULL;
    }
    
    // Reset hover states
    isSearchPrevButtonHover_ = false;
    isSearchNextButtonHover_ = false;
    isSearchCloseButtonHover_ = false;
    
    // Invalidate search bar area
    RECT invalidateRect = searchBarRect_;
    invalidateRect.bottom += 4;
    InvalidateRect(hwnd_, &invalidateRect, FALSE);
    
    // Invalidate chat messages to remove highlights
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    int headerH = theme_.headerHeight;
    int contentLeft = sidebarVisible_ ? sidebarWidth_ : 0;
    RECT chatRect = {contentLeft, headerH, clientRect.right, clientRect.bottom};
    InvalidateRect(hwnd_, &chatRect, FALSE);
}

// Perform search
void MainWindow::PerformSearch(const std::wstring& query) {
    searchQuery_ = query;
    searchResults_.clear();
    currentSearchIndex_ = -1;
    
    if (query.empty()) {
        // Invalidate to remove highlights
        RECT clientRect;
        GetClientRect(hwnd_, &clientRect);
        int headerH = theme_.headerHeight;
        int contentLeft = sidebarVisible_ ? sidebarWidth_ : 0;
        RECT chatRect = {contentLeft, headerH, clientRect.right, clientRect.bottom};
        InvalidateRect(hwnd_, &chatRect, FALSE);
        return;
    }
    
    // Search through all messages
    for (size_t i = 0; i < chatViewState_.messages.size(); ++i) {
        const auto& msg = chatViewState_.messages[i];
        if (CaseInsensitiveContains(msg.text, query)) {
            searchResults_.push_back(static_cast<int>(i));
        }
    }
    
    // If we have results, navigate to first one
    if (!searchResults_.empty()) {
        currentSearchIndex_ = 0;
        NavigateToSearchResult(0); // Navigate to first result
    }
    
    // Invalidate chat messages to show highlights
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    int headerH = theme_.headerHeight;
    int contentLeft = sidebarVisible_ ? sidebarWidth_ : 0;
    RECT chatRect = {contentLeft, headerH, clientRect.right, clientRect.bottom};
    InvalidateRect(hwnd_, &chatRect, FALSE);
}

// Navigate to search result
void MainWindow::NavigateToSearchResult(int direction) {
    if (searchResults_.empty()) return;
    
    if (direction == 0) {
        // Navigate to specific index (used for first result)
        if (currentSearchIndex_ >= 0 && currentSearchIndex_ < static_cast<int>(searchResults_.size())) {
            ScrollToSearchResult(searchResults_[currentSearchIndex_]);
        }
        return;
    }
    
    // Navigate next/previous
    if (direction > 0) {
        // Next
        currentSearchIndex_++;
        if (currentSearchIndex_ >= static_cast<int>(searchResults_.size())) {
            currentSearchIndex_ = 0; // Wrap around
        }
    } else {
        // Previous
        currentSearchIndex_--;
        if (currentSearchIndex_ < 0) {
            currentSearchIndex_ = static_cast<int>(searchResults_.size()) - 1; // Wrap around
        }
    }
    
    if (currentSearchIndex_ >= 0 && currentSearchIndex_ < static_cast<int>(searchResults_.size())) {
        ScrollToSearchResult(searchResults_[currentSearchIndex_]);
    }
}

// Scroll to search result
void MainWindow::ScrollToSearchResult(int messageIndex) {
    if (messageIndex < 0 || static_cast<size_t>(messageIndex) >= chatViewState_.messages.size()) {
        return;
    }
    
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    
    int headerH = theme_.headerHeight;
    int inputHeight = 60;
    int marginBottom = 20;
    int messageAreaTop = headerH + (searchVisible_ ? 50 : 20);
    int messageAreaBottom = clientRect.bottom - inputHeight - marginBottom;
    int availableHeight = messageAreaBottom - messageAreaTop;
    
    // Calculate total height up to target message
    int totalHeight = 0;
    int messageMarginY = theme_.messageMarginY;
    int bubblePaddingY = 12;
    
    for (int i = 0; i < messageIndex; ++i) {
        const auto& msg = chatViewState_.messages[i];
        // Estimate message height (simplified)
        int estimatedHeight = 60; // Default estimate
        totalHeight += estimatedHeight + messageMarginY;
    }
    
    // Calculate scroll offset to center the message
    int targetScroll = totalHeight - (availableHeight / 2);
    if (targetScroll < 0) targetScroll = 0;
    
    chatViewState_.scrollOffset = targetScroll;
    chatViewState_.autoScrollToBottom = false;
    
    // Invalidate chat area
    int contentLeft = sidebarVisible_ ? sidebarWidth_ : 0;
    RECT chatRect = {contentLeft, messageAreaTop, clientRect.right, messageAreaBottom};
    InvalidateRect(hwnd_, &chatRect, FALSE);
}

// Draw search bar
void MainWindow::DrawSearchBar(HDC hdc) {
    if (!searchVisible_) return;
    
    // Draw search bar background
    HBRUSH searchBgBrush = CreateSolidBrush(RGB(20, 28, 50));
    FillRect(hdc, &searchBarRect_, searchBgBrush);
    DeleteObject(searchBgBrush);
    
    // Draw top and bottom borders (thin lines)
    HPEN borderPen = CreatePen(PS_SOLID, 1, RGB(74, 215, 255));
    HGDIOBJ oldPen = SelectObject(hdc, borderPen);
    // Top border
    MoveToEx(hdc, searchBarRect_.left, searchBarRect_.top, NULL);
    LineTo(hdc, searchBarRect_.right, searchBarRect_.top);
    // Bottom border
    MoveToEx(hdc, searchBarRect_.left, searchBarRect_.bottom - 1, NULL);
    LineTo(hdc, searchBarRect_.right, searchBarRect_.bottom - 1);
    SelectObject(hdc, oldPen);
    DeleteObject(borderPen);
    
    // Draw custom buttons
    DrawSearchButton(hdc, searchPrevButtonRect_, L"◀", isSearchPrevButtonHover_);
    DrawSearchButton(hdc, searchNextButtonRect_, L"▶", isSearchNextButtonHover_);
    DrawSearchButton(hdc, searchCloseButtonRect_, L"✕", isSearchCloseButtonHover_);
    
    // Draw result count if we have results
    if (!searchQuery_.empty() && !searchResults_.empty()) {
        SetBkMode(hdc, TRANSPARENT);
        SetTextColor(hdc, RGB(154, 163, 195));
        SelectObject(hdc, hMetaFont_->Get());
        
        wchar_t resultText[64];
        swprintf_s(resultText, L"%d / %d", currentSearchIndex_ + 1, static_cast<int>(searchResults_.size()));
        
        RECT resultRect = searchBarRect_;
        resultRect.left = searchPrevButtonRect_.left - 80;
        resultRect.right = searchPrevButtonRect_.left - 10;
        DrawTextW(hdc, resultText, -1, &resultRect, DT_RIGHT | DT_VCENTER | DT_SINGLELINE);
    }
}

// Draw search button (custom drawn)
void MainWindow::DrawSearchButton(HDC hdc, const RECT& rect, const wchar_t* text, bool isHovered) {
    // Button background color (light gray - darker than white but still light)
    // Normal: RGB(200, 200, 200) - light gray
    // Hovered: RGB(180, 180, 180) - slightly darker gray
    COLORREF bgColor = isHovered ? RGB(180, 180, 180) : RGB(200, 200, 200);
    
    // Draw shadow first (offset down and right, darker gray)
    RECT shadowRect = rect;
    OffsetRect(&shadowRect, 2, 2);
    HBRUSH shadowBrush = CreateSolidBrush(RGB(140, 140, 140));
    int radius = 4;
    HGDIOBJ oldShadowBrush = SelectObject(hdc, shadowBrush);
    RoundRect(hdc, shadowRect.left, shadowRect.top, shadowRect.right, shadowRect.bottom, radius, radius);
    SelectObject(hdc, oldShadowBrush);
    DeleteObject(shadowBrush);
    
    // Draw button background
    HBRUSH bgBrush = CreateSolidBrush(bgColor);
    HPEN borderPen = CreatePen(PS_SOLID, 1, RGB(170, 170, 170));
    
    HGDIOBJ oldBrush = SelectObject(hdc, bgBrush);
    HGDIOBJ oldPen = SelectObject(hdc, borderPen);
    
    // Draw button with rounded corners
    RoundRect(hdc, rect.left, rect.top, rect.right, rect.bottom, radius, radius);
    
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
    DeleteObject(bgBrush);
    DeleteObject(borderPen);
    
    // Draw button text (black)
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(0, 0, 0));
    SelectObject(hdc, hInputFont_->Get());
    
    RECT textRect = rect;
    DrawTextW(hdc, text, -1, &textRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
}

// Draw search highlight in text
void MainWindow::DrawSearchHighlight(HDC hdc, const std::wstring& text, const RECT& textRect, HFONT hFont) {
    if (searchQuery_.empty() || text.empty()) return;
    
    // Get matches
    auto matches = FindTextMatches(text, searchQuery_);
    if (matches.empty()) return;
    
    // Select font for text measurement
    HGDIOBJ oldFont = SelectObject(hdc, hFont);
    
    // Calculate character positions
    std::vector<int> charXPositions;
    charXPositions.reserve(text.length() + 1);
    
    int currentX = textRect.left;
    charXPositions.push_back(currentX);
    
    for (size_t i = 0; i < text.length(); ++i) {
        wchar_t ch = text[i];
        SIZE charSize;
        GetTextExtentPoint32W(hdc, &ch, 1, &charSize);
        currentX += charSize.cx;
        charXPositions.push_back(currentX);
    }
    
    // Draw highlights with a more visible color
    COLORREF highlightColor = RGB(255, 255, 100); // Bright yellow highlight
    HBRUSH highlightBrush = CreateSolidBrush(highlightColor);
    HGDIOBJ oldBrush = SelectObject(hdc, highlightBrush);
    
    // Set background mode to opaque for highlights
    int oldBkMode = SetBkMode(hdc, OPAQUE);
    SetBkColor(hdc, highlightColor);
    
    for (const auto& match : matches) {
        int startX = charXPositions[match.first];
        int endX = charXPositions[match.second];
        
        // Draw highlight rectangle
        RECT highlightRect = {startX, textRect.top, endX, textRect.bottom};
        FillRect(hdc, &highlightRect, highlightBrush);
    }
    
    // Restore background mode
    SetBkMode(hdc, oldBkMode);
    
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldFont);
    DeleteObject(highlightBrush);
}