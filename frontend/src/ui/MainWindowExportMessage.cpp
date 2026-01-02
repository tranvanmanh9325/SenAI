#include <windows.h>
#include <commdlg.h>
#include <windowsx.h>
#include <dwmapi.h>
#include "MainWindow.h"
#include "MainWindowHelpers.h"
#include "../core/ExportService.h"
#include <string>

// Export message dialog structure
struct ExportMessageDlgData {
    MainWindow* pMainWindow;
    std::wstring message;
    bool isSuccess;
    bool isOkHover;
    RECT okRect;
    RECT messageRect;
    RECT iconRect;
    bool shouldClose;
};

LRESULT CALLBACK MainWindow::ExportMessageDlgProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    ExportMessageDlgData* pData = (ExportMessageDlgData*)GetWindowLongPtr(hwnd, GWLP_USERDATA);
    
    switch (uMsg) {
        case WM_CREATE: {
            CREATESTRUCT* pCreate = (CREATESTRUCT*)lParam;
            pData = (ExportMessageDlgData*)pCreate->lpCreateParams;
            SetWindowLongPtr(hwnd, GWLP_USERDATA, (LONG_PTR)pData);
            
            if (pData) {
                pData->isOkHover = false;
                // Center OK button horizontally, move up a bit to avoid cutoff
                pData->okRect = {160, 130, 240, 162};
                // Message text: wider, centered vertically with icon
                pData->messageRect = {80, 55, 360, 110};
                // Icon: centered vertically with message
                pData->iconRect = {30, 55, 70, 95};
                pData->shouldClose = false;
            }
            
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
            
            // Draw header
            RECT headerRect = {0, 0, clientRect.right, 40};
            HBRUSH headerBrush = CreateSolidBrush(RGB(16, 22, 40));
            FillRect(hdcMem, &headerRect, headerBrush);
            DeleteObject(headerBrush);
            
            // Draw title
            SetBkMode(hdcMem, TRANSPARENT);
            SetTextColor(hdcMem, RGB(232, 236, 255));
            HFONT hTitleFont = CreateFontW(-20, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
            HFONT hOldFont = (HFONT)SelectObject(hdcMem, hTitleFont);
            RECT titleRect = {20, 0, clientRect.right, 40};
            DrawTextW(hdcMem, UiStrings::Get(IDS_EXPORT_TITLE).c_str(), -1, &titleRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
            SelectObject(hdcMem, hOldFont);
            DeleteObject(hTitleFont);
            
            // Draw cyan line
            HPEN headerPen = CreatePen(PS_SOLID, 1, RGB(74, 215, 255));
            HGDIOBJ oldPen = SelectObject(hdcMem, headerPen);
            MoveToEx(hdcMem, 0, headerRect.bottom - 1, NULL);
            LineTo(hdcMem, clientRect.right, headerRect.bottom - 1);
            SelectObject(hdcMem, oldPen);
            DeleteObject(headerPen);
            
            if (pData) {
                // Draw icon (success = checkmark, error = X)
                int iconSize = 32;
                COLORREF iconColor = pData->isSuccess ? RGB(74, 215, 255) : RGB(255, 120, 120);
                
                if (pData->isSuccess) {
                    // Draw checkmark circle
                    HBRUSH iconBrush = CreateSolidBrush(iconColor);
                    HPEN iconPen = CreatePen(PS_SOLID, 2, iconColor);
                    HGDIOBJ oldIconBrush = SelectObject(hdcMem, iconBrush);
                    HGDIOBJ oldIconPen = SelectObject(hdcMem, iconPen);
                    Ellipse(hdcMem, pData->iconRect.left, pData->iconRect.top, 
                           pData->iconRect.right, pData->iconRect.bottom);
                    
                    // Draw checkmark
                    HPEN checkmarkPen = CreatePen(PS_SOLID, 3, RGB(255, 255, 255));
                    SelectObject(hdcMem, checkmarkPen);
                    int centerX = (pData->iconRect.left + pData->iconRect.right) / 2;
                    int centerY = (pData->iconRect.top + pData->iconRect.bottom) / 2;
                    int checkSize = 12;
                    
                    MoveToEx(hdcMem, centerX - checkSize/2, centerY, NULL);
                    LineTo(hdcMem, centerX - 2, centerY + checkSize/2);
                    LineTo(hdcMem, centerX + checkSize/2, centerY - checkSize/2);
                    
                    SelectObject(hdcMem, oldIconBrush);
                    SelectObject(hdcMem, oldIconPen);
                    DeleteObject(iconBrush);
                    DeleteObject(iconPen);
                    DeleteObject(checkmarkPen);
                } else {
                    // Draw error X circle
                    HBRUSH iconBrush = CreateSolidBrush(iconColor);
                    HPEN iconPen = CreatePen(PS_SOLID, 2, iconColor);
                    HGDIOBJ oldIconBrush = SelectObject(hdcMem, iconBrush);
                    HGDIOBJ oldIconPen = SelectObject(hdcMem, iconPen);
                    Ellipse(hdcMem, pData->iconRect.left, pData->iconRect.top, 
                           pData->iconRect.right, pData->iconRect.bottom);
                    
                    // Draw X
                    HPEN xPen = CreatePen(PS_SOLID, 3, RGB(255, 255, 255));
                    SelectObject(hdcMem, xPen);
                    int centerX = (pData->iconRect.left + pData->iconRect.right) / 2;
                    int centerY = (pData->iconRect.top + pData->iconRect.bottom) / 2;
                    int xSize = 10;
                    
                    MoveToEx(hdcMem, centerX - xSize/2, centerY - xSize/2, NULL);
                    LineTo(hdcMem, centerX + xSize/2, centerY + xSize/2);
                    MoveToEx(hdcMem, centerX + xSize/2, centerY - xSize/2, NULL);
                    LineTo(hdcMem, centerX - xSize/2, centerY + xSize/2);
                    
                    SelectObject(hdcMem, oldIconBrush);
                    SelectObject(hdcMem, oldIconPen);
                    DeleteObject(iconBrush);
                    DeleteObject(iconPen);
                    DeleteObject(xPen);
                }
                
                // Draw message text
                HFONT hMessageFont = CreateFontW(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                    DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                    CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
                hOldFont = (HFONT)SelectObject(hdcMem, hMessageFont);
                SetTextColor(hdcMem, RGB(232, 236, 255));
                DrawTextW(hdcMem, pData->message.c_str(), -1, &pData->messageRect, 
                         DT_LEFT | DT_VCENTER | DT_WORDBREAK);
                SelectObject(hdcMem, hOldFont);
                DeleteObject(hMessageFont);
                
                // Draw OK button
                int radius = 8;
                COLORREF okBg = pData->isOkHover ? RGB(74, 215, 255) : RGB(25, 36, 64);
                COLORREF okBorder = RGB(74, 215, 255);
                COLORREF okText = pData->isOkHover ? RGB(0, 0, 0) : RGB(232, 236, 255);
                
                HBRUSH okBrush = CreateSolidBrush(okBg);
                HPEN okPen = CreatePen(PS_SOLID, 1, okBorder);
                HGDIOBJ oldBrush = SelectObject(hdcMem, okBrush);
                oldPen = SelectObject(hdcMem, okPen);
                RoundRect(hdcMem, pData->okRect.left, pData->okRect.top, 
                         pData->okRect.right, pData->okRect.bottom, radius, radius);
                SelectObject(hdcMem, oldBrush);
                SelectObject(hdcMem, oldPen);
                DeleteObject(okBrush);
                DeleteObject(okPen);
                
                SetTextColor(hdcMem, okText);
                hOldFont = (HFONT)SelectObject(hdcMem, hMessageFont);
                DrawTextW(hdcMem, UiStrings::Get(IDS_OK_BUTTON).c_str(), -1, &pData->okRect, 
                         DT_CENTER | DT_VCENTER | DT_SINGLELINE);
                SelectObject(hdcMem, hOldFont);
            }
            
            // Blit to screen
            BitBlt(hdc, 0, 0, clientRect.right, clientRect.bottom, hdcMem, 0, 0, SRCCOPY);
            
            SelectObject(hdcMem, hbmOld);
            DeleteObject(hbmMem);
            DeleteDC(hdcMem);
            
            EndPaint(hwnd, &ps);
            return 0;
        }
        
        case WM_MOUSEMOVE: {
            if (!pData) break;
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            bool newOkHover = PtInRect(&pData->okRect, pt);
            
            if (newOkHover != pData->isOkHover) {
                pData->isOkHover = newOkHover;
                InvalidateRect(hwnd, NULL, FALSE);
            }
            return 0;
        }
        
        case WM_LBUTTONDOWN: {
            if (!pData) break;
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            
            if (PtInRect(&pData->okRect, pt)) {
                pData->shouldClose = true;
                DestroyWindow(hwnd);
                return 0;
            }
            break;
        }
        
        case WM_CLOSE:
            if (pData) {
                pData->shouldClose = true;
            }
            DestroyWindow(hwnd);
            return 0;
            
        case WM_ERASEBKGND:
            return TRUE;
    }
    
    return DefWindowProcW(hwnd, uMsg, wParam, lParam);
}

void MainWindow::ShowExportMessageDialog(const std::wstring& message, bool isSuccess) {
    // Register dialog class if not already registered
    static bool classRegistered = false;
    if (!classRegistered) {
        WNDCLASSW wc = {};
        wc.lpfnWndProc = ExportMessageDlgProc;
        wc.hInstance = hInstance_;
        wc.lpszClassName = L"SenAIExportMessageDialog";
        wc.hbrBackground = NULL;
        wc.hCursor = LoadCursor(NULL, IDC_ARROW);
        wc.style = CS_HREDRAW | CS_VREDRAW;
        RegisterClassW(&wc);
        classRegistered = true;
    }
    
    // Create dialog data
    ExportMessageDlgData dlgData = {};
    dlgData.pMainWindow = this;
    dlgData.message = message;
    dlgData.isSuccess = isSuccess;
    dlgData.isOkHover = false;
    dlgData.shouldClose = false;
    
    // Create dialog window
    HINSTANCE hInst = hInstance_ ? hInstance_ : GetModuleHandle(NULL);
    HWND hDlg = CreateWindowExW(
        WS_EX_DLGMODALFRAME | WS_EX_TOPMOST,
        L"SenAIExportMessageDialog",
        UiStrings::Get(IDS_EXPORT_TITLE).c_str(),
        WS_POPUP | WS_CAPTION | WS_SYSMENU,
        CW_USEDEFAULT, CW_USEDEFAULT,
        400, 210,
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