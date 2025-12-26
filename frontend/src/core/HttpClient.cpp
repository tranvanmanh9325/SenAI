#include "HttpClient.h"
#include "JsonParser.h"
#include "ErrorHandler.h"
#include <windows.h>
#include <wininet.h>
#include <sstream>
#include <iomanip>
#include <fstream>
#include <chrono>
#include <ctime>
#include <nlohmann/json.hpp>

#pragma comment(lib, "wininet.lib")

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
    
    // Use retry logic for GET requests
    return ErrorHandler::GetInstance().RetryOperationWithResult(
        [this, &url]() -> std::string {
            return httpGetInternal(url);
        },
        3,  // max retries
        1000,  // 1 second delay
        "GET request failed for " + url
    );
}

std::string HttpClient::httpGetInternal(const std::string& url) {
    std::string result;
    
    HINTERNET hInternet = InternetOpenA("SenAI Client", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
    if (!hInternet) {
        ErrorHandler::GetInstance().LogSystemError(
            "Failed to initialize WinInet for GET " + url, "HttpClient::httpGetInternal");
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
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            "Failed to parse URL for GET: " + url, "HttpClient::httpGetInternal");
        return "Error: Failed to parse URL";
    }
    
    HINTERNET hConnect = InternetConnectA(hInternet, hostName, urlComp.nPort, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
    if (!hConnect) {
        InternetCloseHandle(hInternet);
        DWORD error = GetLastError();
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            "Failed to connect for GET " + url + " (Error: " + std::to_string(error) + ")", 
            "HttpClient::httpGetInternal");
        return "Error: Failed to connect";
    }
    
    HINTERNET hRequest = HttpOpenRequestA(hConnect, "GET", urlPath, NULL, NULL, NULL, INTERNET_FLAG_RELOAD, 0);
    if (!hRequest) {
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        ErrorHandler::GetInstance().LogSystemError(
            "Failed to open GET request for " + url, "HttpClient::httpGetInternal");
        return "Error: Failed to open request";
    }
    
    // Add headers including API key if available
    std::string headers = buildHeaders();
    if (!headers.empty()) {
        HttpAddRequestHeadersA(hRequest, headers.c_str(), headers.length(), HTTP_ADDREQ_FLAG_ADD);
    }
    
    // Set timeout (30 seconds)
    DWORD timeout = 30000;
    InternetSetOptionA(hRequest, INTERNET_OPTION_SEND_TIMEOUT, &timeout, sizeof(timeout));
    InternetSetOptionA(hRequest, INTERNET_OPTION_RECEIVE_TIMEOUT, &timeout, sizeof(timeout));
    
    if (!HttpSendRequestA(hRequest, NULL, 0, NULL, 0)) {
        DWORD error = GetLastError();
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        
        std::string errorMsg = "Failed to send GET request for " + url;
        if (error == ERROR_INTERNET_TIMEOUT) {
            errorMsg += " (Timeout)";
        }
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            errorMsg + " (Error: " + std::to_string(error) + ")", "HttpClient::httpGetInternal");
        return "Error: Failed to send request";
    }
    
    // Check HTTP status code
    DWORD statusCode = 0;
    DWORD statusCodeSize = sizeof(statusCode);
    if (HttpQueryInfoA(hRequest, HTTP_QUERY_STATUS_CODE | HTTP_QUERY_FLAG_NUMBER, 
                      &statusCode, &statusCodeSize, NULL)) {
        if (statusCode >= 400) {
            InternetCloseHandle(hRequest);
            InternetCloseHandle(hConnect);
            InternetCloseHandle(hInternet);
            ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
                "HTTP error " + std::to_string(statusCode) + " for GET " + url, 
                "HttpClient::httpGetInternal");
            return "Error: HTTP " + std::to_string(statusCode);
        }
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
    
    // Use retry logic for POST requests
    return ErrorHandler::GetInstance().RetryOperationWithResult(
        [this, &url, &jsonData]() -> std::string {
            return httpPostInternal(url, jsonData);
        },
        3,  // max retries
        1000,  // 1 second delay
        "POST request failed for " + url
    );
}

