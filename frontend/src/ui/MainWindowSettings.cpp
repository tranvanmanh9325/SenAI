#include <windows.h>
#include <windowsx.h>
#include <dwmapi.h>
#include "MainWindow.h"
#include "MainWindowHelpers.h"
#include <string>

// Settings dialog implementation

// Settings dialog structure
struct SettingsDlgData {
    MainWindow* pMainWindow;
    HWND hUrlEdit;
    HWND hKeyEdit;
    bool isCtrlEnterChecked;  // Custom checkbox state
    bool isCheckboxHover;     // Checkbox hover state
    RECT checkboxRect;         // Checkbox clickable area
    bool isOkHover;
    bool isCancelHover;
    bool isExportHover;
    RECT okRect;
    RECT cancelRect;
    RECT exportRect;
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
                // Set checkbox state (custom checkbox, no Windows control)
                pData->isCtrlEnterChecked = pData->pMainWindow->enableCtrlEnterToSend_;
            }
            
            // Initialize checkbox rect (custom drawn, no Windows control)
            pData->checkboxRect = {22, 178, 478, 202};  // x, y, right, bottom
            pData->isCheckboxHover = false;
            
            // Button rects - positioned to fit within dialog (moved down for checkbox)
            // Checkbox ends around y=202 (178 + 24), buttons start at y=220 (18px gap)
            pData->exportRect = {20, 220, 120, 252};
            pData->okRect = {320, 220, 400, 252};
            pData->cancelRect = {410, 220, 490, 252};
            pData->isOkHover = false;
            pData->isCancelHover = false;
            pData->isExportHover = false;
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
            DrawTextW(hdcMem, UiStrings::Get(IDS_SETTINGS_TITLE).c_str(), -1, &titleRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
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
            DrawTextW(hdcMem, UiStrings::Get(IDS_API_URL_LABEL).c_str(), -1, &labelRect1, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
            
            RECT labelRect2 = {20, 108, 200, 126};
            DrawTextW(hdcMem, UiStrings::Get(IDS_API_KEY_LABEL).c_str(), -1, &labelRect2, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
            
            // Draw custom checkbox (Ctrl+Enter to send)
            if (pData) {
                int checkboxSize = 18;
                int checkboxX = pData->checkboxRect.left;
                int checkboxY = pData->checkboxRect.top + (pData->checkboxRect.bottom - pData->checkboxRect.top - checkboxSize) / 2;
                RECT checkboxBox = {checkboxX, checkboxY, checkboxX + checkboxSize, checkboxY + checkboxSize};
                
                // Checkbox colors
                COLORREF checkboxBg = RGB(18, 24, 42);
                COLORREF checkboxBorder = RGB(60, 90, 130);
                COLORREF checkboxBorderHover = RGB(100, 150, 200);
                COLORREF checkboxChecked = RGB(74, 215, 255);
                
                if (pData->isCheckboxHover) {
                    checkboxBorder = checkboxBorderHover;
                }
                
                if (pData->isCtrlEnterChecked) {
                    checkboxBg = checkboxChecked;
                    checkboxBorder = checkboxChecked;
                }
                
                // Draw checkbox box with rounded corners
                int radius = 4;
                HBRUSH checkboxBrush = CreateSolidBrush(checkboxBg);
                HPEN checkboxPen = CreatePen(PS_SOLID, 1, checkboxBorder);
                HGDIOBJ oldCheckboxBrush = SelectObject(hdcMem, checkboxBrush);
                HGDIOBJ oldCheckboxPen = SelectObject(hdcMem, checkboxPen);
                RoundRect(hdcMem, checkboxBox.left, checkboxBox.top, checkboxBox.right, checkboxBox.bottom, radius, radius);
                
                // Draw checkmark if checked
                if (pData->isCtrlEnterChecked) {
                    // Draw checkmark with white color for better contrast on cyan background
                    HPEN checkmarkPen = CreatePen(PS_SOLID, 2, RGB(255, 255, 255));
                    HGDIOBJ oldCheckmarkPen = SelectObject(hdcMem, checkmarkPen);
                    
                    // Draw checkmark (V shape) - centered and properly sized
                    int checkX = checkboxBox.left + 4;
                    int checkY = checkboxBox.top + checkboxSize / 2;
                    int checkSize = 8;
                    
                    // Left part of checkmark
                    MoveToEx(hdcMem, checkX, checkY, NULL);
                    LineTo(hdcMem, checkX + 3, checkY + 3);
                    
                    // Right part of checkmark
                    MoveToEx(hdcMem, checkX + 3, checkY + 3, NULL);
                    LineTo(hdcMem, checkX + checkSize, checkY - 3);
                    
                    SelectObject(hdcMem, oldCheckmarkPen);
                    DeleteObject(checkmarkPen);
                }
                
                SelectObject(hdcMem, oldCheckboxBrush);
                SelectObject(hdcMem, oldCheckboxPen);
                DeleteObject(checkboxBrush);
                DeleteObject(checkboxPen);
                
                // Draw checkbox label text
                SetTextColor(hdcMem, RGB(232, 236, 255));
                RECT labelRect = {checkboxX + checkboxSize + 10, pData->checkboxRect.top, 
                                  pData->checkboxRect.right, pData->checkboxRect.bottom};
                DrawTextW(hdcMem, L"Ctrl+Enter để gửi tin nhắn", -1, &labelRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
            }
            
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
            DrawTextW(hdcMem, UiStrings::Get(IDS_OK_BUTTON).c_str(), -1, &pData->okRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            
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
            DrawTextW(hdcMem, UiStrings::Get(IDS_CANCEL_BUTTON).c_str(), -1, &pData->cancelRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            
            // Draw Export button
            COLORREF exportBg = pData->isExportHover ? RGB(74, 215, 255) : RGB(25, 36, 64);
            COLORREF exportBorder = RGB(74, 215, 255);
            COLORREF exportText = pData->isExportHover ? RGB(0, 0, 0) : RGB(232, 236, 255);
            
            HBRUSH exportBrush = CreateSolidBrush(exportBg);
            HPEN exportPen = CreatePen(PS_SOLID, 1, exportBorder);
            oldBrush = SelectObject(hdcMem, exportBrush);
            oldPen = SelectObject(hdcMem, exportPen);
            RoundRect(hdcMem, pData->exportRect.left, pData->exportRect.top, pData->exportRect.right, pData->exportRect.bottom, radius, radius);
            SelectObject(hdcMem, oldBrush);
            SelectObject(hdcMem, oldPen);
            DeleteObject(exportBrush);
            DeleteObject(exportPen);
            
            SetTextColor(hdcMem, exportText);
            DrawTextW(hdcMem, L"Xuất", -1, &pData->exportRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            
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
        
        case WM_CTLCOLORBTN: {
            // No custom checkbox control anymore, return default
            return DefWindowProcW(hwnd, uMsg, wParam, lParam);
        }
        
        case WM_MOUSEMOVE: {
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            bool newOkHover = PtInRect(&pData->okRect, pt);
            bool newCancelHover = PtInRect(&pData->cancelRect, pt);
            bool newExportHover = PtInRect(&pData->exportRect, pt);
            bool newCheckboxHover = PtInRect(&pData->checkboxRect, pt);
            
            if (newOkHover != pData->isOkHover || 
                newCancelHover != pData->isCancelHover ||
                newExportHover != pData->isExportHover ||
                newCheckboxHover != pData->isCheckboxHover) {
                pData->isOkHover = newOkHover;
                pData->isCancelHover = newCancelHover;
                pData->isExportHover = newExportHover;
                pData->isCheckboxHover = newCheckboxHover;
                InvalidateRect(hwnd, NULL, FALSE);
            }
            return 0;
        }
        
        case WM_LBUTTONDOWN: {
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            
            // Handle checkbox click
            if (PtInRect(&pData->checkboxRect, pt)) {
                pData->isCtrlEnterChecked = !pData->isCtrlEnterChecked;
                InvalidateRect(hwnd, NULL, FALSE);
                return 0;
            }
            
            // Handle Export button click
            if (PtInRect(&pData->exportRect, pt)) {
                if (pData->pMainWindow) {
                    pData->pMainWindow->ShowExportDialog();
                }
                return 0;
            }
            
            if (PtInRect(&pData->okRect, pt)) {
                // Get values
                char urlBuffer[512] = {0};
                char keyBuffer[512] = {0};
                GetWindowTextA(pData->hUrlEdit, urlBuffer, sizeof(urlBuffer));
                GetWindowTextA(pData->hKeyEdit, keyBuffer, sizeof(keyBuffer));
                
                // Get checkbox state (custom checkbox)
                bool ctrlEnterEnabled = pData->isCtrlEnterChecked;
                
                if (pData->pMainWindow) {
                    pData->pMainWindow->httpClient_.setBaseUrl(urlBuffer);
                    pData->pMainWindow->httpClient_.setApiKey(keyBuffer);
                    pData->pMainWindow->enableCtrlEnterToSend_ = ctrlEnterEnabled;
                    pData->pMainWindow->SaveSettingsToFile(urlBuffer, keyBuffer, ctrlEnterEnabled);
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
    dlgData.isCtrlEnterChecked = enableCtrlEnterToSend_;
    dlgData.isCheckboxHover = false;
    dlgData.isOkHover = false;
    dlgData.isCancelHover = false;
    dlgData.isExportHover = false;
    
    // Create dialog window
    HINSTANCE hInst = hInstance_ ? hInstance_ : GetModuleHandle(NULL);
    HWND hDlg = CreateWindowExW(
        WS_EX_DLGMODALFRAME | WS_EX_TOPMOST,
        L"SenAISettingsDialog",
        UiStrings::Get(IDS_SETTINGS_TITLE).c_str(),
        WS_POPUP | WS_CAPTION | WS_SYSMENU,
        CW_USEDEFAULT, CW_USEDEFAULT,
        520, 290,  // Increased height for checkbox
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