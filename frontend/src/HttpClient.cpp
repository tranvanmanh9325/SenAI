#include "HttpClient.h"
#include "JsonParser.h"
#include <windows.h>
#include <wininet.h>
#include <sstream>
#include <iomanip>
#include <fstream>
#include <chrono>
#include <ctime>
#include <nlohmann/json.hpp>

#pragma comment(lib, "wininet.lib")

namespace {
    // Ghi log lỗi HTTP đơn giản ra file SenAI_frontend.log (cùng thư mục exe)
    void LogHttpError(const std::string& message) {
        char path[MAX_PATH] = {0};
        if (GetModuleFileNameA(NULL, path, MAX_PATH) == 0) {
            return;
        }
        std::string exePath(path);
        size_t pos = exePath.find_last_of("\\/");
        std::string dir = (pos == std::string::npos) ? "" : exePath.substr(0, pos + 1);
        std::string logPath = dir + "SenAI_frontend.log";

        std::ofstream out(logPath, std::ios::app);
        if (!out.is_open()) return;

        auto now = std::chrono::system_clock::now();
        std::time_t t = std::chrono::system_clock::to_time_t(now);
        out << "[HTTP] " << std::put_time(std::localtime(&t), "%Y-%m-%d %H:%M:%S")
            << " - " << message << "\n";
    }
}

HttpClient::HttpClient(const std::string& baseUrl, const std::string& apiKey) 
    : baseUrl_(baseUrl), apiKey_(apiKey) {}


std::string HttpClient::buildHeaders() {
    std::ostringstream headers;
    headers << "Content-Type: application/json\r\n";
    if (!apiKey_.empty()) {
        headers << "X-API-Key: " << apiKey_ << "\r\n";
    }
    return headers.str();
}

std::string HttpClient::httpGet(const std::string& endpoint) {
    std::string url = baseUrl_ + endpoint;
    std::string result;
    
    HINTERNET hInternet = InternetOpenA("SenAI Client", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
    if (!hInternet) {
        LogHttpError("Failed to initialize WinInet for GET " + url);
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
        LogHttpError("Failed to parse URL for GET: " + url);
        return "Error: Failed to parse URL";
    }
    
    HINTERNET hConnect = InternetConnectA(hInternet, hostName, urlComp.nPort, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
    if (!hConnect) {
        InternetCloseHandle(hInternet);
        LogHttpError("Failed to connect for GET " + url);
        return "Error: Failed to connect";
    }
    
    HINTERNET hRequest = HttpOpenRequestA(hConnect, "GET", urlPath, NULL, NULL, NULL, INTERNET_FLAG_RELOAD, 0);
    if (!hRequest) {
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        LogHttpError("Failed to open GET request for " + url);
        return "Error: Failed to open request";
    }
    
    // Add headers including API key if available
    std::string headers = buildHeaders();
    if (!headers.empty()) {
        HttpAddRequestHeadersA(hRequest, headers.c_str(), headers.length(), HTTP_ADDREQ_FLAG_ADD);
    }
    
    if (!HttpSendRequestA(hRequest, NULL, 0, NULL, 0)) {
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        LogHttpError("Failed to send GET request for " + url);
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

std::string HttpClient::httpPost(const std::string& endpoint, const std::string& jsonData) {
    std::string url = baseUrl_ + endpoint;
    std::string result;
    
    HINTERNET hInternet = InternetOpenA("SenAI Client", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
    if (!hInternet) {
        LogHttpError("Failed to initialize WinInet for POST " + url);
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
        LogHttpError("Failed to parse URL for POST: " + url);
        return "Error: Failed to parse URL";
    }
    
    HINTERNET hConnect = InternetConnectA(hInternet, hostName, urlComp.nPort, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
    if (!hConnect) {
        InternetCloseHandle(hInternet);
        LogHttpError("Failed to connect for POST " + url);
        return "Error: Failed to connect";
    }
    
    HINTERNET hRequest = HttpOpenRequestA(hConnect, "POST", urlPath, NULL, NULL, NULL, INTERNET_FLAG_RELOAD, 0);
    if (!hRequest) {
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        LogHttpError("Failed to open POST request for " + url);
        return "Error: Failed to open request";
    }
    
    std::string headers = buildHeaders();
    HttpAddRequestHeadersA(hRequest, headers.c_str(), headers.length(), HTTP_ADDREQ_FLAG_ADD);
    
    if (!HttpSendRequestA(hRequest, NULL, 0, (LPVOID)jsonData.c_str(), jsonData.length())) {
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        LogHttpError("Failed to send POST request for " + url);
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
        LogHttpError("Failed to initialize WinInet for PUT " + url);
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
        LogHttpError("Failed to parse URL for PUT: " + url);
        return "Error: Failed to parse URL";
    }
    
    HINTERNET hConnect = InternetConnectA(hInternet, hostName, urlComp.nPort, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
    if (!hConnect) {
        InternetCloseHandle(hInternet);
        LogHttpError("Failed to connect for PUT " + url);
        return "Error: Failed to connect";
    }
    
    HINTERNET hRequest = HttpOpenRequestA(hConnect, "PUT", urlPath, NULL, NULL, NULL, INTERNET_FLAG_RELOAD, 0);
    if (!hRequest) {
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        LogHttpError("Failed to open PUT request for " + url);
        return "Error: Failed to open request";
    }
    
    std::string headers = buildHeaders();
    HttpAddRequestHeadersA(hRequest, headers.c_str(), headers.length(), HTTP_ADDREQ_FLAG_ADD);
    
    if (!HttpSendRequestA(hRequest, NULL, 0, (LPVOID)jsonData.c_str(), jsonData.length())) {
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        LogHttpError("Failed to send PUT request for " + url);
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
    try {
        // Build JSON using nlohmann/json for proper escaping
        nlohmann::json json;
        json["user_message"] = message;
        if (!sessionId.empty()) {
            json["session_id"] = sessionId;
        }
        std::string jsonStr = json.dump();
        
        std::string response = httpPost("/conversations", jsonStr);
        
        // Check if response is an error
        if (response.find("Error:") == 0) {
            return response; // Return error message as-is
        }
        
        // Extract ai_response từ JSON response using JsonParser
        std::string aiResponse = JsonParser::GetString(response, "ai_response");
        if (!aiResponse.empty()) {
            return aiResponse;
        }
        
        // Nếu không tìm thấy ai_response, kiểm tra xem có phải là error response không
        std::string errorDetail = JsonParser::GetString(response, "detail");
        if (!errorDetail.empty()) {
            return "Error: " + errorDetail;
        }
        
        // Nếu vẫn không tìm thấy, trả về toàn bộ response để debug (fallback)
        // Trong production, có thể muốn return empty string hoặc error message
        return response;
    } catch (const std::exception& e) {
        return "Error: Failed to send message - " + std::string(e.what());
    }
}

std::string HttpClient::getConversations(const std::string& sessionId) {
    std::string endpoint = "/conversations";
    if (!sessionId.empty()) {
        endpoint += "?session_id=" + sessionId;
    }
    return httpGet(endpoint);
}

std::string HttpClient::createTask(const std::string& taskName, const std::string& description) {
    try {
        nlohmann::json json;
        json["task_name"] = taskName;
        if (!description.empty()) {
            json["description"] = description;
        }
        return httpPost("/tasks", json.dump());
    } catch (const std::exception& e) {
        return "Error: Failed to create task - " + std::string(e.what());
    }
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