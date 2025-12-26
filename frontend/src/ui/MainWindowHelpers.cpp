#include "MainWindowHelpers.h"

#include <fstream>
#include <map>
#include <vector>

std::string WideToUtf8(const std::wstring& wstr) {
    if (wstr.empty()) return {};
    int sizeNeeded = WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), -1, nullptr, 0, nullptr, nullptr);
    if (sizeNeeded <= 0) return {};
    std::string result(sizeNeeded - 1, '\0'); // exclude terminating null
    WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), -1, result.data(), sizeNeeded - 1, nullptr, nullptr);
    return result;
}

std::wstring Utf8ToWide(const std::string& str) {
    if (str.empty()) return {};
    int sizeNeeded = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), -1, nullptr, 0);
    if (sizeNeeded <= 0) return {};
    std::wstring result(sizeNeeded - 1, L'\0'); // exclude terminating null
    MultiByteToWideChar(CP_UTF8, 0, str.c_str(), -1, result.data(), sizeNeeded - 1);
    return result;
}

std::string GetEnvironmentVariableUtf8(const std::string& name) {
    // Convert to wide string for Windows API
    std::wstring wname = Utf8ToWide(name);
    wchar_t* buffer = nullptr;
    size_t size = 0;
    if (_wgetenv_s(&size, nullptr, 0, wname.c_str()) == 0 && size > 0) {
        buffer = new wchar_t[size];
        if (_wgetenv_s(&size, buffer, size, wname.c_str()) == 0) {
            std::string result = WideToUtf8(std::wstring(buffer));
            delete[] buffer;
            return result;
        }
        delete[] buffer;
    }
    return "";
}

std::string Trim(const std::string& str) {
    size_t first = str.find_first_not_of(" \t\n\r");
    if (first == std::string::npos) return "";
    size_t last = str.find_last_not_of(" \t\n\r");
    return str.substr(first, (last - first + 1));
}

std::string GetExecutableDirectory() {
    char buffer[MAX_PATH];
    DWORD length = GetModuleFileNameA(NULL, buffer, MAX_PATH);
    if (length == 0) {
        return "";
    }
    std::string exePath(buffer);
    size_t lastSlash = exePath.find_last_of("\\/");
    if (lastSlash != std::string::npos) {
        return exePath.substr(0, lastSlash + 1);
    }
    return "";
}

std::string ReadEnvFile(const std::string& key) {
    // List of possible .env file locations
    std::vector<std::string> envPaths = {
        ".env",                                    // Current directory
        GetExecutableDirectory() + ".env",         // Executable directory
        GetExecutableDirectory() + "../.env",      // Parent of executable directory
        GetExecutableDirectory() + "../../.env",   // Two levels up (for build/bin/)
        GetExecutableDirectory() + "../../../.env" // Three levels up
    };

    for (const auto& envPath : envPaths) {
        std::ifstream file(envPath);
        if (!file.is_open()) {
            continue;
        }

        std::string line;
        while (std::getline(file, line)) {
            // Skip empty lines and comments
            line = Trim(line);
            if (line.empty() || line[0] == '#') {
                continue;
            }

            // Find the equals sign
            size_t pos = line.find('=');
            if (pos == std::string::npos) {
                continue;
            }

            std::string fileKey = Trim(line.substr(0, pos));
            std::string value = Trim(line.substr(pos + 1));

            // Remove quotes if present
            if (!value.empty() && ((value[0] == '"' && value.back() == '"') ||
                                   (value[0] == '\'' && value.back() == '\''))) {
                value = value.substr(1, value.length() - 2);
            }

            if (fileKey == key) {
                file.close();
                return value;
            }
        }

        file.close();
    }

    return "";
}

std::wstring GetCurrentTimeW() {
    SYSTEMTIME st;
    GetLocalTime(&st);
    wchar_t buf[16];
    swprintf_s(buf, L"%02d:%02d", st.wHour, st.wMinute);
    return std::wstring(buf);
}

std::string UnescapeJsonString(const std::string& str) {
    std::string result;
    bool escaped = false;
    for (size_t i = 0; i < str.length(); ++i) {
        char c = str[i];
        if (escaped) {
            switch (c) {
                case 'n': result += '\n'; break;
                case 'r': result += '\r'; break;
                case 't': result += '\t'; break;
                case '\\': result += '\\'; break;
                case '"': result += '"'; break;
                case '/': result += '/'; break;
                case 'b': result += '\b'; break;
                case 'f': result += '\f'; break;
                case 'u': {
                    // Handle \uXXXX unicode escape (skip for now)
                    if (i + 4 < str.length()) {
                        i += 4; // Skip 4 hex digits
                    }
                    break;
                }
                default: result += c; break;
            }
            escaped = false;
        } else {
            if (c == '\\') {
                escaped = true;
            } else {
                result += c;
            }
        }
    }
    return result;
}