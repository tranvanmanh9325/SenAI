#include <windows.h>
#include "MainWindow.h"
#include <string>

// Sidebar and header controls rendering split from MainWindowRender.cpp

void MainWindow::DrawSidebar(HDC hdc) {
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    
    int headerH = theme_.headerHeight;
    int sidebarX = 0;
    int sidebarY = headerH;
    int sidebarW = sidebarWidth_;
    int sidebarH = clientRect.bottom - headerH;
    
    RECT sidebarRect = {sidebarX, sidebarY, sidebarX + sidebarW, sidebarY + sidebarH};
    
    // Background
    HBRUSH sidebarBrush = CreateSolidBrush(RGB(12, 18, 32));
    FillRect(hdc, &sidebarRect, sidebarBrush);
    DeleteObject(sidebarBrush);
    
    // Border on right
    HPEN borderPen = CreatePen(PS_SOLID, 1, RGB(40, 50, 70));
    HGDIOBJ oldPen = SelectObject(hdc, borderPen);
    MoveToEx(hdc, sidebarRect.right - 1, sidebarRect.top, NULL);
    LineTo(hdc, sidebarRect.right - 1, sidebarRect.bottom);
    SelectObject(hdc, oldPen);
    DeleteObject(borderPen);
    
    // Vẽ nút "Chat Mới" phía trên title (custom draw, không dùng child window để tránh nhấp nháy)
    if (newSessionButtonRect_.right > newSessionButtonRect_.left &&
        newSessionButtonRect_.bottom > newSessionButtonRect_.top) {
        DrawNewSessionButton(hdc, newSessionButtonRect_, false);
    }

    // Title
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(200, 210, 230));
    HFONT titleFont = CreateFontW(-18, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    HFONT oldFont = (HFONT)SelectObject(hdc, titleFont);
    
    int titleTop = newSessionButtonRect_.bottom > 0
        ? newSessionButtonRect_.bottom + 12
        : sidebarY + 12;
    RECT titleRect = {sidebarX + 16, titleTop, sidebarRect.right - 16, titleTop + 28};
    DrawTextW(hdc, L"Lịch sử", -1, &titleRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
    
    SelectObject(hdc, oldFont);
    DeleteObject(titleFont);
    
    // List conversations
    int itemHeight = 75;  // Tăng chiều cao item một chút
    int itemPaddingX = 16; // Tăng padding để dễ đọc hơn
    int itemPaddingY = 8;
    int startY = titleRect.bottom + 12;
    // Visible height from list top to bottom of sidebar (avoid header overlap)
    int contentTop = startY;
    int contentBottom = sidebarRect.bottom;
    int visibleHeight = contentBottom - contentTop;
    if (visibleHeight < 0) visibleHeight = 0;
    
    HFONT itemFont = CreateFontW(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    HFONT metaFont = CreateFontW(-13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    
    int currentY = startY - sidebarScrollOffset_;

    // Clip drawing to the list region so items never paint into header
    int savedDC = SaveDC(hdc);
    IntersectClipRect(hdc, sidebarRect.left, contentTop, sidebarRect.right, contentBottom);
    
    for (size_t i = 0; i < conversations_.size(); i++) {
        if (currentY > contentBottom) break;
        if (currentY + itemHeight < contentTop) {
            currentY += itemHeight;
            continue;
        }
        
        RECT itemRect = {
            sidebarX + itemPaddingX,
            currentY,
            sidebarRect.right - itemPaddingX,
            currentY + itemHeight
        };
        
        bool isSelected = (selectedConversationIndex_ >= 0 && 
                          static_cast<size_t>(selectedConversationIndex_) == i);
        bool isHovered = (!isSelected &&
                          hoveredConversationIndex_ >= 0 &&
                          static_cast<size_t>(hoveredConversationIndex_) == i);
        
        // Background với màu tối hơn cho selected/hover đồng bộ UI (không dùng nền trắng)
        COLORREF bgColor = isSelected ? RGB(24, 35, 55)
                           : (isHovered ? RGB(22, 30, 46) : RGB(18, 26, 40));
        HBRUSH itemBrush = CreateSolidBrush(bgColor);
        FillRect(hdc, &itemRect, itemBrush);
        DeleteObject(itemBrush);
        
        // Border highlight cho selected item với màu cyan đồng bộ theme
        if (isSelected) {
            // Vẽ border với màu cyan glow
            HPEN highlightPen = CreatePen(PS_SOLID, 2, theme_.colorHeaderLine);
            HGDIOBJ oldPen2 = SelectObject(hdc, highlightPen);
            RoundRect(hdc, itemRect.left, itemRect.top, itemRect.right, itemRect.bottom, 10, 10);
            SelectObject(hdc, oldPen2);
            DeleteObject(highlightPen);
            
            // Thêm một lớp nền nhẹ với màu cyan để tạo glow effect
            RECT glowRect = itemRect;
            InflateRect(&glowRect, -2, -2);
            HBRUSH glowBrush = CreateSolidBrush(RGB(20, 50, 80));
            HPEN glowPen = CreatePen(PS_SOLID, 1, RGB(40, 100, 140));
            HGDIOBJ oldGlowBrush = SelectObject(hdc, glowBrush);
            HGDIOBJ oldGlowPen = SelectObject(hdc, glowPen);
            RoundRect(hdc, glowRect.left, glowRect.top, glowRect.right, glowRect.bottom, 8, 8);
            SelectObject(hdc, oldGlowBrush);
            SelectObject(hdc, oldGlowPen);
            DeleteObject(glowBrush);
            DeleteObject(glowPen);
        } else if (isHovered) {
            // Subtle border and glow on hover (cyan tint, no white)
            HPEN hoverPen = CreatePen(PS_SOLID, 1, RGB(70, 140, 200));
            HGDIOBJ oldPen2 = SelectObject(hdc, hoverPen);
            RoundRect(hdc, itemRect.left, itemRect.top, itemRect.right, itemRect.bottom, 10, 10);
            SelectObject(hdc, oldPen2);
            DeleteObject(hoverPen);

            RECT glowRect = itemRect;
            InflateRect(&glowRect, -3, -3);
            HBRUSH glowBrush = CreateSolidBrush(RGB(20, 34, 54));
            HPEN glowPen = CreatePen(PS_SOLID, 1, RGB(50, 100, 150));
            HGDIOBJ oldGlowBrush = SelectObject(hdc, glowBrush);
            HGDIOBJ oldGlowPen = SelectObject(hdc, glowPen);
            RoundRect(hdc, glowRect.left, glowRect.top, glowRect.right, glowRect.bottom, 8, 8);
            SelectObject(hdc, oldGlowBrush);
            SelectObject(hdc, oldGlowPen);
            DeleteObject(glowBrush);
            DeleteObject(glowPen);
        }
        
        // Preview text với màu sáng hơn khi selected
        SelectObject(hdc, itemFont);
        SetTextColor(hdc, isSelected ? RGB(240, 245, 255)
                                     : (isHovered ? RGB(215, 230, 250) : RGB(200, 210, 230)));
        RECT previewRect = itemRect;
        previewRect.left += 4;
        previewRect.top += 8;
        previewRect.right -= 4;
        previewRect.bottom = previewRect.top + 24;
        DrawTextW(hdc, conversations_[i].preview.c_str(), -1, &previewRect,
                  DT_LEFT | DT_TOP | DT_WORDBREAK | DT_END_ELLIPSIS);
        
        // Timestamp với màu sáng hơn khi selected
        SelectObject(hdc, metaFont);
        SetTextColor(hdc, isSelected ? RGB(160, 200, 240)
                                     : (isHovered ? RGB(150, 180, 210) : RGB(140, 150, 180)));
        RECT timeRect = previewRect;
        timeRect.top = previewRect.bottom + 4;
        timeRect.bottom = itemRect.bottom - 8;
        DrawTextW(hdc, conversations_[i].timestamp.c_str(), -1, &timeRect,
                  DT_LEFT | DT_BOTTOM | DT_SINGLELINE);
        
        currentY += itemHeight;
    }
    
    SelectObject(hdc, oldFont);
    DeleteObject(itemFont);
    DeleteObject(metaFont);
    RestoreDC(hdc, savedDC);
}

void MainWindow::DrawNewSessionButton(HDC hdc, const RECT& rc, bool isPressed) {
    RECT rect = rc;

    // Nền đồng bộ với sidebar
    HBRUSH bgBrush = CreateSolidBrush(RGB(12, 18, 32));
    FillRect(hdc, &rect, bgBrush);
    DeleteObject(bgBrush);

    // Tính hình pill bo tròn
    int radius = (rect.bottom - rect.top) / 2;

    // Màu base
    COLORREF borderColor = isNewSessionButtonHover_ || isPressed
        ? RGB(120, 230, 255)
        : RGB(60, 110, 150);
    COLORREF fillColor = isPressed
        ? RGB(20, 34, 64)
        : RGB(16, 28, 56);

    HPEN pen = CreatePen(PS_SOLID, 1, borderColor);
    HBRUSH brush = CreateSolidBrush(fillColor);
    HGDIOBJ oldPen = SelectObject(hdc, pen);
    HGDIOBJ oldBrush = SelectObject(hdc, brush);

    RoundRect(hdc, rect.left, rect.top, rect.right, rect.bottom, radius, radius);

    SelectObject(hdc, oldPen);
    SelectObject(hdc, oldBrush);
    DeleteObject(pen);
    DeleteObject(brush);

    // Vẽ text "Chat Mới"
    const wchar_t* label = L"Chat Mới";
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(232, 236, 255));
    HFONT oldFont2 = (HFONT)SelectObject(hdc, hInputFont_);

    RECT textRect = rect;
    DrawTextW(hdc, label, -1, &textRect,
              DT_CENTER | DT_VCENTER | DT_SINGLELINE);

    SelectObject(hdc, oldFont2);
}

void MainWindow::DrawStatusBadge(HDC hdc, const RECT& headerRect, RECT* outBadgeRect, int titleEndX) {
    const wchar_t* statusText;
    COLORREF bgColor, borderColor, textColor;
    
    switch (healthStatus_) {
        case HealthStatus::Online:
            statusText = L"Online";
            bgColor = RGB(50, 140, 80);      // Xanh
            borderColor = RGB(90, 200, 120);
            textColor = RGB(230, 255, 240);
            break;
        case HealthStatus::Checking:
            statusText = L"Đang kết nối…";
            bgColor = RGB(180, 150, 60);     // Vàng/Xám (amber)
            borderColor = RGB(220, 180, 80);
            textColor = RGB(255, 250, 230);
            break;
        case HealthStatus::Offline:
        default:
            statusText = L"Offline";
            bgColor = RGB(180, 60, 60);      // Đỏ
            borderColor = RGB(220, 100, 100);
            textColor = RGB(255, 240, 240);
            break;
    }
    
    SIZE statusSize = {0,0};
    GetTextExtentPoint32W(hdc, statusText, lstrlenW(statusText), &statusSize);
    int badgePaddingX = 10;
    int badgePaddingY = 4;
    int badgeWidth = statusSize.cx + badgePaddingX * 2;
    int badgeHeight = statusSize.cy + badgePaddingY * 2;
    // Đặt badge sau text "Tiểu Bối" với khoảng cách 12px, hoặc fallback về vị trí cũ nếu titleEndX = 0
    int badgeX = (titleEndX > 0) ? (titleEndX + 12) : (16 + 60 + 12);
    int badgeY = (headerRect.bottom - headerRect.top - badgeHeight) / 2;
    RECT badgeRect = {badgeX, badgeY, badgeX + badgeWidth, badgeY + badgeHeight};
    
    if (outBadgeRect) {
        *outBadgeRect = badgeRect;
    }
    
    HBRUSH badgeBrush = CreateSolidBrush(bgColor);
    HPEN badgePen = CreatePen(PS_SOLID, 1, borderColor);
    HGDIOBJ oldBrush = SelectObject(hdc, badgeBrush);
    HGDIOBJ oldPen = SelectObject(hdc, badgePen);
    RoundRect(hdc, badgeRect.left, badgeRect.top, badgeRect.right, badgeRect.bottom, 12, 12);
    SetTextColor(hdc, textColor);
    RECT badgeTextRect = badgeRect;
    DrawTextW(hdc, statusText, -1, &badgeTextRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
    DeleteObject(badgeBrush);
    DeleteObject(badgePen);
}

void MainWindow::DrawSettingsIcon(HDC hdc) {
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    int headerH = theme_.headerHeight;
    
    // Position settings icon ở góc phải header
    int iconSize = 24;
    int iconMarginRight = 16;
    int iconX = clientRect.right - iconSize - iconMarginRight;
    int iconY = (headerH - iconSize) / 2;
    
    settingsIconRect_ = {iconX, iconY, iconX + iconSize, iconY + iconSize};
    
    // Draw gear icon (⚙) as text or simple shape
    SetBkMode(hdc, TRANSPARENT);
    COLORREF iconColor = isSettingsIconHover_ ? RGB(120, 230, 255) : RGB(154, 163, 195);
    SetTextColor(hdc, iconColor);
    
    // Use a larger font for the gear icon
    HFONT iconFont = CreateFontW(-20, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    HFONT oldFont = (HFONT)SelectObject(hdc, iconFont);
    
    RECT iconTextRect = settingsIconRect_;
    DrawTextW(hdc, L"⚙", -1, &iconTextRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    
    SelectObject(hdc, oldFont);
    DeleteObject(iconFont);
}