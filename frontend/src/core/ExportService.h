#pragma once
#include <string>
#include <vector>

// Forward declarations
class HttpClient;

// Forward declare types that are defined in MainWindow.h
enum class MessageType;
struct MessageMetadata;
struct ChatMessage;

// Export format types
enum class ExportFormat {
    TXT,
    Markdown,
    JSON
};

// Export scope
enum class ExportScope {
    CurrentConversation,
    AllConversations
};

// Export service to handle conversation exports
class ExportService {
public:
    // Export conversation(s) to file
    static bool ExportConversations(
        const std::vector<ChatMessage>& messages,
        const std::string& sessionId,
        const std::wstring& filePath,
        ExportFormat format,
        const std::wstring& modelName = L""
    );
    
    // Export all conversations from backend
    static bool ExportAllConversations(
        HttpClient& httpClient,
        const std::wstring& filePath,
        ExportFormat format,
        const std::wstring& modelName = L""
    );
    
    // Get file extension for format
    static std::wstring GetFileExtension(ExportFormat format);
    
    // Get format filter string for file dialog
    static std::wstring GetFormatFilter(ExportFormat format);
    
    // Get all format filters for file dialog
    static std::wstring GetAllFormatFilters();

private:
    // Format converters
    static std::wstring ConvertToTXT(
        const std::vector<ChatMessage>& messages,
        const std::string& sessionId,
        const std::wstring& modelName
    );
    
    static std::wstring ConvertToMarkdown(
        const std::vector<ChatMessage>& messages,
        const std::string& sessionId,
        const std::wstring& modelName
    );
    
    static std::wstring ConvertToJSON(
        const std::vector<ChatMessage>& messages,
        const std::string& sessionId,
        const std::wstring& modelName
    );
    
    // Helper to write file
    static bool WriteFile(const std::wstring& filePath, const std::wstring& content);
    
    // Helper to format timestamp
    static std::wstring FormatTimestamp(const std::wstring& timestamp);
    
    // Helper to escape markdown
    static std::wstring EscapeMarkdown(const std::wstring& text);
    
    // Helper to escape JSON
    static std::wstring EscapeJSON(const std::wstring& text);
};
