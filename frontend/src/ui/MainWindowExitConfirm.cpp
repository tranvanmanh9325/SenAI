#include <windows.h>
#include <windowsx.h>
#include <dwmapi.h>
#include "MainWindow.h"
#include "MainWindowHelpers.h"
#include <string>

// Exit confirmation dialog implementation

// Exit confirmation dialog structure
struct ExitConfirmDlgData {
    MainWindow* pMainWindow;
    bool isYesHover;
    bool isNoHover;
    bool isCloseHover;
    RECT yesRect;
    RECT noRect;
    RECT closeRect;
    bool shouldClose;
    bool result; // true if user clicked Yes
};

LRESULT CALLBACK MainWindow::ExitConfirmDlgProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    ExitConfirmDlgData* pData = (ExitConfirmDlgData*)GetWindowLongPtr(hwnd, GWLP_USERDATA);
    
    switch (uMsg) {
        case WM_CREATE: {
            CREATESTRUCT* pCreate = (CREATESTRUCT*)lParam;
            pData = (ExitConfirmDlgData*)pCreate->lpCreateParams;
            SetWindowLongPtr(hwnd, GWLP_USERDATA, (LONG_PTR)pData);
            
            // Button rects - positioned in dialog (adjusted for larger dialog)
            pData->yesRect = {200, 130, 280, 162};
            pData->noRect = {300, 130, 380, 162};
            // Close button in title bar (top right) - initialize in WM_SIZE
            pData->closeRect = {0, 0, 0, 0};
            pData->isYesHover = false;
            pData->isNoHover = false;
            pData->isCloseHover = false;
            pData->shouldClose = false;
            pData->result = false;
            
            // Initialize close button position
            RECT clientRect;
            GetClientRect(hwnd, &clientRect);
            int closeBtnSize = 30;
            pData->closeRect = {clientRect.right - closeBtnSize - 5, 5, clientRect.right - 5, 5 + closeBtnSize};
            
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
            RECT titleRect = {20, 0, clientRect.right - 40, 40};  // Leave space for close button
            DrawTextW(hdcMem, UiStrings::Get(IDS_EXIT_CONFIRM_TITLE).c_str(), -1, &titleRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
            
            // Draw close button (X) in title bar
            COLORREF closeColor = pData->isCloseHover ? RGB(255, 100, 100) : RGB(200, 210, 230);
            HPEN closePen = CreatePen(PS_SOLID, 2, closeColor);
            HGDIOBJ oldClosePen = SelectObject(hdcMem, closePen);
            int closeCenterX = (pData->closeRect.left + pData->closeRect.right) / 2;
            int closeCenterY = (pData->closeRect.top + pData->closeRect.bottom) / 2;
            int closeSize = 12;
            MoveToEx(hdcMem, closeCenterX - closeSize/2, closeCenterY - closeSize/2, NULL);
            LineTo(hdcMem, closeCenterX + closeSize/2, closeCenterY + closeSize/2);
            MoveToEx(hdcMem, closeCenterX + closeSize/2, closeCenterY - closeSize/2, NULL);
            LineTo(hdcMem, closeCenterX - closeSize/2, closeCenterY + closeSize/2);
            SelectObject(hdcMem, oldClosePen);
            DeleteObject(closePen);
            
            SelectObject(hdcMem, hOldFont);
            DeleteObject(hTitleFont);
            
            // Draw cyan line at the bottom of header (after title)
            HPEN headerPen = CreatePen(PS_SOLID, 1, RGB(74, 215, 255));
            HGDIOBJ oldPen = SelectObject(hdcMem, headerPen);
            MoveToEx(hdcMem, 0, headerRect.bottom - 1, NULL);
            LineTo(hdcMem, clientRect.right, headerRect.bottom - 1);
            SelectObject(hdcMem, oldPen);
            DeleteObject(headerPen);
            
            // Draw question mark icon (circular with question mark)
            int iconSize = 48;
            int iconX = 30;
            int iconY = 70;  // More space from header
            RECT iconRect = {iconX, iconY, iconX + iconSize, iconY + iconSize};
            
            // Draw icon background (cyan circle)
            HBRUSH iconBrush = CreateSolidBrush(RGB(74, 215, 255));
            HPEN iconPen = CreatePen(PS_SOLID, 2, RGB(74, 215, 255));
            HGDIOBJ oldIconBrush = SelectObject(hdcMem, iconBrush);
            HGDIOBJ oldIconPen = SelectObject(hdcMem, iconPen);
            Ellipse(hdcMem, iconRect.left, iconRect.top, iconRect.right, iconRect.bottom);
            
            // Draw question mark (white)
            SetTextColor(hdcMem, RGB(0, 0, 0));
            SetBkMode(hdcMem, TRANSPARENT);
            HFONT hIconFont = CreateFontW(-32, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
            HFONT hOldIconFont = (HFONT)SelectObject(hdcMem, hIconFont);
            RECT questionRect = {iconX, iconY, iconX + iconSize, iconY + iconSize};
            DrawTextW(hdcMem, L"?", -1, &questionRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            SelectObject(hdcMem, hOldIconFont);
            DeleteObject(hIconFont);
            
            SelectObject(hdcMem, oldIconBrush);
            SelectObject(hdcMem, oldIconPen);
            DeleteObject(iconBrush);
            DeleteObject(iconPen);
            
            // Draw message text
            HFONT hLabelFont = CreateFontW(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
            hOldFont = (HFONT)SelectObject(hdcMem, hLabelFont);
            SetTextColor(hdcMem, RGB(232, 236, 255));
            RECT messageRect = {iconX + iconSize + 20, iconY, clientRect.right - 20, iconY + iconSize + 20};
            DrawTextW(hdcMem, UiStrings::Get(IDS_EXIT_CONFIRM_MESSAGE).c_str(), -1, &messageRect, DT_LEFT | DT_TOP | DT_WORDBREAK);
            
            // Draw buttons
            int radius = 8;
            
            // Yes button
            COLORREF yesBg = pData->isYesHover ? RGB(74, 215, 255) : RGB(25, 36, 64);
            COLORREF yesBorder = RGB(74, 215, 255);
            COLORREF yesText = pData->isYesHover ? RGB(0, 0, 0) : RGB(232, 236, 255);
            
            HBRUSH yesBrush = CreateSolidBrush(yesBg);
            HPEN yesPen = CreatePen(PS_SOLID, 1, yesBorder);
            HGDIOBJ oldBrush = SelectObject(hdcMem, yesBrush);
            oldPen = SelectObject(hdcMem, yesPen);
            RoundRect(hdcMem, pData->yesRect.left, pData->yesRect.top, pData->yesRect.right, pData->yesRect.bottom, radius, radius);
            SelectObject(hdcMem, oldBrush);
            SelectObject(hdcMem, oldPen);
            DeleteObject(yesBrush);
            DeleteObject(yesPen);
            
            SetTextColor(hdcMem, yesText);
            DrawTextW(hdcMem, UiStrings::Get(IDS_YES_BUTTON).c_str(), -1, &pData->yesRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            
            // No button
            COLORREF noBg = pData->isNoHover ? RGB(40, 50, 70) : RGB(25, 36, 64);
            COLORREF noBorder = RGB(60, 90, 130);
            COLORREF noText = RGB(200, 210, 230);
            
            HBRUSH noBrush = CreateSolidBrush(noBg);
            HPEN noPen = CreatePen(PS_SOLID, 1, noBorder);
            oldBrush = SelectObject(hdcMem, noBrush);
            oldPen = SelectObject(hdcMem, noPen);
            RoundRect(hdcMem, pData->noRect.left, pData->noRect.top, pData->noRect.right, pData->noRect.bottom, radius, radius);
            SelectObject(hdcMem, oldBrush);
            SelectObject(hdcMem, oldPen);
            DeleteObject(noBrush);
            DeleteObject(noPen);
            
            SetTextColor(hdcMem, noText);
            DrawTextW(hdcMem, UiStrings::Get(IDS_NO_BUTTON).c_str(), -1, &pData->noRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            SelectObject(hdcMem, hOldFont);
            DeleteObject(hLabelFont);
            
            // Blit to screen
            BitBlt(hdc, 0, 0, clientRect.right, clientRect.bottom, hdcMem, 0, 0, SRCCOPY);
            
            SelectObject(hdcMem, hbmOld);
            DeleteObject(hbmMem);
            DeleteDC(hdcMem);
            
            EndPaint(hwnd, &ps);
            return 0;
        }
        
        case WM_CTLCOLORSTATIC: {
            HDC hdc = (HDC)wParam;
            SetBkMode(hdc, TRANSPARENT);
            SetTextColor(hdc, RGB(200, 210, 230));
            return (LRESULT)GetStockObject(NULL_BRUSH);
        }
        
        case WM_MOUSEMOVE: {
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            bool newYesHover = PtInRect(&pData->yesRect, pt);
            bool newNoHover = PtInRect(&pData->noRect, pt);
            bool newCloseHover = PtInRect(&pData->closeRect, pt);
            
            if (newYesHover != pData->isYesHover || newNoHover != pData->isNoHover || newCloseHover != pData->isCloseHover) {
                pData->isYesHover = newYesHover;
                pData->isNoHover = newNoHover;
                pData->isCloseHover = newCloseHover;
                InvalidateRect(hwnd, NULL, FALSE);
            }
            return 0;
        }
        
        case WM_LBUTTONDOWN: {
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            if (PtInRect(&pData->closeRect, pt)) {
                // Close button clicked
                pData->result = false;
                pData->shouldClose = true;
                DestroyWindow(hwnd);
                return 0;
            } else if (PtInRect(&pData->yesRect, pt)) {
                pData->result = true;
                pData->shouldClose = true;
                DestroyWindow(hwnd);
                return 0;
            } else if (PtInRect(&pData->noRect, pt)) {
                pData->result = false;
                pData->shouldClose = true;
                DestroyWindow(hwnd);
                return 0;
            }
            break;
        }
        
        case WM_LBUTTONUP: {
            // Handle button release for better UX
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            if (PtInRect(&pData->yesRect, pt) || PtInRect(&pData->noRect, pt)) {
                InvalidateRect(hwnd, NULL, FALSE);
            }
            break;
        }
        
        case WM_KEYDOWN: {
            // Handle Enter (Yes) and Escape (No)
            if (wParam == VK_RETURN) {
                pData->result = true;
                pData->shouldClose = true;
                DestroyWindow(hwnd);
                return 0;
            } else if (wParam == VK_ESCAPE) {
                pData->result = false;
                pData->shouldClose = true;
                DestroyWindow(hwnd);
                return 0;
            }
            break;
        }
        
        case WM_CLOSE:
            pData->result = false;
            pData->shouldClose = true;
            DestroyWindow(hwnd);
            return 0;
            
        case WM_SIZE: {
            // Update close button position when window is resized
            RECT clientRect;
            GetClientRect(hwnd, &clientRect);
            int closeBtnSize = 30;
            pData->closeRect = {clientRect.right - closeBtnSize - 5, 5, clientRect.right - 5, 5 + closeBtnSize};
            break;
        }
        
        case WM_ERASEBKGND:
            return TRUE;
    }
    
    return DefWindowProcW(hwnd, uMsg, wParam, lParam);
}

bool MainWindow::ShowExitConfirmationDialog() {
    // Register dialog class if not already registered
    static bool classRegistered = false;
    if (!classRegistered) {
        WNDCLASSW wc = {};
        wc.lpfnWndProc = ExitConfirmDlgProc;
        wc.hInstance = hInstance_;
        wc.lpszClassName = L"SenAIExitConfirmDialog";
        wc.hbrBackground = NULL;
        wc.hCursor = LoadCursor(NULL, IDC_ARROW);
        wc.style = CS_HREDRAW | CS_VREDRAW;
        RegisterClassW(&wc);
        classRegistered = true;
    }
    
    // Create dialog data
    ExitConfirmDlgData dlgData = {};
    dlgData.pMainWindow = this;
    dlgData.isYesHover = false;
    dlgData.isNoHover = false;
    dlgData.shouldClose = false;
    dlgData.result = false;
    
    // Create dialog window (larger size to prevent clipping, no caption for custom title bar)
    HINSTANCE hInst = hInstance_ ? hInstance_ : GetModuleHandle(NULL);
    HWND hDlg = CreateWindowExW(
        WS_EX_DLGMODALFRAME | WS_EX_TOPMOST,
        L"SenAIExitConfirmDialog",
        UiStrings::Get(IDS_EXIT_CONFIRM_TITLE).c_str(),
        WS_POPUP,  // Removed WS_CAPTION and WS_SYSMENU for custom title bar
        CW_USEDEFAULT, CW_USEDEFAULT,
        480, 220,  // Increased width and height
        hwnd_,
        NULL,
        hInst,
        &dlgData
    );
    
    if (!hDlg) return false;
    
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
    
    return dlgData.result;
}