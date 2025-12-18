#include "HttpClient.h"
#include <windows.h>
#include <wininet.h>
#include <sstream>
#include <iomanip>

#pragma comment(lib, "wininet.lib")

HttpClient::HttpClient(const std::string& baseUrl) : baseUrl_(baseUrl) {}

std::string HttpClient::escapeJson(const std::string& str) {
    std::ostringstream o;
    for (size_t i = 0; i < str.length(); ++i) {
        switch (str[i]) {
            case '"': o << "\\\""; break;
            case '\\': o << "\\\\"; break;
            case '\b': o << "\\b"; break;
            case '\f': o << "\\f"; break;
            case '\n': o << "\\n"; break;
            case '\r': o << "\\r"; break;
            case '\t': o << "\\t"; break;
            default:
                if ('\x00' <= str[i] && str[i] <= '\x1f') {
                    o << "\\u" << std::hex << std::setw(4) << std::setfill('0') << (int)str[i];
                } else {
                    o << str[i];
                }
        }
    }
    return o.str();
}

std::string HttpClient::httpGet(const std::string& endpoint) {
    std::string url = baseUrl_ + endpoint;
    std::string result;
    
    HINTERNET hInternet = InternetOpenA("SenAI Client", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
    if (!hInternet) {
        return "Error: Failed to initialize WinInet";
    }
    
    HINTERNET hConnect = InternetOpenUrlA(hInternet, url.c_str(), NULL, 0, INTERNET_FLAG_RELOAD, 0);
    if (!hConnect) {
        InternetCloseHandle(hInternet);
        return "Error: Failed to open URL";
    }
    
    char buffer[4096];
    DWORD bytesRead;
    while (InternetReadFile(hConnect, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
        buffer[bytesRead] = '\0';
        result += buffer;
    }
    
    InternetCloseHandle(hConnect);
    InternetCloseHandle(hInternet);
    
    return result;
}

std::string HttpClient::httpPost(const std::string& endpoint, const std::string& jsonData) {
    std::string url = baseUrl_ + endpoint;
    std::string result;
    
    HINTERNET hInternet = InternetOpenA("SenAI Client", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
    if (!hInternet) {
        return "Error: Failed to initialize WinInet";
    }
    
    URL_COMPONENTSA urlComp;
    ZeroMemory(&urlComp, sizeof(urlComp));
    urlComp.dwStructSize = sizeof(urlComp);
    urlComp.dwHostNameLength = -1;
    urlComp.dwUrlPathLength = -1;
    
    char hostName[256];
    char urlPath[1024];
    urlComp.lpszHostName = hostName;
    urlComp.lpszUrlPath = urlPath;
    
    if (!InternetCrackUrlA(url.c_str(), url.length(), 0, &urlComp)) {
        InternetCloseHandle(hInternet);
        return "Error: Failed to parse URL";
    }
    
    HINTERNET hConnect = InternetConnectA(hInternet, hostName, urlComp.nPort, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
    if (!hConnect) {
        InternetCloseHandle(hInternet);
        return "Error: Failed to connect";
    }
    
    HINTERNET hRequest = HttpOpenRequestA(hConnect, "POST", urlPath, NULL, NULL, NULL, INTERNET_FLAG_RELOAD, 0);
    if (!hRequest) {
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        return "Error: Failed to open request";
    }
    
    std::string headers = "Content-Type: application/json\r\n";
    HttpAddRequestHeadersA(hRequest, headers.c_str(), headers.length(), HTTP_ADDREQ_FLAG_ADD);
    
    if (!HttpSendRequestA(hRequest, NULL, 0, (LPVOID)jsonData.c_str(), jsonData.length())) {
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        return "Error: Failed to send request";
    }
    
    char buffer[4096];
    DWORD bytesRead;
    while (InternetReadFile(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
        buffer[bytesRead] = '\0';
        result += buffer;
    }
    
    InternetCloseHandle(hRequest);
    InternetCloseHandle(hConnect);
    InternetCloseHandle(hInternet);
    
    return result;
}

std::string HttpClient::httpPut(const std::string& endpoint, const std::string& jsonData) {
    std::string url = baseUrl_ + endpoint;
    std::string result;
    
    HINTERNET hInternet = InternetOpenA("SenAI Client", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
    if (!hInternet) {
        return "Error: Failed to initialize WinInet";
    }
    
    URL_COMPONENTSA urlComp;
    ZeroMemory(&urlComp, sizeof(urlComp));
    urlComp.dwStructSize = sizeof(urlComp);
    urlComp.dwHostNameLength = -1;
    urlComp.dwUrlPathLength = -1;
    
    char hostName[256];
    char urlPath[1024];
    urlComp.lpszHostName = hostName;
    urlComp.lpszUrlPath = urlPath;
    
    if (!InternetCrackUrlA(url.c_str(), url.length(), 0, &urlComp)) {
        InternetCloseHandle(hInternet);
        return "Error: Failed to parse URL";
    }
    
    HINTERNET hConnect = InternetConnectA(hInternet, hostName, urlComp.nPort, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
    if (!hConnect) {
        InternetCloseHandle(hInternet);
        return "Error: Failed to connect";
    }
    
    HINTERNET hRequest = HttpOpenRequestA(hConnect, "PUT", urlPath, NULL, NULL, NULL, INTERNET_FLAG_RELOAD, 0);
    if (!hRequest) {
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        return "Error: Failed to open request";
    }
    
    std::string headers = "Content-Type: application/json\r\n";
    HttpAddRequestHeadersA(hRequest, headers.c_str(), headers.length(), HTTP_ADDREQ_FLAG_ADD);
    
    if (!HttpSendRequestA(hRequest, NULL, 0, (LPVOID)jsonData.c_str(), jsonData.length())) {
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        return "Error: Failed to send request";
    }
    
    char buffer[4096];
    DWORD bytesRead;
    while (InternetReadFile(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
        buffer[bytesRead] = '\0';
        result += buffer;
    }
    
    InternetCloseHandle(hRequest);
    InternetCloseHandle(hConnect);
    InternetCloseHandle(hInternet);
    
    return result;
}

std::string HttpClient::checkHealth() {
    return httpGet("/health");
}

std::string HttpClient::sendMessage(const std::string& message, const std::string& sessionId) {
    std::ostringstream json;
    json << "{\"user_message\":\"" << escapeJson(message) << "\"";
    if (!sessionId.empty()) {
        json << ",\"session_id\":\"" << escapeJson(sessionId) << "\"";
    }
    json << "}";
    return httpPost("/conversations", json.str());
}

std::string HttpClient::getConversations(const std::string& sessionId) {
    std::string endpoint = "/conversations";
    if (!sessionId.empty()) {
        endpoint += "?session_id=" + sessionId;
    }
    return httpGet(endpoint);
}

std::string HttpClient::createTask(const std::string& taskName, const std::string& description) {
    std::ostringstream json;
    json << "{\"task_name\":\"" << escapeJson(taskName) << "\"";
    if (!description.empty()) {
        json << ",\"description\":\"" << escapeJson(description) << "\"";
    }
    json << "}";
    return httpPost("/tasks", json.str());
}

std::string HttpClient::getTasks() {
    return httpGet("/tasks");
}

std::string HttpClient::getTask(int taskId) {
    return httpGet("/tasks/" + std::to_string(taskId));
}

std::string HttpClient::updateTask(int taskId, const std::string& status, const std::string& result) {
    std::string endpoint = "/tasks/" + std::to_string(taskId) + "?status=" + status;
    if (!result.empty()) {
        // URL encode result
        std::string encodedResult;
        for (char c : result) {
            if (c == ' ') encodedResult += "%20";
            else if (c == '&') encodedResult += "%26";
            else if (c == '=') encodedResult += "%3D";
            else if (c == '+') encodedResult += "%2B";
            else encodedResult += c;
        }
        endpoint += "&result=" + encodedResult;
    }
    return httpPut(endpoint, "");
}