std::string HttpClient::httpPostInternal(const std::string& url, const std::string& jsonData) {
    std::string result;
    
    HINTERNET hInternet = InternetOpenA("SenAI Client", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
    if (!hInternet) {
        ErrorHandler::GetInstance().LogSystemError(
            "Failed to initialize WinInet for POST " + url, "HttpClient::httpPostInternal");
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
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            "Failed to parse URL for POST: " + url, "HttpClient::httpPostInternal");
        return "Error: Failed to parse URL";
    }
    
    HINTERNET hConnect = InternetConnectA(hInternet, hostName, urlComp.nPort, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
    if (!hConnect) {
        InternetCloseHandle(hInternet);
        DWORD error = GetLastError();
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            "Failed to connect for POST " + url + " (Error: " + std::to_string(error) + ")", 
            "HttpClient::httpPostInternal");
        return "Error: Failed to connect";
    }
    
    HINTERNET hRequest = HttpOpenRequestA(hConnect, "POST", urlPath, NULL, NULL, NULL, INTERNET_FLAG_RELOAD, 0);
    if (!hRequest) {
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        ErrorHandler::GetInstance().LogSystemError(
            "Failed to open POST request for " + url, "HttpClient::httpPostInternal");
        return "Error: Failed to open request";
    }
    
    std::string headers = buildHeaders();
    HttpAddRequestHeadersA(hRequest, headers.c_str(), headers.length(), HTTP_ADDREQ_FLAG_ADD);
    
    // Set timeout (60 seconds for POST as it may take longer)
    DWORD timeout = 60000;
    InternetSetOptionA(hRequest, INTERNET_OPTION_SEND_TIMEOUT, &timeout, sizeof(timeout));
    InternetSetOptionA(hRequest, INTERNET_OPTION_RECEIVE_TIMEOUT, &timeout, sizeof(timeout));
    
    if (!HttpSendRequestA(hRequest, NULL, 0, (LPVOID)jsonData.c_str(), jsonData.length())) {
        DWORD error = GetLastError();
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        
        std::string errorMsg = "Failed to send POST request for " + url;
        if (error == ERROR_INTERNET_TIMEOUT) {
            errorMsg += " (Timeout)";
        }
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            errorMsg + " (Error: " + std::to_string(error) + ")", "HttpClient::httpPostInternal");
        return "Error: Failed to send request";
    }
    
    // Check HTTP status code
    DWORD statusCode = 0;
    DWORD statusCodeSize = sizeof(statusCode);
    if (HttpQueryInfoA(hRequest, HTTP_QUERY_STATUS_CODE | HTTP_QUERY_FLAG_NUMBER, 
                      &statusCode, &statusCodeSize, NULL)) {
        if (statusCode >= 400) {
            InternetCloseHandle(hRequest);
            InternetCloseHandle(hConnect);
            InternetCloseHandle(hInternet);
            ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
                "HTTP error " + std::to_string(statusCode) + " for POST " + url, 
                "HttpClient::httpPostInternal");
            return "Error: HTTP " + std::to_string(statusCode);
        }
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
    
    // Use retry logic for PUT requests
    return ErrorHandler::GetInstance().RetryOperationWithResult(
        [this, &url, &jsonData]() -> std::string {
            return httpPutInternal(url, jsonData);
        },
        3,  // max retries
        1000,  // 1 second delay
        "PUT request failed for " + url
    );
}

std::string HttpClient::httpPutInternal(const std::string& url, const std::string& jsonData) {
    std::string result;
    
    HINTERNET hInternet = InternetOpenA("SenAI Client", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
    if (!hInternet) {
        ErrorHandler::GetInstance().LogSystemError(
            "Failed to initialize WinInet for PUT " + url, "HttpClient::httpPutInternal");
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
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            "Failed to parse URL for PUT: " + url, "HttpClient::httpPutInternal");
        return "Error: Failed to parse URL";
    }
    
    HINTERNET hConnect = InternetConnectA(hInternet, hostName, urlComp.nPort, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
    if (!hConnect) {
        InternetCloseHandle(hInternet);
        DWORD error = GetLastError();
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            "Failed to connect for PUT " + url + " (Error: " + std::to_string(error) + ")", 
            "HttpClient::httpPutInternal");
        return "Error: Failed to connect";
    }
    
    HINTERNET hRequest = HttpOpenRequestA(hConnect, "PUT", urlPath, NULL, NULL, NULL, INTERNET_FLAG_RELOAD, 0);
    if (!hRequest) {
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        ErrorHandler::GetInstance().LogSystemError(
            "Failed to open PUT request for " + url, "HttpClient::httpPutInternal");
        return "Error: Failed to open request";
    }
    
    std::string headers = buildHeaders();
    HttpAddRequestHeadersA(hRequest, headers.c_str(), headers.length(), HTTP_ADDREQ_FLAG_ADD);
    
    // Set timeout (30 seconds)
    DWORD timeout = 30000;
    InternetSetOptionA(hRequest, INTERNET_OPTION_SEND_TIMEOUT, &timeout, sizeof(timeout));
    InternetSetOptionA(hRequest, INTERNET_OPTION_RECEIVE_TIMEOUT, &timeout, sizeof(timeout));
    
    if (!HttpSendRequestA(hRequest, NULL, 0, (LPVOID)jsonData.c_str(), jsonData.length())) {
        DWORD error = GetLastError();
        InternetCloseHandle(hRequest);
        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);
        
        std::string errorMsg = "Failed to send PUT request for " + url;
        if (error == ERROR_INTERNET_TIMEOUT) {
            errorMsg += " (Timeout)";
        }
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            errorMsg + " (Error: " + std::to_string(error) + ")", "HttpClient::httpPutInternal");
        return "Error: Failed to send request";
    }
    
    // Check HTTP status code
    DWORD statusCode = 0;
    DWORD statusCodeSize = sizeof(statusCode);
    if (HttpQueryInfoA(hRequest, HTTP_QUERY_STATUS_CODE | HTTP_QUERY_FLAG_NUMBER, 
                      &statusCode, &statusCodeSize, NULL)) {
        if (statusCode >= 400) {
            InternetCloseHandle(hRequest);
            InternetCloseHandle(hConnect);
            InternetCloseHandle(hInternet);
            ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
                "HTTP error " + std::to_string(statusCode) + " for PUT " + url, 
                "HttpClient::httpPutInternal");
            return "Error: HTTP " + std::to_string(statusCode);
        }
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
            ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
                "Failed to send message: " + response, "HttpClient::sendMessage");
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
            ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
                "Backend returned error detail: " + errorDetail, "HttpClient::sendMessage");
            return "Error: " + errorDetail;
        }
        
        // Nếu vẫn không tìm thấy, trả về toàn bộ response để debug (fallback)
        // Trong production, có thể muốn return empty string hoặc error message
        return response;
    } catch (const std::exception& e) {
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            "Exception in sendMessage: " + std::string(e.what()), "HttpClient::sendMessage");
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
        std::string result = httpPost("/tasks", json.dump());
        
        if (result.find("Error:") == 0) {
            ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
                "Failed to create task: " + result, "HttpClient::createTask");
        }
        
        return result;
    } catch (const std::exception& e) {
        ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error,
            "Exception in createTask: " + std::string(e.what()), "HttpClient::createTask");
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