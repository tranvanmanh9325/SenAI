#include <windows.h>
#include "MainWindow.h"
#include <string>
#include <algorithm>

// Input field and send button rendering split from MainWindowRender.cpp

void MainWindow::DrawInputField(HDC hdc) {
    // Glass input: outer glow + inner fill
    int radius = theme_.inputRadius;
    RECT outer = inputRect_;
    RECT inner = inputRect_;
    InflateRect(&inner, -2, -2);

    // Get edit control rect to exclude it from drawing
    RECT editRect = {0, 0, 0, 0};
    if (hChatInput_) {
        GetWindowRect(hChatInput_, &editRect);
        POINT pt1 = {editRect.left, editRect.top};
        POINT pt2 = {editRect.right, editRect.bottom};
        ScreenToClient(hwnd_, &pt1);
        ScreenToClient(hwnd_, &pt2);
        editRect.left = pt1.x;
        editRect.top = pt1.y;
        editRect.right = pt2.x;
        editRect.bottom = pt2.y;
    }

    // Outer stroke (cyan gradient simulated by two strokes)
    HPEN penOuter = CreatePen(PS_SOLID, 2, theme_.colorInputStroke);
    HBRUSH brushOuter = CreateSolidBrush(theme_.colorInputOuter);
    HGDIOBJ oldPen = SelectObject(hdc, penOuter);
    HGDIOBJ oldBrush = SelectObject(hdc, brushOuter);
    RoundRect(hdc, outer.left, outer.top, outer.right, outer.bottom, radius, radius);
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
    DeleteObject(brushOuter);
    DeleteObject(penOuter);

    // Inner fill - không cần exclude edit control nữa vì edit control tự vẽ background
    HPEN penInner = CreatePen(PS_SOLID, 1, theme_.colorInputInnerStroke);
    HBRUSH brushInner = CreateSolidBrush(theme_.colorInputInner);
    oldPen = SelectObject(hdc, penInner);
    oldBrush = SelectObject(hdc, brushInner);
    RoundRect(hdc, inner.left, inner.top, inner.right, inner.bottom, radius - 6, radius - 6);
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
    DeleteObject(brushInner);
    DeleteObject(penInner);

    // Placeholder - draw if edit control is empty and not focused
    // Draw placeholder directly over edit control area
    if (chatViewState_.showPlaceholder && hChatInput_) {
        HWND focusedWindow = GetFocus();
        if (focusedWindow != hChatInput_) {
            // Check if edit control is actually empty
            wchar_t buffer[1024] = {0};
            GetWindowTextW(hChatInput_, buffer, static_cast<int>(sizeof(buffer) / sizeof(wchar_t)));
            if (buffer[0] == L'\0') {
                SetBkMode(hdc, TRANSPARENT);
                SetTextColor(hdc, theme_.colorPlaceholder);
                SelectObject(hdc, hInputFont_->Get());

                // Use edit control rect if available, otherwise use inner rect
                RECT textRect;
                if (editRect.right > editRect.left && editRect.bottom > editRect.top) {
                    textRect = editRect;
                } else {
                    textRect = inner;
                }
                
                int inputPaddingX = 50;
                int buttonMarginRight = 12;
                int gapTextToButton = 10;
                int inputHeight = inner.bottom - inner.top;
                int buttonSize = inputHeight - 12;
                int buttonX = inner.right - buttonMarginRight - buttonSize;

                textRect.left = inner.left + inputPaddingX + 2;
                textRect.right = buttonX - gapTextToButton;

                const wchar_t* placeholder = UiStrings::Get(IDS_INPUT_PLACEHOLDER).c_str();
                DrawTextW(hdc, placeholder, -1, &textRect, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
            }
        }
    }

    // Vẽ nút gửi custom bên trong ô input (không dùng child window để tránh nhấp nháy)
    if (sendButtonRect_.right > sendButtonRect_.left &&
        sendButtonRect_.bottom > sendButtonRect_.top) {
        DrawSendButton(hdc, sendButtonRect_);
    }

    // Shortcut hint bên dưới ô input
    {
        SetBkMode(hdc, TRANSPARENT);
        SetTextColor(hdc, RGB(140, 150, 180));
        SelectObject(hdc, hInputFont_->Get());

        RECT hintRect = outer;
        hintRect.top = outer.bottom + 4;
        hintRect.bottom = hintRect.top + 24;

        const wchar_t* hintText = UiStrings::Get(IDS_INPUT_HINT).c_str();
        DrawTextW(hdc, hintText, -1, &hintRect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    }
}

void MainWindow::DrawSendButton(HDC hdc, const RECT& rc) {
    // Ensure square region (circle)
    int size = (std::min)(rc.right - rc.left, rc.bottom - rc.top);
    int cx = (rc.left + rc.right) / 2;
    int cy = (rc.top + rc.bottom) / 2;
    RECT circleRect;
    circleRect.left   = cx - size / 2;
    circleRect.top    = cy - size / 2;
    circleRect.right  = cx + size / 2;
    circleRect.bottom = cy + size / 2;

    // Use high-resolution rendering (3x) for smooth anti-aliasing
    const int scale = 3;
    int highResSize = size * scale;
    
    // Create high-resolution memory DC for smooth rendering
    HDC hdcMem = CreateCompatibleDC(hdc);
    HBITMAP hbmMem = CreateCompatibleBitmap(hdc, highResSize, highResSize);
    HBITMAP hbmOld = (HBITMAP)SelectObject(hdcMem, hbmMem);
    
    // Fill background với màu giống nền ô input để tránh "ô vuông" khác màu
    RECT memRect = {0, 0, highResSize, highResSize};
    HBRUSH bgBrush = CreateSolidBrush(theme_.colorInputInner);
    FillRect(hdcMem, &memRect, bgBrush);
    DeleteObject(bgBrush);
    
    // Enable high-quality rendering
    SetGraphicsMode(hdcMem, GM_ADVANCED);
    SetBkMode(hdcMem, TRANSPARENT);
    
    // Draw gradient circle (cyan -> violet)
    COLORREF outerColor = isSendButtonHover_ ? RGB(100, 235, 255) : RGB(74, 215, 255);
    COLORREF innerColor = isSendButtonHover_ ? RGB(184, 137, 255) : RGB(154, 107, 255);

    HBRUSH brush = CreateSolidBrush(outerColor);
    HPEN pen = CreatePen(PS_NULL, 0, outerColor); // No visible border
    HGDIOBJ oldBrush = SelectObject(hdcMem, brush);
    HGDIOBJ oldPen = SelectObject(hdcMem, pen);
    
    // Draw circle base
    Ellipse(hdcMem, 0, 0, highResSize, highResSize);
    SelectObject(hdcMem, oldBrush);
    SelectObject(hdcMem, oldPen);
    DeleteObject(brush);
    DeleteObject(pen);

    // Overlay inner circle with second color for subtle gradient
    int inset = highResSize / 8;
    brush = CreateSolidBrush(innerColor);
    pen = CreatePen(PS_NULL, 0, innerColor);
    oldBrush = SelectObject(hdcMem, brush);
    oldPen = SelectObject(hdcMem, pen);
    Ellipse(hdcMem, inset, inset, highResSize - inset, highResSize - inset);
    
    // Draw smooth arrow using polygon
    int arrowSize = (int)(highResSize * 0.35);
    int centerX = highResSize / 2;
    int centerY = highResSize / 2;
    
    // Create arrow as a filled polygon (pointing up)
    POINT arrowPoints[7];
    int arrowWidth = (int)(arrowSize * 0.6);
    int arrowHeight = arrowSize;
    
    // Arrow shape: triangle head + rectangular shaft
    arrowPoints[0].x = centerX;
    arrowPoints[0].y = centerY - arrowHeight / 2;
    arrowPoints[1].x = centerX - arrowWidth / 2;
    arrowPoints[1].y = centerY - arrowHeight / 2 + (int)(arrowHeight * 0.4);
    arrowPoints[2].x = centerX - (int)(arrowWidth * 0.25);
    arrowPoints[2].y = centerY - arrowHeight / 2 + (int)(arrowHeight * 0.4);
    arrowPoints[3].x = centerX - (int)(arrowWidth * 0.25);
    arrowPoints[3].y = centerY + arrowHeight / 2;
    arrowPoints[4].x = centerX + (int)(arrowWidth * 0.25);
    arrowPoints[4].y = centerY + arrowHeight / 2;
    arrowPoints[5].x = centerX + (int)(arrowWidth * 0.25);
    arrowPoints[5].y = centerY - arrowHeight / 2 + (int)(arrowHeight * 0.4);
    arrowPoints[6].x = centerX + arrowWidth / 2;
    arrowPoints[6].y = centerY - arrowHeight / 2 + (int)(arrowHeight * 0.4);
    
    // Draw dark arrow
    HBRUSH arrowBrush = CreateSolidBrush(RGB(0, 0, 0));
    HPEN arrowPen = CreatePen(PS_SOLID, 1, RGB(0, 0, 0));
    HGDIOBJ oldArrowBrush = SelectObject(hdcMem, arrowBrush);
    HGDIOBJ oldArrowPen = SelectObject(hdcMem, arrowPen);
    
    Polygon(hdcMem, arrowPoints, 7);
    
    // Cleanup arrow objects
    SelectObject(hdcMem, oldArrowBrush);
    SelectObject(hdcMem, oldArrowPen);
    DeleteObject(arrowBrush);
    DeleteObject(arrowPen);
    
    // Cleanup circle objects
    SelectObject(hdcMem, oldBrush);
    SelectObject(hdcMem, oldPen);
    DeleteObject(brush);
    DeleteObject(pen);
    
    // Scale down with high-quality interpolation for smooth anti-aliasing
    SetStretchBltMode(hdc, HALFTONE);
    SetBrushOrgEx(hdc, 0, 0, NULL);
    StretchBlt(hdc, circleRect.left, circleRect.top, size, size,
               hdcMem, 0, 0, highResSize, highResSize, SRCCOPY);
    
    // Cleanup memory DC
    SelectObject(hdcMem, hbmOld);
    DeleteObject(hbmMem);
    DeleteDC(hdcMem);
}