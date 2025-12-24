#pragma once
#include <string>

// Simple UI strings for future i18n support
struct UiStrings {
    std::wstring appTitle       = L"SenAI";
    std::wstring heroTitle      = L"Hôm nay bạn có ý tưởng gì?";
    std::wstring heroSubtitle   = L"Tiểu Bối sẵn sàng giúp bạn.";
    std::wstring placeholder    = L"Hỏi bất kỳ điều gì";
    std::wstring sessionLabel   = L"Session: ";
    std::wstring modelLabel     = L"Model: ";
    std::wstring statusOnline   = L"Online";
    std::wstring statusChecking = L"Đang kết nối…";
    std::wstring statusOffline  = L"Offline";
};

