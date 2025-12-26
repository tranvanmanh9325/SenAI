#pragma once
#include <string>
#include <functional>
#include <memory>
#include <windows.h>

/**
 * Centralized Error Handling System
 * 
 * Features:
 * - Consistent error logging with timestamps and context
 * - User-friendly error messages
 * - Retry logic for network operations
 * - Error categorization
 * - Stack trace support (where available)
 */

enum class ErrorCategory {
    Network,        // Network/HTTP errors
    Json,           // JSON parsing errors
    System,         // System/OS errors
    Validation,     // Input validation errors
    Unknown         // Unknown errors
};

enum class ErrorSeverity {
    Info,           // Informational
    Warning,        // Warning - operation may continue
    Error,          // Error - operation failed but app continues
    Critical        // Critical - app may need to exit
};

struct ErrorInfo {
    ErrorCategory category;
    ErrorSeverity severity;
    std::string message;
    std::string context;        // Additional context (function name, etc.)
    std::string technicalDetails; // Technical details for logging
    DWORD systemErrorCode = 0;   // Windows error code if applicable
    
    ErrorInfo(ErrorCategory cat, ErrorSeverity sev, const std::string& msg)
        : category(cat), severity(sev), message(msg) {}
};

class ErrorHandler {
public:
    // Singleton pattern
    static ErrorHandler& GetInstance();
    
    /**
     * Log an error with full context
     */
    void LogError(const ErrorInfo& error);
    
    /**
     * Log error with automatic categorization
     */
    void LogError(ErrorCategory category, ErrorSeverity severity, 
                  const std::string& message, const std::string& context = "");
    
    /**
     * Log error with Windows system error code
     */
    void LogSystemError(const std::string& message, const std::string& context = "");
    
    /**
     * Show user-friendly error message (MessageBox)
     */
    void ShowUserError(const std::string& title, const std::string& message, HWND parent = NULL);
    
    /**
     * Show user-friendly error message (wide string version)
     */
    void ShowUserError(const std::wstring& title, const std::wstring& message, HWND parent = NULL);
    
    /**
     * Get user-friendly error message from technical error
     */
    std::wstring GetUserFriendlyMessage(const ErrorInfo& error);
    
    /**
     * Retry logic for operations that may fail
     * @param operation Function to retry (returns true on success)
     * @param maxRetries Maximum number of retries
     * @param retryDelayMs Delay between retries in milliseconds
     * @param errorMessage Error message to log if all retries fail
     * @return true if operation succeeded, false if all retries failed
     */
    bool RetryOperation(std::function<bool()> operation, 
                       int maxRetries = 3, 
                       int retryDelayMs = 1000,
                       const std::string& errorMessage = "");
    
    /**
     * Retry logic for operations that return a value
     * @param operation Function to retry (returns value, empty string on error)
     * @param maxRetries Maximum number of retries
     * @param retryDelayMs Delay between retries in milliseconds
     * @param errorMessage Error message to log if all retries fail
     * @return Result string, empty if all retries failed
     */
    std::string RetryOperationWithResult(std::function<std::string()> operation,
                                        int maxRetries = 3,
                                        int retryDelayMs = 1000,
                                        const std::string& errorMessage = "");
    
    /**
     * Check if error is retryable (network errors, timeouts, etc.)
     */
    bool IsRetryableError(const std::string& errorMessage) const;
    
    /**
     * Get log file path
     */
    std::string GetLogFilePath() const;
    
    /**
     * Set callback for custom error handling (e.g., show in UI)
     */
    void SetErrorCallback(std::function<void(const ErrorInfo&)> callback);
    
private:
    ErrorHandler();
    ~ErrorHandler() = default;
    ErrorHandler(const ErrorHandler&) = delete;
    ErrorHandler& operator=(const ErrorHandler&) = delete;
    
    void WriteToLog(const std::string& logEntry);
    std::string GetTimestamp();
    std::string GetCategoryString(ErrorCategory category);
    std::string GetSeverityString(ErrorSeverity severity);
    std::string GetLogFilePathInternal() const;
    
    std::function<void(const ErrorInfo&)> errorCallback_;
    std::string logFilePath_;
    bool logFilePathInitialized_;
};

// Convenience macros for easier error logging
#define LOG_ERROR(category, severity, message) \
    ErrorHandler::GetInstance().LogError(category, severity, message, __FUNCTION__)

#define LOG_NETWORK_ERROR(message) \
    ErrorHandler::GetInstance().LogError(ErrorCategory::Network, ErrorSeverity::Error, message, __FUNCTION__)

#define LOG_JSON_ERROR(message) \
    ErrorHandler::GetInstance().LogError(ErrorCategory::Json, ErrorSeverity::Warning, message, __FUNCTION__)

#define LOG_SYSTEM_ERROR(message) ErrorHandler::GetInstance().LogSystemError(message, __FUNCTION__)
