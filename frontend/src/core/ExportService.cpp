#include "ExportService.h"
#include "MainWindowHelpers.h"
#include "JsonParser.h"
#include "HttpClient.h"
#include "../ui/MainWindow.h"
#include <fstream>
#include <sstream>
#include <iomanip>
#include <map>
#include <nlohmann/json.hpp>

bool ExportService::ExportConversations(
    const std::vector<ChatMessage>& messages,
    const std::string& sessionId,
    const std::wstring& filePath,
    ExportFormat format,
    const std::wstring& modelName) {
    
    if (messages.empty()) {
        return false;
    }
    
    std::wstring content;
    switch (format) {
        case ExportFormat::TXT:
            content = ConvertToTXT(messages, sessionId, modelName);
            break;
        case ExportFormat::Markdown:
            content = ConvertToMarkdown(messages, sessionId, modelName);
            break;
        case ExportFormat::JSON:
            content = ConvertToJSON(messages, sessionId, modelName);
            break;
        default:
            return false;
    }
    
    return WriteFile(filePath, content);
}

bool ExportService::ExportAllConversations(
    HttpClient& httpClient,
    const std::wstring& filePath,
    ExportFormat format,
    const std::wstring& modelName) {
    
    // Get all conversations from backend
    std::string conversationsJson = httpClient.getConversations("");
    
    if (conversationsJson.empty() || conversationsJson.find("Error:") == 0) {
        return false;
    }
    
    // Parse conversations
    std::vector<nlohmann::json> conversationsArray = JsonParser::ParseArray(conversationsJson);
    if (conversationsArray.empty()) {
        return false;
    }
    
    // Group by session_id and convert to ChatMessage format
    std::map<std::string, std::vector<ChatMessage>> sessionMessages;
    
    try {
        for (const auto& conv : conversationsArray) {
            if (!conv.is_object()) {
                continue;
            }
            
            std::string sessionId;
            if (conv.contains("session_id") && conv["session_id"].is_string()) {
                sessionId = conv["session_id"].get<std::string>();
            }
            
            if (sessionId.empty()) {
                sessionId = "unknown";
            }
            
            std::string userMsg;
            if (conv.contains("user_message") && conv["user_message"].is_string()) {
                userMsg = conv["user_message"].get<std::string>();
            }
            
            std::string aiMsg;
            if (conv.contains("ai_response") && conv["ai_response"].is_string()) {
                aiMsg = conv["ai_response"].get<std::string>();
            }
            
            std::string createdAt;
            if (conv.contains("created_at") && conv["created_at"].is_string()) {
                createdAt = conv["created_at"].get<std::string>();
            }
            
            // Create messages
            ChatMessage userMessage;
            userMessage.text = Utf8ToWide(userMsg);
            userMessage.type = MessageType::User;
            userMessage.isUser = true;
            userMessage.timestamp = Utf8ToWide(createdAt);
            
            sessionMessages[sessionId].push_back(userMessage);
            
            if (!aiMsg.empty()) {
                ChatMessage aiMessage;
                aiMessage.text = Utf8ToWide(aiMsg);
                aiMessage.type = MessageType::AI;
                aiMessage.isUser = false;
                aiMessage.timestamp = Utf8ToWide(createdAt);
                
                sessionMessages[sessionId].push_back(aiMessage);
            }
        }
    } catch (const std::exception& e) {
        return false;
    }
    
    // Convert to export format
    std::wstring content;
    
    if (format == ExportFormat::JSON) {
        // For JSON, create a structured format with all sessions
        nlohmann::json exportData;
        exportData["export_info"] = nlohmann::json::object();
        exportData["export_info"]["model"] = WideToUtf8(modelName);
        exportData["export_info"]["export_date"] = ""; // Will be set by system
        exportData["export_info"]["total_sessions"] = sessionMessages.size();
        exportData["conversations"] = nlohmann::json::array();
        
        for (const auto& pair : sessionMessages) {
            nlohmann::json sessionData;
            sessionData["session_id"] = pair.first;
            sessionData["messages"] = nlohmann::json::array();
            
            for (const auto& msg : pair.second) {
                nlohmann::json msgJson;
                msgJson["text"] = WideToUtf8(msg.text);
                msgJson["type"] = (msg.type == MessageType::User) ? "user" : "ai";
                msgJson["timestamp"] = WideToUtf8(msg.timestamp);
                if (msg.metadata.tokenUsage > 0) {
                    msgJson["metadata"] = nlohmann::json::object();
                    msgJson["metadata"]["token_usage"] = msg.metadata.tokenUsage;
                    msgJson["metadata"]["latency_ms"] = msg.metadata.latencyMs;
                    if (!msg.metadata.modelName.empty()) {
                        msgJson["metadata"]["model"] = WideToUtf8(msg.metadata.modelName);
                    }
                }
                sessionData["messages"].push_back(msgJson);
            }
            
            exportData["conversations"].push_back(sessionData);
        }
        
        content = Utf8ToWide(exportData.dump(2));
    } else {
        // For TXT and Markdown, combine all sessions
        std::wstringstream ss;
        
        if (format == ExportFormat::Markdown) {
            ss << L"# Tất cả cuộc trò chuyện\n\n";
            if (!modelName.empty()) {
                ss << L"**Model:** " << modelName << L"\n\n";
            }
            ss << L"---\n\n";
        } else {
            ss << L"TẤT CẢ CUỘC TRÒ CHUYỆN\n";
            ss << L"====================\n\n";
            if (!modelName.empty()) {
                ss << L"Model: " << modelName << L"\n\n";
            }
            ss << L"----------------------------------------\n\n";
        }
        
        int sessionNum = 1;
        for (const auto& pair : sessionMessages) {
            if (format == ExportFormat::Markdown) {
                ss << L"## Session " << sessionNum << L" (" << Utf8ToWide(pair.first) << L")\n\n";
            } else {
                ss << L"SESSION " << sessionNum << L" (" << Utf8ToWide(pair.first) << L")\n";
                ss << L"----------------------------------------\n\n";
            }
            
            std::wstring sessionContent;
            if (format == ExportFormat::Markdown) {
                sessionContent = ConvertToMarkdown(pair.second, pair.first, modelName);
                // Remove header from session content
                size_t pos = sessionContent.find(L"\n\n");
                if (pos != std::wstring::npos) {
                    sessionContent = sessionContent.substr(pos + 2);
                }
            } else {
                sessionContent = ConvertToTXT(pair.second, pair.first, modelName);
                // Remove header from session content
                size_t pos = sessionContent.find(L"\n\n");
                if (pos != std::wstring::npos) {
                    sessionContent = sessionContent.substr(pos + 2);
                }
            }
            
            ss << sessionContent;
            ss << L"\n\n";
            sessionNum++;
        }
        
        content = ss.str();
    }
    
    return WriteFile(filePath, content);
}

