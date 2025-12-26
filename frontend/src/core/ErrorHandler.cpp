#include "ErrorHandler.h"
#include <windows.h>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <ctime>
#include <algorithm>

ErrorHandler& ErrorHandler::GetInstance() {
    static ErrorHandler instance;
    return instance;
}

ErrorHandler::ErrorHandler() : logFilePathInitialized_(false) {
    // Initialize log file path
    GetLogFilePathInternal();
}

std::string ErrorHandler::GetLogFilePathInternal() const {
    if (!logFilePathInitialized_) {
        char path[MAX_PATH] = {0};
        if (GetModuleFileNameA(NULL, path, MAX_PATH) != 0) {
            std::string exePath(path);
            size_t pos = exePath.find_last_of("\\/");
            std::string dir = (pos == std::string::npos) ? "" : exePath.substr(0, pos + 1);
            const_cast<ErrorHandler*>(this)->logFilePath_ = dir + "SenAI_frontend.log";
            const_cast<ErrorHandler*>(this)->logFilePathInitialized_ = true;
        } else {
            const_cast<ErrorHandler*>(this)->logFilePath_ = "SenAI_frontend.log";
            const_cast<ErrorHandler*>(this)->logFilePathInitialized_ = true;
        }
    }
    return logFilePath_;
}

std::string ErrorHandler::GetLogFilePath() const {
    return GetLogFilePathInternal();
}

std::string ErrorHandler::GetTimestamp() {
    auto now = std::chrono::system_clock::now();
    std::time_t t = std::chrono::system_clock::to_time_t(now);
    std::ostringstream oss;
    oss << std::put_time(std::localtime(&t), "%Y-%m-%d %H:%M:%S");
    
    // Add milliseconds
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()) % 1000;
    oss << "." << std::setfill('0') << std::setw(3) << ms.count();
    
    return oss.str();
}

std::string ErrorHandler::GetCategoryString(ErrorCategory category) {
    switch (category) {
        case ErrorCategory::Network: return "NETWORK";
        case ErrorCategory::Json: return "JSON";
        case ErrorCategory::System: return "SYSTEM";
        case ErrorCategory::Validation: return "VALIDATION";
        case ErrorCategory::Unknown: return "UNKNOWN";
        default: return "UNKNOWN";
    }
}

std::string ErrorHandler::GetSeverityString(ErrorSeverity severity) {
    switch (severity) {
        case ErrorSeverity::Info: return "INFO";
        case ErrorSeverity::Warning: return "WARN";
        case ErrorSeverity::Error: return "ERROR";
        case ErrorSeverity::Critical: return "CRITICAL";
        default: return "UNKNOWN";
    }
}

void ErrorHandler::WriteToLog(const std::string& logEntry) {
    std::ofstream out(GetLogFilePathInternal(), std::ios::app);
    if (out.is_open()) {
        out << logEntry << "\n";
        out.flush();
    }
}

void ErrorHandler::LogError(const ErrorInfo& error) {
    std::ostringstream logEntry;
    logEntry << "[" << GetTimestamp() << "] "
             << "[" << GetSeverityString(error.severity) << "] "
             << "[" << GetCategoryString(error.category) << "] ";
    
    if (!error.context.empty()) {
        logEntry << "[" << error.context << "] ";
    }
    
    logEntry << error.message;
    
    if (!error.technicalDetails.empty()) {
        logEntry << " | Technical: " << error.technicalDetails;
    }
    
    if (error.systemErrorCode != 0) {
        logEntry << " | System Error Code: " << error.systemErrorCode;
        
        // Get Windows error message
        LPSTR messageBuffer = nullptr;
        size_t size = FormatMessageA(
            FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
            NULL, error.systemErrorCode, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
            (LPSTR)&messageBuffer, 0, NULL);
        
        if (messageBuffer) {
            std::string sysMsg(messageBuffer);
            // Remove trailing newlines
            sysMsg.erase(std::find_if(sysMsg.rbegin(), sysMsg.rend(),
                [](unsigned char ch) { return ch != '\n' && ch != '\r'; }).base(), sysMsg.end());
            logEntry << " (" << sysMsg << ")";
            LocalFree(messageBuffer);
        }
    }
    
    WriteToLog(logEntry.str());
    
    // Call custom callback if set
    if (errorCallback_) {
        errorCallback_(error);
    }
}

