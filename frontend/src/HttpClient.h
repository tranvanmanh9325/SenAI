#pragma once
#include <string>
#include <memory>

// Kết quả chuẩn hóa (hiện tại mới dùng cho logging, tương lai có thể dùng rộng hơn)
struct HttpResult {
    bool ok;
    std::string message;
};

class HttpClient {
public:
    HttpClient(const std::string& baseUrl = "http://localhost:8000", const std::string& apiKey = "");
    
    // Health check
    std::string checkHealth();
    
    // Conversation endpoints
    std::string sendMessage(const std::string& message, const std::string& sessionId = "");
    std::string getConversations(const std::string& sessionId = "");
    
    // Task endpoints
    std::string createTask(const std::string& taskName, const std::string& description = "");
    std::string getTasks();
    std::string getTask(int taskId);
    std::string updateTask(int taskId, const std::string& status, const std::string& result = "");
    
    void setBaseUrl(const std::string& url) { baseUrl_ = url; }
    std::string getBaseUrl() const { return baseUrl_; }
    void setApiKey(const std::string& apiKey) { apiKey_ = apiKey; }
    std::string getApiKey() const { return apiKey_; }

private:
    std::string baseUrl_;
    std::string apiKey_;
    std::string httpGet(const std::string& endpoint);
    std::string httpPost(const std::string& endpoint, const std::string& jsonData);
    std::string httpPut(const std::string& endpoint, const std::string& jsonData);
    std::string escapeJson(const std::string& str);
    std::string buildHeaders();
    std::string extractJsonField(const std::string& json, const std::string& fieldName);
};