std::wstring ExportService::GetFileExtension(ExportFormat format) {
    switch (format) {
        case ExportFormat::TXT:
            return L".txt";
        case ExportFormat::Markdown:
            return L".md";
        case ExportFormat::JSON:
            return L".json";
        default:
            return L".txt";
    }
}

std::wstring ExportService::GetFormatFilter(ExportFormat format) {
    switch (format) {
        case ExportFormat::TXT:
            return L"Text Files (*.txt)\0*.txt\0";
        case ExportFormat::Markdown:
            return L"Markdown Files (*.md)\0*.md\0";
        case ExportFormat::JSON:
            return L"JSON Files (*.json)\0*.json\0";
        default:
            return L"All Files (*.*)\0*.*\0";
    }
}

std::wstring ExportService::GetAllFormatFilters() {
    return L"Text Files (*.txt)\0*.txt\0Markdown Files (*.md)\0*.md\0JSON Files (*.json)\0*.json\0All Files (*.*)\0*.*\0";
}

std::wstring ExportService::ConvertToTXT(
    const std::vector<ChatMessage>& messages,
    const std::string& sessionId,
    const std::wstring& modelName) {
    
    std::wstringstream ss;
    
    ss << L"CUỘC TRÒ CHUYỆN\n";
    ss << L"===============\n\n";
    
    if (!modelName.empty()) {
        ss << L"Model: " << modelName << L"\n";
    }
    ss << L"Session ID: " << Utf8ToWide(sessionId) << L"\n";
    ss << L"\n";
    ss << L"----------------------------------------\n\n";
    
    for (const auto& msg : messages) {
        std::wstring role = (msg.type == MessageType::User || msg.isUser) ? L"Bạn" : L"AI";
        ss << L"[" << role << L"] ";
        
        if (!msg.timestamp.empty()) {
            ss << L"(" << FormatTimestamp(msg.timestamp) << L") ";
        }
        
        ss << L"\n";
        ss << msg.text;
        ss << L"\n\n";
        
        // Add metadata if available
        if (msg.metadata.tokenUsage > 0 || msg.metadata.latencyMs > 0 || !msg.metadata.modelName.empty()) {
            ss << L"  [Metadata: ";
            bool hasMeta = false;
            if (msg.metadata.tokenUsage > 0) {
                ss << L"Tokens=" << msg.metadata.tokenUsage;
                hasMeta = true;
            }
            if (msg.metadata.latencyMs > 0) {
                if (hasMeta) ss << L", ";
                ss << L"Latency=" << msg.metadata.latencyMs << L"ms";
                hasMeta = true;
            }
            if (!msg.metadata.modelName.empty()) {
                if (hasMeta) ss << L", ";
                ss << L"Model=" << msg.metadata.modelName;
            }
            ss << L"]\n\n";
        }
    }
    
    return ss.str();
}

