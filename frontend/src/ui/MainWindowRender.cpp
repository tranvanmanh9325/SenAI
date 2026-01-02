#include <windows.h>
#include <windowsx.h>
#include <dwmapi.h>
#include "MainWindow.h"
#include "MainWindowHelpers.h"
#include "UiConstants.h"
#include <string>

// Rendering functions split from MainWindowUI.cpp

namespace {
    // Local UTF-8 -> UTF-16 converter for rendering sessionId_
    std::wstring Utf8ToWideLocal(const std::string& str) {
        return Utf8ToWide(str);
    }
}

void MainWindow::OnPaint() {
    PAINTSTRUCT ps;
    HDC hdcWindow = BeginPaint(hwnd_, &ps);

    // Double-buffered painting to avoid flicker
    RECT clientRect;
    GetClientRect(hwnd_, &clientRect);
    int width = clientRect.right - clientRect.left;
    int height = clientRect.bottom - clientRect.top;

    HDC hdcMem = CreateCompatibleDC(hdcWindow);
    HBITMAP hbmMem = CreateCompatibleBitmap(hdcWindow, width, height);
    HBITMAP hbmOld = (HBITMAP)SelectObject(hdcMem, hbmMem);

    HBRUSH oldBrush = nullptr;
    HPEN oldPen = nullptr;

    // Fill background with solid black (darker look) - use cached brush
    FillRect(hdcMem, &clientRect, hDarkBrush_->Get());

    // Overlay subtle grid - use resource manager
    using namespace UiConstants;
    auto gridPen = gdiManager_->CreatePen(PS_SOLID, 1, theme_.colorGrid);
    oldPen = (HPEN)SelectObject(hdcMem, gridPen->Get());
    for (int x = Grid::START_X; x < clientRect.right; x += Grid::SPACING_X) {
        MoveToEx(hdcMem, x, 0, NULL);
        LineTo(hdcMem, x, clientRect.bottom);
    }
    for (int y = Grid::START_Y; y < clientRect.bottom; y += Grid::SPACING_Y) {
        MoveToEx(hdcMem, 0, y, NULL);
        LineTo(hdcMem, clientRect.right, y);
    }
    SelectObject(hdcMem, oldPen);
    // gridPen automatically cleaned up by smart pointer

    // Glowing orb (soft circle)
    int orbSize = 260;
    int orbX = clientRect.right - orbSize - 80;
    int orbY = 80;
    BLENDFUNCTION bf = {AC_SRC_OVER, 0, 30, 0};
    HDC orbDC = CreateCompatibleDC(hdcMem);
    HBITMAP orbBmp = CreateCompatibleBitmap(hdcMem, orbSize, orbSize);
    HBITMAP oldBmp = (HBITMAP)SelectObject(orbDC, orbBmp);
    RECT orbRect = {0, 0, orbSize, orbSize};
    HBRUSH orbBg = CreateSolidBrush(RGB(0,0,0));
    FillRect(orbDC, &orbRect, orbBg);
    DeleteObject(orbBg);
    HBRUSH orbFill = CreateSolidBrush(RGB(40, 120, 255));
    SelectObject(orbDC, orbFill);
    Ellipse(orbDC, 0, 0, orbSize, orbSize);
    AlphaBlend(hdcMem, orbX, orbY, orbSize, orbSize, orbDC, 0, 0, orbSize, orbSize, bf);
    SelectObject(orbDC, oldBmp);
    DeleteObject(orbFill);
    DeleteObject(orbBmp);
    DeleteDC(orbDC);
    
    // Header bar
    int headerH = theme_.headerHeight;
    RECT headerRect = {clientRect.left, clientRect.top, clientRect.right, clientRect.top + headerH};
    HBRUSH headerBrush = CreateSolidBrush(theme_.colorHeaderBg);
    FillRect(hdcMem, &headerRect, headerBrush);
    DeleteObject(headerBrush);

    // Bottom border for header
    HPEN headerPen = CreatePen(PS_SOLID, 1, theme_.colorHeaderLine);
    oldPen = (HPEN)SelectObject(hdcMem, headerPen);
    MoveToEx(hdcMem, headerRect.left, headerRect.bottom - 1, NULL);
    LineTo(hdcMem, headerRect.right, headerRect.bottom - 1);
    SelectObject(hdcMem, oldPen);
    DeleteObject(headerPen);

    // Header text
    SetBkMode(hdcMem, TRANSPARENT);
    SetTextColor(hdcMem, theme_.colorHeaderText);
    SelectObject(hdcMem, hInputFont_->Get());
    
    // Tính chiều rộng thực tế của text "Tiểu Bối" để đặt badge đúng vị trí
    const wchar_t* titleText = UiStrings::Get(IDS_APP_TITLE).c_str();
    SIZE titleSize = {0, 0};
    GetTextExtentPoint32W(hdcMem, titleText, lstrlenW(titleText), &titleSize);
    int titleWidth = titleSize.cx;
    
    RECT titleRect = {16, 0, 16 + titleWidth, headerH};
    DrawTextW(hdcMem, titleText, -1, &titleRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);

    // Status badge (drawn by DrawStatusBadge) - đặt sau text với khoảng cách hợp lý
    RECT badgeRect;
    DrawStatusBadge(hdcMem, headerRect, &badgeRect, 16 + titleWidth + 12);
    
    // Settings icon (⚙)
    DrawSettingsIcon(hdcMem);
    
    // Session ID text đặt giữa badge và icon settings + model name
    std::wstring sessionLabel = UiStrings::Get(IDS_SESSION_LABEL);
    std::wstring sessionIdW = Utf8ToWideLocal(sessionId_);
    if (sessionIdW.length() > 16) {
        sessionIdW = L"..." + sessionIdW.substr(sessionIdW.length() - 13);
    }
    sessionLabel += sessionIdW;
    
    std::wstring modelText = UiStrings::Get(IDS_MODEL_LABEL) + (modelName_.empty() ? UiStrings::Get(IDS_MODEL_NOT_AVAILABLE) : modelName_);
    
    SetTextColor(hdcMem, RGB(154, 163, 195));

    int sessionRight = settingsIconRect_.left - 12;
    if (sessionRight < badgeRect.right + 40) {
        sessionRight = badgeRect.right + 40;
    }
    RECT sessionRect = { badgeRect.right + 16, 0, sessionRight, headerH / 2 };
    DrawTextW(hdcMem, sessionLabel.c_str(), -1, &sessionRect, DT_RIGHT | DT_VCENTER | DT_SINGLELINE);
    
    RECT modelRect = { badgeRect.right + 16, headerH / 2, sessionRight, headerH };
    SetTextColor(hdcMem, RGB(120, 190, 240));
    DrawTextW(hdcMem, modelText.c_str(), -1, &modelRect, DT_RIGHT | DT_VCENTER | DT_SINGLELINE);

    // Draw sidebar if visible
    if (sidebarVisible_) {
        DrawSidebar(hdcMem);
    }
    
    // Draw search bar if visible
    if (searchVisible_) {
        DrawSearchBar(hdcMem);
    }

    // Draw chat messages if any exist
    if (!chatViewState_.messages.empty()) {
        DrawChatMessages(hdcMem);
    } else {
        // Draw hero title
        SetBkMode(hdcMem, TRANSPARENT);
        SetTextColor(hdcMem, RGB(232, 236, 255));
        SelectObject(hdcMem, hTitleFont_->Get());
        
        const wchar_t* titleText2 = UiStrings::Get(IDS_HERO_TITLE).c_str();

        // Căn giữa theo vùng main content (bên phải sidebar nếu sidebarVisible_)
        int contentLeft = sidebarVisible_ ? sidebarWidth_ : 0;
        int contentWidth = windowWidth_ - contentLeft;
        if (contentWidth < 0) contentWidth = 0;

        // Cho chiều cao rộng hơn để tránh bị cắt phần trên/dưới của font lớn
        RECT titleRect2 = {
            contentLeft,
            windowHeight_ / 2 - 170,
            contentLeft + contentWidth,
            windowHeight_ / 2 - 90
        };
        // Soft shadow
        SetTextColor(hdcMem, RGB(0, 10, 30));
        OffsetRect(&titleRect2, 1, 2);
        DrawTextW(hdcMem, titleText2, -1, &titleRect2, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        OffsetRect(&titleRect2, -1, -2);
        SetTextColor(hdcMem, RGB(232, 236, 255));
        DrawTextW(hdcMem, titleText2, -1, &titleRect2, DT_CENTER | DT_VCENTER | DT_SINGLELINE);

        const wchar_t* subtitle = UiStrings::Get(IDS_HERO_SUBTITLE).c_str();
        // Tăng thêm khoảng trống phía dưới để không bị cắt mép dưới
        RECT subRect = {
            contentLeft,
            windowHeight_ / 2 - 90,
            contentLeft + contentWidth,
            windowHeight_ / 2 + 10
        };
        SetTextColor(hdcMem, RGB(154, 163, 195));
        DrawTextW(hdcMem, subtitle, -1, &subRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    }
    
    // Draw input field
    DrawInputField(hdcMem);

    // Blit the composed frame in one go
    BitBlt(hdcWindow, 0, 0, width, height, hdcMem, 0, 0, SRCCOPY);

    // Cleanup
    SelectObject(hdcMem, hbmOld);
    DeleteObject(hbmMem);
    DeleteDC(hdcMem);

    EndPaint(hwnd_, &ps);
}

BOOL MainWindow::OnEraseBkgnd(HDC hdc) {
    // We paint the full background in OnPaint with double buffering,
    // so return TRUE here to prevent Windows from erasing the background
    // This eliminates flicker completely
    UNREFERENCED_PARAMETER(hdc);
    return TRUE;
}

void MainWindow::HandleSettingsIconClick() {
    ShowSettingsDialog();
}