void ErrorHandler::LogError(ErrorCategory category, ErrorSeverity severity,
                            const std::string& message, const std::string& context) {
    ErrorInfo error(category, severity, message);
    error.context = context;
    LogError(error);
}

void ErrorHandler::LogSystemError(const std::string& message, const std::string& context) {
    DWORD errorCode = GetLastError();
    ErrorInfo error(ErrorCategory::System, ErrorSeverity::Error, message);
    error.context = context;
    error.systemErrorCode = errorCode;
    error.technicalDetails = "Windows system error";
    LogError(error);
}

void ErrorHandler::ShowUserError(const std::string& title, const std::string& message, HWND parent) {
    // Convert to wide string for MessageBox
    int titleLen = MultiByteToWideChar(CP_UTF8, 0, title.c_str(), -1, NULL, 0);
    int msgLen = MultiByteToWideChar(CP_UTF8, 0, message.c_str(), -1, NULL, 0);
    
    if (titleLen > 0 && msgLen > 0) {
        std::vector<wchar_t> titleBuf(titleLen);
        std::vector<wchar_t> msgBuf(msgLen);
        
        MultiByteToWideChar(CP_UTF8, 0, title.c_str(), -1, titleBuf.data(), titleLen);
        MultiByteToWideChar(CP_UTF8, 0, message.c_str(), -1, msgBuf.data(), msgLen);
        
        MessageBoxW(parent, msgBuf.data(), titleBuf.data(), MB_OK | MB_ICONERROR);
    } else {
        // Fallback to ASCII
        MessageBoxA(parent, message.c_str(), title.c_str(), MB_OK | MB_ICONERROR);
    }
}

void ErrorHandler::ShowUserError(const std::wstring& title, const std::wstring& message, HWND parent) {
    MessageBoxW(parent, message.c_str(), title.c_str(), MB_OK | MB_ICONERROR);
}

std::wstring ErrorHandler::GetUserFriendlyMessage(const ErrorInfo& error) {
    std::wstring userMessage;
    
    switch (error.category) {
        case ErrorCategory::Network: {
            std::string lowerMsg = error.message;
            std::transform(lowerMsg.begin(), lowerMsg.end(), lowerMsg.begin(), ::tolower);
            
            if (lowerMsg.find("timeout") != std::string::npos || 
                lowerMsg.find("timed out") != std::string::npos) {
                // Convert to wide string
                std::string msg = "Yêu cầu đến server mất quá nhiều thời gian. Vui lòng kiểm tra kết nối mạng hoặc thử lại sau.";
                int len = MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, NULL, 0);
                if (len > 0) {
                    std::vector<wchar_t> buf(len);
                    MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, buf.data(), len);
                    userMessage = buf.data();
                }
            } else if (lowerMsg.find("connect") != std::string::npos || 
                      lowerMsg.find("failed to connect") != std::string::npos) {
                std::string msg = "Không thể kết nối đến server. Vui lòng kiểm tra kết nối mạng và địa chỉ server.";
                int len = MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, NULL, 0);
                if (len > 0) {
                    std::vector<wchar_t> buf(len);
                    MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, buf.data(), len);
                    userMessage = buf.data();
                }
            } else {
                std::string msg = "Đã xảy ra lỗi khi gọi backend. Bạn hãy thử lại sau hoặc kiểm tra server.";
                int len = MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, NULL, 0);
                if (len > 0) {
                    std::vector<wchar_t> buf(len);
                    MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, buf.data(), len);
                    userMessage = buf.data();
                }
            }
            break;
        }
        case ErrorCategory::Json: {
            std::string msg = "Lỗi khi xử lý dữ liệu từ server. Vui lòng thử lại.";
            int len = MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, NULL, 0);
            if (len > 0) {
                std::vector<wchar_t> buf(len);
                MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, buf.data(), len);
                userMessage = buf.data();
            }
            break;
        }
        case ErrorCategory::System: {
            std::string msg = "Đã xảy ra lỗi hệ thống. Vui lòng thử lại hoặc khởi động lại ứng dụng.";
            int len = MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, NULL, 0);
            if (len > 0) {
                std::vector<wchar_t> buf(len);
                MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, buf.data(), len);
                userMessage = buf.data();
            }
            break;
        }
        default: {
            std::string msg = "Đã xảy ra lỗi không xác định. Vui lòng thử lại.";
            int len = MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, NULL, 0);
            if (len > 0) {
                std::vector<wchar_t> buf(len);
                MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, buf.data(), len);
                userMessage = buf.data();
            }
            break;
        }
    }
    
    // Add technical details if available (for advanced users)
    if (!error.technicalDetails.empty() && error.severity == ErrorSeverity::Error) {
        std::string detailMsg = "\r\nChi tiết kỹ thuật: " + error.technicalDetails;
        int len = MultiByteToWideChar(CP_UTF8, 0, detailMsg.c_str(), -1, NULL, 0);
        if (len > 0) {
            std::vector<wchar_t> buf(len);
            MultiByteToWideChar(CP_UTF8, 0, detailMsg.c_str(), -1, buf.data(), len);
            userMessage += L"\r\n";
            userMessage += buf.data();
        }
    }
    
    return userMessage;
}

