#include <windows.h>
#include <windowsx.h>
#include <dwmapi.h>
#include "MainWindow.h"
#include "MainWindowHelpers.h"
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

    // Fill background with solid black (darker look)
    HBRUSH bgBrush = CreateSolidBrush(theme_.colorBackground);
    FillRect(hdcMem, &clientRect, bgBrush);
    DeleteObject(bgBrush);

    // Overlay subtle grid
    HPEN gridPen = CreatePen(PS_SOLID, 1, theme_.colorGrid);
    oldPen = (HPEN)SelectObject(hdcMem, gridPen);
    for (int x = 60; x < clientRect.right; x += 80) {
        MoveToEx(hdcMem, x, 0, NULL);
        LineTo(hdcMem, x, clientRect.bottom);
    }
    for (int y = 60; y < clientRect.bottom; y += 80) {
        MoveToEx(hdcMem, 0, y, NULL);
        LineTo(hdcMem, clientRect.right, y);
    }
    SelectObject(hdcMem, oldPen);
    DeleteObject(gridPen);

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
    SelectObject(hdcMem, hInputFont_);
    
    // Tính chiều rộng thực tế của text "Tiểu Bối" để đặt badge đúng vị trí
    const wchar_t* titleText = uiStrings_.appTitle.c_str();
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
    std::wstring sessionLabel = uiStrings_.sessionLabel;
    std::wstring sessionIdW = Utf8ToWideLocal(sessionId_);
    if (sessionIdW.length() > 16) {
        sessionIdW = L"..." + sessionIdW.substr(sessionIdW.length() - 13);
    }
    sessionLabel += sessionIdW;
    
    std::wstring modelText = uiStrings_.modelLabel + (modelName_.empty() ? L"(chưa có)" : modelName_);
    
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

    // Draw chat messages if any exist
    if (!chatViewState_.messages.empty()) {
        DrawChatMessages(hdcMem);
    } else {
        // Draw hero title
        SetBkMode(hdcMem, TRANSPARENT);
        SetTextColor(hdcMem, RGB(232, 236, 255));
        SelectObject(hdcMem, hTitleFont_);
        
        const wchar_t* titleText2 = uiStrings_.heroTitle.c_str();

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

        const wchar_t* subtitle = uiStrings_.heroSubtitle.c_str();
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

// Settings dialog structure
struct SettingsDlgData {
    MainWindow* pMainWindow;
    HWND hUrlEdit;
    HWND hKeyEdit;
    bool isOkHover;
    bool isCancelHover;
    RECT okRect;
    RECT cancelRect;
    bool shouldClose;
};

LRESULT CALLBACK MainWindow::SettingsDlgProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    SettingsDlgData* pData = (SettingsDlgData*)GetWindowLongPtr(hwnd, GWLP_USERDATA);
    
    switch (uMsg) {
        case WM_CREATE: {
            CREATESTRUCT* pCreate = (CREATESTRUCT*)lParam;
            pData = (SettingsDlgData*)pCreate->lpCreateParams;
            SetWindowLongPtr(hwnd, GWLP_USERDATA, (LONG_PTR)pData);
            
            // Create edit controls with dark theme (no border, we'll draw custom border)
            // Positioned with clear spacing from labels (12px gap between label bottom and input top)
            // Label "API URL" ends at y=66, input starts at y=78 (12px gap)
            // Label "API Key" ends at y=126, input starts at y=138 (12px gap)
            HINSTANCE hInst = GetModuleHandle(NULL);
            pData->hUrlEdit = CreateWindowExW(
                0, L"EDIT", L"",
                WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_LEFT,
                22, 78, 456, 28, hwnd, (HMENU)1001, hInst, NULL);
            
            pData->hKeyEdit = CreateWindowExW(
                0, L"EDIT", L"",
                WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_LEFT | ES_PASSWORD,
                22, 138, 456, 28, hwnd, (HMENU)1002, hInst, NULL);
            
            // Set fonts
            HFONT hDlgFont = CreateFontW(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
            SendMessageW(pData->hUrlEdit, WM_SETFONT, (WPARAM)hDlgFont, TRUE);
            SendMessageW(pData->hKeyEdit, WM_SETFONT, (WPARAM)hDlgFont, TRUE);
            
            // Set current values
            if (pData->pMainWindow) {
                std::string baseUrl = pData->pMainWindow->httpClient_.getBaseUrl();
                std::string apiKey = pData->pMainWindow->httpClient_.getApiKey();
                SetWindowTextA(pData->hUrlEdit, baseUrl.c_str());
                SetWindowTextA(pData->hKeyEdit, apiKey.c_str());
            }
            
            // Button rects - positioned to fit within dialog
            // Input fields end around y=166 (138 + 28), buttons start at y=184 (16px gap)
            pData->okRect = {320, 184, 400, 216};
            pData->cancelRect = {410, 184, 490, 216};
            pData->isOkHover = false;
            pData->isCancelHover = false;
            pData->shouldClose = false;
            
            return 0;
        }
        
        case WM_PAINT: {
            PAINTSTRUCT ps;
            HDC hdc = BeginPaint(hwnd, &ps);
            
            RECT clientRect;
            GetClientRect(hwnd, &clientRect);
            
            // Double buffering
            HDC hdcMem = CreateCompatibleDC(hdc);
            HBITMAP hbmMem = CreateCompatibleBitmap(hdc, clientRect.right, clientRect.bottom);
            HBITMAP hbmOld = (HBITMAP)SelectObject(hdcMem, hbmMem);
            
            // Fill dark background
            HBRUSH bgBrush = CreateSolidBrush(RGB(16, 22, 40));
            FillRect(hdcMem, &clientRect, bgBrush);
            DeleteObject(bgBrush);
            
            // Draw header with cyan line
            RECT headerRect = {0, 0, clientRect.right, 40};
            HBRUSH headerBrush = CreateSolidBrush(RGB(16, 22, 40));
            FillRect(hdcMem, &headerRect, headerBrush);
            DeleteObject(headerBrush);
            
            // Draw title first (before the line)
            SetBkMode(hdcMem, TRANSPARENT);
            SetTextColor(hdcMem, RGB(232, 236, 255));
            HFONT hTitleFont = CreateFontW(-20, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
            HFONT hOldFont = (HFONT)SelectObject(hdcMem, hTitleFont);
            RECT titleRect = {20, 0, clientRect.right, 40};
            DrawTextW(hdcMem, L"Cài đặt", -1, &titleRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
            SelectObject(hdcMem, hOldFont);
            DeleteObject(hTitleFont);
            
            // Draw cyan line at the bottom of header (after title)
            HPEN headerPen = CreatePen(PS_SOLID, 1, RGB(74, 215, 255));
            HGDIOBJ oldPen = SelectObject(hdcMem, headerPen);
            MoveToEx(hdcMem, 0, headerRect.bottom - 1, NULL);
            LineTo(hdcMem, clientRect.right, headerRect.bottom - 1);
            SelectObject(hdcMem, oldPen);
            DeleteObject(headerPen);
            
            // Draw labels (below the header line)
            HFONT hLabelFont = CreateFontW(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
            hOldFont = (HFONT)SelectObject(hdcMem, hLabelFont);
            SetTextColor(hdcMem, RGB(200, 210, 230));
            
            // Labels với khoảng cách rõ ràng từ input fields (12px gap)
            // Tăng chiều cao để chứa đầy đủ các ký tự có descenders (y, g, p, q)
            RECT labelRect1 = {20, 48, 200, 66};
            DrawTextW(hdcMem, L"API URL:", -1, &labelRect1, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
            
            RECT labelRect2 = {20, 108, 200, 126};
            DrawTextW(hdcMem, L"API Key:", -1, &labelRect2, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
            
            SelectObject(hdcMem, hOldFont);
            DeleteObject(hLabelFont);
            
            // Draw input field borders (similar to main input field)
            if (pData && pData->hUrlEdit && pData->hKeyEdit) {
                RECT urlRect, keyRect;
                GetWindowRect(pData->hUrlEdit, &urlRect);
                GetWindowRect(pData->hKeyEdit, &keyRect);
                POINT pt1 = {urlRect.left, urlRect.top};
                POINT pt2 = {urlRect.right, urlRect.bottom};
                POINT pt3 = {keyRect.left, keyRect.top};
                POINT pt4 = {keyRect.right, keyRect.bottom};
                ScreenToClient(hwnd, &pt1);
                ScreenToClient(hwnd, &pt2);
                ScreenToClient(hwnd, &pt3);
                ScreenToClient(hwnd, &pt4);
                
                urlRect.left = pt1.x - 2;
                urlRect.top = pt1.y - 2;
                urlRect.right = pt2.x + 2;
                urlRect.bottom = pt2.y + 2;
                
                keyRect.left = pt3.x - 2;
                keyRect.top = pt3.y - 2;
                keyRect.right = pt4.x + 2;
                keyRect.bottom = pt4.y + 2;
                
                // Outer border (cyan)
                HPEN borderPen = CreatePen(PS_SOLID, 2, RGB(74, 215, 255));
                HBRUSH borderBrush = CreateSolidBrush(RGB(25, 36, 64));
                HGDIOBJ oldBorderPen = SelectObject(hdcMem, borderPen);
                HGDIOBJ oldBorderBrush = SelectObject(hdcMem, borderBrush);
                RoundRect(hdcMem, urlRect.left, urlRect.top, urlRect.right, urlRect.bottom, 8, 8);
                RoundRect(hdcMem, keyRect.left, keyRect.top, keyRect.right, keyRect.bottom, 8, 8);
                SelectObject(hdcMem, oldBorderBrush);
                SelectObject(hdcMem, oldBorderPen);
                DeleteObject(borderBrush);
                DeleteObject(borderPen);
            }
            
            // Draw buttons
            int radius = 8;
            COLORREF okBg = pData->isOkHover ? RGB(74, 215, 255) : RGB(25, 36, 64);
            COLORREF okBorder = RGB(74, 215, 255);
            COLORREF okText = pData->isOkHover ? RGB(0, 0, 0) : RGB(232, 236, 255);
            
            HBRUSH okBrush = CreateSolidBrush(okBg);
            HPEN okPen = CreatePen(PS_SOLID, 1, okBorder);
            HGDIOBJ oldBrush = SelectObject(hdcMem, okBrush);
            oldPen = SelectObject(hdcMem, okPen);
            RoundRect(hdcMem, pData->okRect.left, pData->okRect.top, pData->okRect.right, pData->okRect.bottom, radius, radius);
            SelectObject(hdcMem, oldBrush);
            SelectObject(hdcMem, oldPen);
            DeleteObject(okBrush);
            DeleteObject(okPen);
            
            SetTextColor(hdcMem, okText);
            hOldFont = (HFONT)SelectObject(hdcMem, hLabelFont);
            DrawTextW(hdcMem, L"OK", -1, &pData->okRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            
            COLORREF cancelBg = pData->isCancelHover ? RGB(40, 50, 70) : RGB(25, 36, 64);
            COLORREF cancelBorder = RGB(60, 90, 130);
            COLORREF cancelText = RGB(200, 210, 230);
            
            HBRUSH cancelBrush = CreateSolidBrush(cancelBg);
            HPEN cancelPen = CreatePen(PS_SOLID, 1, cancelBorder);
            oldBrush = SelectObject(hdcMem, cancelBrush);
            oldPen = SelectObject(hdcMem, cancelPen);
            RoundRect(hdcMem, pData->cancelRect.left, pData->cancelRect.top, pData->cancelRect.right, pData->cancelRect.bottom, radius, radius);
            SelectObject(hdcMem, oldBrush);
            SelectObject(hdcMem, oldPen);
            DeleteObject(cancelBrush);
            DeleteObject(cancelPen);
            
            SetTextColor(hdcMem, cancelText);
            DrawTextW(hdcMem, L"Hủy", -1, &pData->cancelRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            SelectObject(hdcMem, hOldFont);
            
            // Blit to screen
            BitBlt(hdc, 0, 0, clientRect.right, clientRect.bottom, hdcMem, 0, 0, SRCCOPY);
            
            SelectObject(hdcMem, hbmOld);
            DeleteObject(hbmMem);
            DeleteDC(hdcMem);
            
            EndPaint(hwnd, &ps);
            return 0;
        }
        
        case WM_CTLCOLOREDIT: {
            HDC hdc = (HDC)wParam;
            SetBkMode(hdc, TRANSPARENT);
            SetBkColor(hdc, RGB(18, 24, 42));
            SetTextColor(hdc, RGB(255, 255, 255));
            static HBRUSH hEditBrush = NULL;
            if (!hEditBrush) {
                hEditBrush = CreateSolidBrush(RGB(18, 24, 42));
            }
            return (LRESULT)hEditBrush;
        }
        
        case WM_CTLCOLORSTATIC: {
            HDC hdc = (HDC)wParam;
            SetBkMode(hdc, TRANSPARENT);
            SetTextColor(hdc, RGB(200, 210, 230));
            return (LRESULT)GetStockObject(NULL_BRUSH);
        }
        
        case WM_MOUSEMOVE: {
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            bool newOkHover = PtInRect(&pData->okRect, pt);
            bool newCancelHover = PtInRect(&pData->cancelRect, pt);
            
            if (newOkHover != pData->isOkHover || newCancelHover != pData->isCancelHover) {
                pData->isOkHover = newOkHover;
                pData->isCancelHover = newCancelHover;
                InvalidateRect(hwnd, NULL, FALSE);
            }
            return 0;
        }
        
        case WM_LBUTTONDOWN: {
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            if (PtInRect(&pData->okRect, pt)) {
                // Get values
                char urlBuffer[512] = {0};
                char keyBuffer[512] = {0};
                GetWindowTextA(pData->hUrlEdit, urlBuffer, sizeof(urlBuffer));
                GetWindowTextA(pData->hKeyEdit, keyBuffer, sizeof(keyBuffer));
                
                if (pData->pMainWindow) {
                    pData->pMainWindow->httpClient_.setBaseUrl(urlBuffer);
                    pData->pMainWindow->httpClient_.setApiKey(keyBuffer);
                    pData->pMainWindow->SaveSettingsToFile(urlBuffer, keyBuffer);
                    pData->pMainWindow->healthStatus_ = HealthStatus::Checking;
                    pData->pMainWindow->CheckHealthStatus();
                }
                pData->shouldClose = true;
                DestroyWindow(hwnd);
                return 0;
            } else if (PtInRect(&pData->cancelRect, pt)) {
                pData->shouldClose = true;
                DestroyWindow(hwnd);
                return 0;
            }
            break;
        }
        
        case WM_LBUTTONUP: {
            // Handle button release for better UX
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            if (PtInRect(&pData->okRect, pt) || PtInRect(&pData->cancelRect, pt)) {
                InvalidateRect(hwnd, NULL, FALSE);
            }
            break;
        }
        
        case WM_CLOSE:
            pData->shouldClose = true;
            DestroyWindow(hwnd);
            return 0;
            
        case WM_ERASEBKGND:
            return TRUE;
    }
    
    return DefWindowProcW(hwnd, uMsg, wParam, lParam);
}

void MainWindow::ShowSettingsDialog() {
    // Register dialog class if not already registered
    static bool classRegistered = false;
    if (!classRegistered) {
        WNDCLASSW wc = {};
        wc.lpfnWndProc = SettingsDlgProc;
        wc.hInstance = hInstance_;
        wc.lpszClassName = L"SenAISettingsDialog";
        wc.hbrBackground = NULL;
        wc.hCursor = LoadCursor(NULL, IDC_ARROW);
        wc.style = CS_HREDRAW | CS_VREDRAW;
        RegisterClassW(&wc);
        classRegistered = true;
    }
    
    // Create dialog data
    SettingsDlgData dlgData = {};
    dlgData.pMainWindow = this;
    dlgData.hUrlEdit = NULL;
    dlgData.hKeyEdit = NULL;
    dlgData.isOkHover = false;
    dlgData.isCancelHover = false;
    
    // Create dialog window
    HINSTANCE hInst = hInstance_ ? hInstance_ : GetModuleHandle(NULL);
    HWND hDlg = CreateWindowExW(
        WS_EX_DLGMODALFRAME | WS_EX_TOPMOST,
        L"SenAISettingsDialog",
        L"Cài đặt",
        WS_POPUP | WS_CAPTION | WS_SYSMENU,
        CW_USEDEFAULT, CW_USEDEFAULT,
        520, 255,
        hwnd_,
        NULL,
        hInst,
        &dlgData
    );
    
    if (!hDlg) return;
    
    // Center dialog
    RECT dlgRect, parentRect;
    GetWindowRect(hDlg, &dlgRect);
    GetWindowRect(hwnd_, &parentRect);
    int x = parentRect.left + (parentRect.right - parentRect.left - (dlgRect.right - dlgRect.left)) / 2;
    int y = parentRect.top + (parentRect.bottom - parentRect.top - (dlgRect.bottom - dlgRect.top)) / 2;
    SetWindowPos(hDlg, NULL, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER);
    
    // Set dark mode
    BOOL darkMode = TRUE;
    DwmSetWindowAttribute(hDlg, 20, &darkMode, sizeof(darkMode));
    
    ShowWindow(hDlg, SW_SHOW);
    UpdateWindow(hDlg);
    
    // Modal message loop
    MSG msg;
    while (IsWindow(hDlg) && GetMessageW(&msg, NULL, 0, 0)) {
        if (!IsDialogMessage(hDlg, &msg)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
}