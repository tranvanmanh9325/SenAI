#pragma once

#include <string>
#include <vector>
#include <memory>
#include <nlohmann/json.hpp>

/**
 * JsonParser - Wrapper class for JSON parsing operations
 * 
 * Provides a safe, centralized way to parse JSON with proper error handling.
 * Uses nlohmann/json library for robust JSON parsing.
 */
class JsonParser {
public:
    /**
     * Parse a JSON string into a JSON object
     * @param jsonString The JSON string to parse
     * @return Parsed JSON object, or nullptr if parsing failed
     */
    static std::unique_ptr<nlohmann::json> Parse(const std::string& jsonString);

    /**
     * Extract a string field from JSON
     * @param jsonString The JSON string
     * @param fieldName The name of the field to extract
     * @param defaultValue Default value if field not found or invalid
     * @return The field value, or defaultValue if not found/invalid
     */
    static std::string GetString(const std::string& jsonString, 
                                 const std::string& fieldName, 
                                 const std::string& defaultValue = "");

    /**
     * Extract an integer field from JSON
     * @param jsonString The JSON string
     * @param fieldName The name of the field to extract
     * @param defaultValue Default value if field not found or invalid
     * @return The field value, or defaultValue if not found/invalid
     */
    static int GetInt(const std::string& jsonString, 
                      const std::string& fieldName, 
                      int defaultValue = 0);

    /**
     * Extract a boolean field from JSON
     * @param jsonString The JSON string
     * @param fieldName The name of the field to extract
     * @param defaultValue Default value if field not found or invalid
     * @return The field value, or defaultValue if not found/invalid
     */
    static bool GetBool(const std::string& jsonString, 
                        const std::string& fieldName, 
                        bool defaultValue = false);

    /**
     * Check if a JSON string is valid
     * @param jsonString The JSON string to validate
     * @return true if valid, false otherwise
     */
    static bool IsValid(const std::string& jsonString);

    /**
     * Extract a nested field using dot notation (e.g., "user.name")
     * @param jsonString The JSON string
     * @param fieldPath The dot-separated path to the field
     * @param defaultValue Default value if field not found
     * @return The field value as string, or defaultValue if not found
     */
    static std::string GetNestedString(const std::string& jsonString,
                                       const std::string& fieldPath,
                                       const std::string& defaultValue = "");

    /**
     * Parse a JSON array and extract all elements
     * @param jsonString The JSON string containing an array
     * @return Vector of JSON objects, empty if parsing failed or not an array
     */
    static std::vector<nlohmann::json> ParseArray(const std::string& jsonString);

    /**
     * Build a JSON object from key-value pairs
     * @param pairs Vector of key-value pairs
     * @return JSON string representation
     */
    static std::string BuildJson(const std::vector<std::pair<std::string, std::string>>& pairs);

    /**
     * Build a JSON object with a single key-value pair
     * @param key The key
     * @param value The value (will be escaped)
     * @return JSON string representation
     */
    static std::string BuildJson(const std::string& key, const std::string& value);

    /**
     * Escape a string for JSON (for manual JSON building if needed)
     * @param str The string to escape
     * @return Escaped string
     */
    static std::string EscapeJson(const std::string& str);

    /**
     * Log JSON parsing errors (public for use in other classes)
     * @param errorMessage The error message to log
     */
    static void LogError(const std::string& errorMessage);
};

