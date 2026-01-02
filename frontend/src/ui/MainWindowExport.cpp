#include <windows.h>
#include <commdlg.h>
#include <windowsx.h>
#include <dwmapi.h>
#include "MainWindow.h"
#include "MainWindowHelpers.h"
#include "../core/ExportService.h"
#include <string>

// Export dialog structure
struct ExportDlgData {
    MainWindow* pMainWindow;
    ExportFormat selectedFormat;
    ExportScope selectedScope;
    bool isFormatTxtHover;
    bool isFormatMdHover;
    bool isFormatJsonHover;
    bool isScopeCurrentHover;
    bool isScopeAllHover;
    bool isExportHover;
    bool isCancelHover;
    RECT formatTxtRect;
    RECT formatMdRect;
    RECT formatJsonRect;
    RECT scopeCurrentRect;
    RECT scopeAllRect;
    RECT exportRect;
    RECT cancelRect;
    bool shouldClose;
};

LRESULT CALLBACK MainWindow::ExportDlgProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {
    ExportDlgData* pData = (ExportDlgData*)GetWindowLongPtr(hwnd, GWLP_USERDATA);
    
    switch (uMsg) {
        case WM_CREATE: {
            CREATESTRUCT* pCreate = (CREATESTRUCT*)lParam;
            pData = (ExportDlgData*)pCreate->lpCreateParams;
            SetWindowLongPtr(hwnd, GWLP_USERDATA, (LONG_PTR)pData);
            
            // Initialize default values
            if (pData) {
                pData->selectedFormat = ExportFormat::Markdown;
                pData->selectedScope = ExportScope::CurrentConversation;
                pData->isFormatTxtHover = false;
                pData->isFormatMdHover = false;
                pData->isFormatJsonHover = false;
                pData->isScopeCurrentHover = false;
                pData->isScopeAllHover = false;
                pData->isExportHover = false;
                pData->isCancelHover = false;
                
                // Format radio buttons
                pData->formatTxtRect = {30, 60, 150, 85};
                pData->formatMdRect = {30, 90, 150, 115};
                pData->formatJsonRect = {30, 120, 150, 145};
                
                // Scope radio buttons
                pData->scopeCurrentRect = {30, 170, 250, 195};
                pData->scopeAllRect = {30, 200, 250, 225};
                
                // Buttons - positioned with more space from bottom
                pData->exportRect = {280, 250, 360, 282};
                pData->cancelRect = {370, 250, 450, 282};
                
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
                // Draw labels
                HFONT hLabelFont = CreateFontW(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                    DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                    CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
                hOldFont = (HFONT)SelectObject(hdcMem, hLabelFont);
                SetTextColor(hdcMem, RGB(200, 210, 230));
                
                RECT formatLabelRect = {20, 45, 200, 60};
                DrawTextW(hdcMem, UiStrings::Get(IDS_EXPORT_FORMAT_LABEL).c_str(), -1, &formatLabelRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
                
                RECT scopeLabelRect = {20, 155, 200, 170};
                DrawTextW(hdcMem, UiStrings::Get(IDS_EXPORT_SCOPE_LABEL).c_str(), -1, &scopeLabelRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
                
                SelectObject(hdcMem, hOldFont);
                DeleteObject(hLabelFont);
                
                // Draw format radio buttons
                int radioSize = 16;
                int radioX = pData->formatTxtRect.left;
                
                // TXT
                int txtY = pData->formatTxtRect.top + (pData->formatTxtRect.bottom - pData->formatTxtRect.top - radioSize) / 2;
                RECT txtRadio = {radioX, txtY, radioX + radioSize, txtY + radioSize};
                COLORREF radioColor = (pData->selectedFormat == ExportFormat::TXT) ? RGB(74, 215, 255) : RGB(60, 90, 130);
                if (pData->isFormatTxtHover) radioColor = RGB(100, 150, 200);
                
                HBRUSH radioBrush = CreateSolidBrush((pData->selectedFormat == ExportFormat::TXT) ? radioColor : RGB(18, 24, 42));
                HPEN radioPen = CreatePen(PS_SOLID, 1, radioColor);
                HGDIOBJ oldRadioBrush = SelectObject(hdcMem, radioBrush);
                HGDIOBJ oldRadioPen = SelectObject(hdcMem, radioPen);
                Ellipse(hdcMem, txtRadio.left, txtRadio.top, txtRadio.right, txtRadio.bottom);
                if (pData->selectedFormat == ExportFormat::TXT) {
                    // Draw inner circle
                    HBRUSH innerBrush = CreateSolidBrush(RGB(74, 215, 255));
                    SelectObject(hdcMem, innerBrush);
                    Ellipse(hdcMem, txtRadio.left + 4, txtRadio.top + 4, txtRadio.right - 4, txtRadio.bottom - 4);
                    DeleteObject(innerBrush);
                }
                SelectObject(hdcMem, oldRadioBrush);
                SelectObject(hdcMem, oldRadioPen);
                DeleteObject(radioBrush);
                DeleteObject(radioPen);
                
                SetTextColor(hdcMem, RGB(232, 236, 255));
                RECT txtLabel = {radioX + radioSize + 10, pData->formatTxtRect.top, pData->formatTxtRect.right, pData->formatTxtRect.bottom};
                DrawTextW(hdcMem, L"Text (.txt)", -1, &txtLabel, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
                
                // Markdown
                int mdY = pData->formatMdRect.top + (pData->formatMdRect.bottom - pData->formatMdRect.top - radioSize) / 2;
                RECT mdRadio = {radioX, mdY, radioX + radioSize, mdY + radioSize};
                radioColor = (pData->selectedFormat == ExportFormat::Markdown) ? RGB(74, 215, 255) : RGB(60, 90, 130);
                if (pData->isFormatMdHover) radioColor = RGB(100, 150, 200);
                
                radioBrush = CreateSolidBrush((pData->selectedFormat == ExportFormat::Markdown) ? radioColor : RGB(18, 24, 42));
                radioPen = CreatePen(PS_SOLID, 1, radioColor);
                oldRadioBrush = SelectObject(hdcMem, radioBrush);
                oldRadioPen = SelectObject(hdcMem, radioPen);
                Ellipse(hdcMem, mdRadio.left, mdRadio.top, mdRadio.right, mdRadio.bottom);
                if (pData->selectedFormat == ExportFormat::Markdown) {
                    HBRUSH innerBrush = CreateSolidBrush(RGB(74, 215, 255));
                    SelectObject(hdcMem, innerBrush);
                    Ellipse(hdcMem, mdRadio.left + 4, mdRadio.top + 4, mdRadio.right - 4, mdRadio.bottom - 4);
                    DeleteObject(innerBrush);
                }
                SelectObject(hdcMem, oldRadioBrush);
                SelectObject(hdcMem, oldRadioPen);
                DeleteObject(radioBrush);
                DeleteObject(radioPen);
                
                RECT mdLabel = {radioX + radioSize + 10, pData->formatMdRect.top, pData->formatMdRect.right, pData->formatMdRect.bottom};
                DrawTextW(hdcMem, L"Markdown (.md)", -1, &mdLabel, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
                
                // JSON
                int jsonY = pData->formatJsonRect.top + (pData->formatJsonRect.bottom - pData->formatJsonRect.top - radioSize) / 2;
                RECT jsonRadio = {radioX, jsonY, radioX + radioSize, jsonY + radioSize};
                radioColor = (pData->selectedFormat == ExportFormat::JSON) ? RGB(74, 215, 255) : RGB(60, 90, 130);
                if (pData->isFormatJsonHover) radioColor = RGB(100, 150, 200);
                
                radioBrush = CreateSolidBrush((pData->selectedFormat == ExportFormat::JSON) ? radioColor : RGB(18, 24, 42));
                radioPen = CreatePen(PS_SOLID, 1, radioColor);
                oldRadioBrush = SelectObject(hdcMem, radioBrush);
                oldRadioPen = SelectObject(hdcMem, radioPen);
                Ellipse(hdcMem, jsonRadio.left, jsonRadio.top, jsonRadio.right, jsonRadio.bottom);
                if (pData->selectedFormat == ExportFormat::JSON) {
                    HBRUSH innerBrush = CreateSolidBrush(RGB(74, 215, 255));
                    SelectObject(hdcMem, innerBrush);
                    Ellipse(hdcMem, jsonRadio.left + 4, jsonRadio.top + 4, jsonRadio.right - 4, jsonRadio.bottom - 4);
                    DeleteObject(innerBrush);
                }
                SelectObject(hdcMem, oldRadioBrush);
                SelectObject(hdcMem, oldRadioPen);
                DeleteObject(radioBrush);
                DeleteObject(radioPen);
                
                RECT jsonLabel = {radioX + radioSize + 10, pData->formatJsonRect.top, pData->formatJsonRect.right, pData->formatJsonRect.bottom};
                DrawTextW(hdcMem, L"JSON (.json)", -1, &jsonLabel, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
                
                // Draw scope radio buttons
                // Current
                int currentY = pData->scopeCurrentRect.top + (pData->scopeCurrentRect.bottom - pData->scopeCurrentRect.top - radioSize) / 2;
                RECT currentRadio = {radioX, currentY, radioX + radioSize, currentY + radioSize};
                radioColor = (pData->selectedScope == ExportScope::CurrentConversation) ? RGB(74, 215, 255) : RGB(60, 90, 130);
                if (pData->isScopeCurrentHover) radioColor = RGB(100, 150, 200);
                
                radioBrush = CreateSolidBrush((pData->selectedScope == ExportScope::CurrentConversation) ? radioColor : RGB(18, 24, 42));
                radioPen = CreatePen(PS_SOLID, 1, radioColor);
                oldRadioBrush = SelectObject(hdcMem, radioBrush);
                oldRadioPen = SelectObject(hdcMem, radioPen);
                Ellipse(hdcMem, currentRadio.left, currentRadio.top, currentRadio.right, currentRadio.bottom);
                if (pData->selectedScope == ExportScope::CurrentConversation) {
                    HBRUSH innerBrush = CreateSolidBrush(RGB(74, 215, 255));
                    SelectObject(hdcMem, innerBrush);
                    Ellipse(hdcMem, currentRadio.left + 4, currentRadio.top + 4, currentRadio.right - 4, currentRadio.bottom - 4);
                    DeleteObject(innerBrush);
                }
                SelectObject(hdcMem, oldRadioBrush);
                SelectObject(hdcMem, oldRadioPen);
                DeleteObject(radioBrush);
                DeleteObject(radioPen);
                
                RECT currentLabel = {radioX + radioSize + 10, pData->scopeCurrentRect.top, pData->scopeCurrentRect.right, pData->scopeCurrentRect.bottom};
                DrawTextW(hdcMem, UiStrings::Get(IDS_EXPORT_CURRENT).c_str(), -1, &currentLabel, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
                
                // All
                int allY = pData->scopeAllRect.top + (pData->scopeAllRect.bottom - pData->scopeAllRect.top - radioSize) / 2;
                RECT allRadio = {radioX, allY, radioX + radioSize, allY + radioSize};
                radioColor = (pData->selectedScope == ExportScope::AllConversations) ? RGB(74, 215, 255) : RGB(60, 90, 130);
                if (pData->isScopeAllHover) radioColor = RGB(100, 150, 200);
                
                radioBrush = CreateSolidBrush((pData->selectedScope == ExportScope::AllConversations) ? radioColor : RGB(18, 24, 42));
                radioPen = CreatePen(PS_SOLID, 1, radioColor);
                oldRadioBrush = SelectObject(hdcMem, radioBrush);
                oldRadioPen = SelectObject(hdcMem, radioPen);
                Ellipse(hdcMem, allRadio.left, allRadio.top, allRadio.right, allRadio.bottom);
                if (pData->selectedScope == ExportScope::AllConversations) {
                    HBRUSH innerBrush = CreateSolidBrush(RGB(74, 215, 255));
                    SelectObject(hdcMem, innerBrush);
                    Ellipse(hdcMem, allRadio.left + 4, allRadio.top + 4, allRadio.right - 4, allRadio.bottom - 4);
                    DeleteObject(innerBrush);
                }
                SelectObject(hdcMem, oldRadioBrush);
                SelectObject(hdcMem, oldRadioPen);
                DeleteObject(radioBrush);
                DeleteObject(radioPen);
                
                RECT allLabel = {radioX + radioSize + 10, pData->scopeAllRect.top, pData->scopeAllRect.right, pData->scopeAllRect.bottom};
                DrawTextW(hdcMem, UiStrings::Get(IDS_EXPORT_ALL).c_str(), -1, &allLabel, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
                
                // Draw buttons
                int radius = 8;
                COLORREF exportBg = pData->isExportHover ? RGB(74, 215, 255) : RGB(25, 36, 64);
                COLORREF exportBorder = RGB(74, 215, 255);
                COLORREF exportText = pData->isExportHover ? RGB(0, 0, 0) : RGB(232, 236, 255);
                
                HBRUSH exportBrush = CreateSolidBrush(exportBg);
                HPEN exportPen = CreatePen(PS_SOLID, 1, exportBorder);
                HGDIOBJ oldBrush = SelectObject(hdcMem, exportBrush);
                oldPen = SelectObject(hdcMem, exportPen);
                RoundRect(hdcMem, pData->exportRect.left, pData->exportRect.top, pData->exportRect.right, pData->exportRect.bottom, radius, radius);
                SelectObject(hdcMem, oldBrush);
                SelectObject(hdcMem, oldPen);
                DeleteObject(exportBrush);
                DeleteObject(exportPen);
                
                SetTextColor(hdcMem, exportText);
                hOldFont = (HFONT)SelectObject(hdcMem, hLabelFont);
                DrawTextW(hdcMem, L"Xuất", -1, &pData->exportRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
                
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
            
            bool newFormatTxtHover = PtInRect(&pData->formatTxtRect, pt);
            bool newFormatMdHover = PtInRect(&pData->formatMdRect, pt);
            bool newFormatJsonHover = PtInRect(&pData->formatJsonRect, pt);
            bool newScopeCurrentHover = PtInRect(&pData->scopeCurrentRect, pt);
            bool newScopeAllHover = PtInRect(&pData->scopeAllRect, pt);
            bool newExportHover = PtInRect(&pData->exportRect, pt);
            bool newCancelHover = PtInRect(&pData->cancelRect, pt);
            
            bool needsRedraw = false;
            if (newFormatTxtHover != pData->isFormatTxtHover ||
                newFormatMdHover != pData->isFormatMdHover ||
                newFormatJsonHover != pData->isFormatJsonHover ||
                newScopeCurrentHover != pData->isScopeCurrentHover ||
                newScopeAllHover != pData->isScopeAllHover ||
                newExportHover != pData->isExportHover ||
                newCancelHover != pData->isCancelHover) {
                pData->isFormatTxtHover = newFormatTxtHover;
                pData->isFormatMdHover = newFormatMdHover;
                pData->isFormatJsonHover = newFormatJsonHover;
                pData->isScopeCurrentHover = newScopeCurrentHover;
                pData->isScopeAllHover = newScopeAllHover;
                pData->isExportHover = newExportHover;
                pData->isCancelHover = newCancelHover;
                needsRedraw = true;
            }
            
            if (needsRedraw) {
                InvalidateRect(hwnd, NULL, FALSE);
            }
            return 0;
        }
        
        case WM_LBUTTONDOWN: {
            if (!pData) break;
            POINT pt = {GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam)};
            
            // Handle format selection
            if (PtInRect(&pData->formatTxtRect, pt)) {
                pData->selectedFormat = ExportFormat::TXT;
                InvalidateRect(hwnd, NULL, FALSE);
                return 0;
            } else if (PtInRect(&pData->formatMdRect, pt)) {
                pData->selectedFormat = ExportFormat::Markdown;
                InvalidateRect(hwnd, NULL, FALSE);
                return 0;
            } else if (PtInRect(&pData->formatJsonRect, pt)) {
                pData->selectedFormat = ExportFormat::JSON;
                InvalidateRect(hwnd, NULL, FALSE);
                return 0;
            }
            
            // Handle scope selection
            if (PtInRect(&pData->scopeCurrentRect, pt)) {
                pData->selectedScope = ExportScope::CurrentConversation;
                InvalidateRect(hwnd, NULL, FALSE);
                return 0;
            } else if (PtInRect(&pData->scopeAllRect, pt)) {
                pData->selectedScope = ExportScope::AllConversations;
                InvalidateRect(hwnd, NULL, FALSE);
                return 0;
            }
            
            // Handle export button
            if (PtInRect(&pData->exportRect, pt)) {
                // Show file save dialog
                OPENFILENAMEW ofn = {0};
                wchar_t szFile[260] = {0};
                
                std::wstring defaultName = L"conversation";
                if (pData->selectedScope == ExportScope::AllConversations) {
                    defaultName = L"all_conversations";
                }
                defaultName += ExportService::GetFileExtension(pData->selectedFormat);
                
                wcscpy_s(szFile, defaultName.c_str());
                
                std::wstring filter = ExportService::GetFormatFilter(pData->selectedFormat);
                filter += L"\0";
                
                ofn.lStructSize = sizeof(OPENFILENAMEW);
                ofn.hwndOwner = hwnd;
                ofn.lpstrFile = szFile;
                ofn.nMaxFile = sizeof(szFile) / sizeof(wchar_t);
                ofn.lpstrFilter = filter.c_str();
                ofn.nFilterIndex = 1;
                ofn.lpstrFileTitle = NULL;
                ofn.nMaxFileTitle = 0;
                ofn.lpstrInitialDir = NULL;
                ofn.Flags = OFN_PATHMUSTEXIST | OFN_FILEMUSTEXIST | OFN_OVERWRITEPROMPT;
                
                if (GetSaveFileNameW(&ofn)) {
                    std::wstring filePath = szFile;
                    bool success = false;
                    
                    if (pData->pMainWindow) {
                        if (pData->selectedScope == ExportScope::CurrentConversation) {
                            success = pData->pMainWindow->ExportCurrentConversation(filePath, pData->selectedFormat);
                        } else {
                            success = pData->pMainWindow->ExportAllConversations(filePath, pData->selectedFormat);
                        }
                    }
                    
                    if (success) {
                        if (pData->pMainWindow) {
                            pData->pMainWindow->ShowExportMessageDialog(UiStrings::Get(IDS_EXPORT_SUCCESS), true);
                        }
                        pData->shouldClose = true;
                        DestroyWindow(hwnd);
                    } else {
                        if (pData->pMainWindow) {
                            pData->pMainWindow->ShowExportMessageDialog(UiStrings::Get(IDS_EXPORT_ERROR), false);
                        }
                    }
                }
                return 0;
            } else if (PtInRect(&pData->cancelRect, pt)) {
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

void MainWindow::ShowExportDialog() {
    // Register dialog class if not already registered
    static bool classRegistered = false;
    if (!classRegistered) {
        WNDCLASSW wc = {};
        wc.lpfnWndProc = ExportDlgProc;
        wc.hInstance = hInstance_;
        wc.lpszClassName = L"SenAIExportDialog";
        wc.hbrBackground = NULL;
        wc.hCursor = LoadCursor(NULL, IDC_ARROW);
        wc.style = CS_HREDRAW | CS_VREDRAW;
        RegisterClassW(&wc);
        classRegistered = true;
    }
    
    // Create dialog data
    ExportDlgData dlgData = {};
    dlgData.pMainWindow = this;
    dlgData.selectedFormat = ExportFormat::Markdown;
    dlgData.selectedScope = ExportScope::CurrentConversation;
    dlgData.isFormatTxtHover = false;
    dlgData.isFormatMdHover = false;
    dlgData.isFormatJsonHover = false;
    dlgData.isScopeCurrentHover = false;
    dlgData.isScopeAllHover = false;
    dlgData.isExportHover = false;
    dlgData.isCancelHover = false;
    dlgData.shouldClose = false;
    
    // Create dialog window
    HINSTANCE hInst = hInstance_ ? hInstance_ : GetModuleHandle(NULL);
    HWND hDlg = CreateWindowExW(
        WS_EX_DLGMODALFRAME | WS_EX_TOPMOST,
        L"SenAIExportDialog",
        UiStrings::Get(IDS_EXPORT_TITLE).c_str(),
        WS_POPUP | WS_CAPTION | WS_SYSMENU,
        CW_USEDEFAULT, CW_USEDEFAULT,
        500, 320,
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

bool MainWindow::ExportCurrentConversation(const std::wstring& filePath, ExportFormat format) {
    if (chatViewState_.messages.empty()) {
        ShowExportMessageDialog(UiStrings::Get(IDS_EXPORT_ERROR_NO_MESSAGES), false);
        return false;
    }
    
    return ExportService::ExportConversations(
        chatViewState_.messages,
        sessionId_,
        filePath,
        format,
        modelName_
    );
}

bool MainWindow::ExportAllConversations(const std::wstring& filePath, ExportFormat format) {
    return ExportService::ExportAllConversations(
        httpClient_,
        filePath,
        format,
        modelName_
    );
}