bool ErrorHandler::IsRetryableError(const std::string& errorMessage) const {
    std::string lower = errorMessage;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
    
    // Check for retryable error patterns
    return lower.find("timeout") != std::string::npos ||
           lower.find("timed out") != std::string::npos ||
           lower.find("connection") != std::string::npos ||
           lower.find("network") != std::string::npos ||
           lower.find("failed to connect") != std::string::npos ||
           lower.find("temporary") != std::string::npos ||
           lower.find("503") != std::string::npos ||  // Service Unavailable
           lower.find("502") != std::string::npos ||  // Bad Gateway
           lower.find("504") != std::string::npos;    // Gateway Timeout
}

bool ErrorHandler::RetryOperation(std::function<bool()> operation,
                                  int maxRetries,
                                  int retryDelayMs,
                                  const std::string& errorMessage) {
    for (int attempt = 0; attempt <= maxRetries; ++attempt) {
        if (operation()) {
            if (attempt > 0) {
                LogError(ErrorCategory::Network, ErrorSeverity::Info,
                        "Operation succeeded after " + std::to_string(attempt) + " retries");
            }
            return true;
        }
        
        if (attempt < maxRetries) {
            LogError(ErrorCategory::Network, ErrorSeverity::Warning,
                    "Operation failed, retrying (" + std::to_string(attempt + 1) + "/" + 
                    std::to_string(maxRetries) + ")");
            Sleep(retryDelayMs);
        }
    }
    
    if (!errorMessage.empty()) {
        LogError(ErrorCategory::Network, ErrorSeverity::Error,
                errorMessage + " (failed after " + std::to_string(maxRetries) + " retries)");
    }
    
    return false;
}

std::string ErrorHandler::RetryOperationWithResult(std::function<std::string()> operation,
                                                   int maxRetries,
                                                   int retryDelayMs,
                                                   const std::string& errorMessage) {
    for (int attempt = 0; attempt <= maxRetries; ++attempt) {
        std::string result = operation();
        
        // Check if result indicates error
        if (!result.empty() && result.find("Error:") != 0) {
            if (attempt > 0) {
                LogError(ErrorCategory::Network, ErrorSeverity::Info,
                        "Operation succeeded after " + std::to_string(attempt) + " retries");
            }
            return result;
        }
        
        // Check if error is retryable
        if (attempt < maxRetries && IsRetryableError(result)) {
            LogError(ErrorCategory::Network, ErrorSeverity::Warning,
                    "Operation failed with retryable error, retrying (" + 
                    std::to_string(attempt + 1) + "/" + std::to_string(maxRetries) + "): " + result);
            Sleep(retryDelayMs);
        } else {
            // Not retryable or max retries reached
            if (!errorMessage.empty()) {
                LogError(ErrorCategory::Network, ErrorSeverity::Error,
                        errorMessage + " (failed after " + std::to_string(attempt + 1) + " attempts): " + result);
            }
            return result;
        }
    }
    
    if (!errorMessage.empty()) {
        LogError(ErrorCategory::Network, ErrorSeverity::Error,
                errorMessage + " (failed after " + std::to_string(maxRetries) + " retries)");
    }
    
    return "Error: Operation failed after maximum retries";
}

void ErrorHandler::SetErrorCallback(std::function<void(const ErrorInfo&)> callback) {
    errorCallback_ = callback;
}