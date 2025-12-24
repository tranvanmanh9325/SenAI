#pragma once

#include <windows.h>
#include <string>

// Shared helper utilities for MainWindow logic files
std::string WideToUtf8(const std::wstring& wstr);
std::wstring Utf8ToWide(const std::string& str);
std::string GetEnvironmentVariableUtf8(const std::string& name);
std::string Trim(const std::string& str);
std::string GetExecutableDirectory();
std::string ReadEnvFile(const std::string& key);
std::wstring GetCurrentTimeW();
std::string UnescapeJsonString(const std::string& str);