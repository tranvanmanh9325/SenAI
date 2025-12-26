#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <objbase.h>
#include "ui/MainWindow.h"

#pragma comment(lib, "ole32.lib")

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    // Enable visual styles
    SetProcessDPIAware();
    
    // Initialize COM (may be needed for some Windows features)
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
    
    MainWindow mainWindow;
    
    if (!mainWindow.Create(hInstance)) {
        DWORD error = GetLastError();
        wchar_t errorMsg[256];
        swprintf_s(errorMsg, UiStrings::Get(IDS_ERROR_WINDOW_CREATE_FAILED).c_str(), error);
        MessageBoxW(nullptr, errorMsg, UiStrings::Get(IDS_ERROR_DIALOG_TITLE).c_str(), MB_OK | MB_ICONERROR);
        CoUninitialize();
        return 1;
    }
    
    mainWindow.Show(nCmdShow);
    int result = mainWindow.Run();
    
    CoUninitialize();
    return result;
}