std::wstring ExportService::ConvertToMarkdown(
    const std::vector<ChatMessage>& messages,
    const std::string& sessionId,
    const std::wstring& modelName) {
    
    std::wstringstream ss;
    
    ss << L"# Cuộc trò chuyện\n\n";
    
    if (!modelName.empty()) {
        ss << L"**Model:** " << modelName << L"\n\n";
    }
    ss << L"**Session ID:** `" << Utf8ToWide(sessionId) << L"`\n\n";
    ss << L"---\n\n";
    
    for (const auto& msg : messages) {
        std::wstring role = (msg.type == MessageType::User || msg.isUser) ? L"**Bạn**" : L"**AI**";
        ss << role;
        
        if (!msg.timestamp.empty()) {
            ss << L" *(" << FormatTimestamp(msg.timestamp) << L")*";
        }
        
        ss << L"\n\n";
        
        // Escape markdown special characters in message text
        std::wstring escapedText = EscapeMarkdown(msg.text);
        ss << escapedText;
        ss << L"\n\n";
        
        // Add metadata if available
        if (msg.metadata.tokenUsage > 0 || msg.metadata.latencyMs > 0 || !msg.metadata.modelName.empty()) {
            ss << L"<small>";
            bool hasMeta = false;
            if (msg.metadata.tokenUsage > 0) {
                ss << L"Tokens: " << msg.metadata.tokenUsage;
                hasMeta = true;
            }
            if (msg.metadata.latencyMs > 0) {
                if (hasMeta) ss << L" | ";
                ss << L"Latency: " << msg.metadata.latencyMs << L"ms";
                hasMeta = true;
            }
            if (!msg.metadata.modelName.empty()) {
                if (hasMeta) ss << L" | ";
                ss << L"Model: " << msg.metadata.modelName;
            }
            ss << L"</small>\n\n";
        }
        
        ss << L"---\n\n";
    }
    
    return ss.str();
}

std::wstring ExportService::ConvertToJSON(
    const std::vector<ChatMessage>& messages,
    const std::string& sessionId,
    const std::wstring& modelName) {
    
    nlohmann::json exportData;
    exportData["export_info"] = nlohmann::json::object();
    exportData["export_info"]["model"] = WideToUtf8(modelName);
    exportData["export_info"]["session_id"] = sessionId;
    exportData["export_info"]["message_count"] = messages.size();
    
    exportData["messages"] = nlohmann::json::array();
    
    for (const auto& msg : messages) {
        nlohmann::json msgJson;
        msgJson["text"] = WideToUtf8(msg.text);
        msgJson["type"] = (msg.type == MessageType::User || msg.isUser) ? "user" : "ai";
        msgJson["timestamp"] = WideToUtf8(msg.timestamp);
        
        if (msg.metadata.tokenUsage > 0 || msg.metadata.latencyMs > 0 || !msg.metadata.modelName.empty()) {
            msgJson["metadata"] = nlohmann::json::object();
            if (msg.metadata.tokenUsage > 0) {
                msgJson["metadata"]["token_usage"] = msg.metadata.tokenUsage;
            }
            if (msg.metadata.latencyMs > 0) {
                msgJson["metadata"]["latency_ms"] = msg.metadata.latencyMs;
            }
            if (!msg.metadata.modelName.empty()) {
                msgJson["metadata"]["model"] = WideToUtf8(msg.metadata.modelName);
            }
        }
        
        exportData["messages"].push_back(msgJson);
    }
    
    return Utf8ToWide(exportData.dump(2));
}

bool ExportService::WriteFile(const std::wstring& filePath, const std::wstring& content) {
    // Convert wide string path to UTF-8 for file operations
    std::string utf8Path = WideToUtf8(filePath);
    std::ofstream file(utf8Path, std::ios::out | std::ios::binary);
    if (!file.is_open()) {
        return false;
    }
    
    // Convert wide string content to UTF-8
    std::string utf8Content = WideToUtf8(content);
    file.write(utf8Content.c_str(), utf8Content.length());
    file.close();
    
    return file.good();
}

std::wstring ExportService::FormatTimestamp(const std::wstring& timestamp) {
    // Format: "2024-01-01T12:00:00" -> "01/01/2024 12:00:00"
    if (timestamp.length() >= 19) {
        std::wstring year = timestamp.substr(0, 4);
        std::wstring month = timestamp.substr(5, 2);
        std::wstring day = timestamp.substr(8, 2);
        std::wstring time = timestamp.substr(11, 8);
        return day + L"/" + month + L"/" + year + L" " + time;
    }
    return timestamp;
}

std::wstring ExportService::EscapeMarkdown(const std::wstring& text) {
    std::wstring result;
    result.reserve(text.length() * 2);
    
    for (wchar_t c : text) {
        switch (c) {
            case L'*':
                result += L"\\*";
                break;
            case L'_':
                result += L"\\_";
                break;
            case L'`':
                result += L"\\`";
                break;
            case L'#':
                result += L"\\#";
                break;
            case L'[':
                result += L"\\[";
                break;
            case L']':
                result += L"\\]";
                break;
            case L'(':
                result += L"\\(";
                break;
            case L')':
                result += L"\\)";
                break;
            case L'!':
                result += L"\\!";
                break;
            default:
                result += c;
                break;
        }
    }
    
    return result;
}

std::wstring ExportService::EscapeJSON(const std::wstring& text) {
    // JSON escaping is handled by nlohmann::json library
    // This function is kept for potential future use
    return text;
}