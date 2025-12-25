#include "JsonParser.h"
#include <windows.h>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <ctime>

namespace {
    // Log JSON parsing errors to file
    void LogJsonError(const std::string& message) {
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
        out << "[JSON] " << std::put_time(std::localtime(&t), "%Y-%m-%d %H:%M:%S")
            << " - " << message << "\n";
    }
}

std::unique_ptr<nlohmann::json> JsonParser::Parse(const std::string& jsonString) {
    if (jsonString.empty()) {
        LogJsonError("Empty JSON string provided");
        return nullptr;
    }

    try {
        auto json = std::make_unique<nlohmann::json>(nlohmann::json::parse(jsonString));
        return json;
    } catch (const nlohmann::json::parse_error& e) {
        LogJsonError("JSON parse error: " + std::string(e.what()) + " - Input: " + jsonString.substr(0, 200));
        return nullptr;
    } catch (const std::exception& e) {
        LogJsonError("JSON error: " + std::string(e.what()));
        return nullptr;
    } catch (...) {
        LogJsonError("Unknown error parsing JSON");
        return nullptr;
    }
}

std::string JsonParser::GetString(const std::string& jsonString, 
                                   const std::string& fieldName, 
                                   const std::string& defaultValue) {
    auto json = Parse(jsonString);
    if (!json || !json->is_object()) {
        return defaultValue;
    }

    try {
        if (json->contains(fieldName)) {
            auto& value = (*json)[fieldName];
            if (value.is_string()) {
                return value.get<std::string>();
            } else if (value.is_null()) {
                return defaultValue;
            } else {
                // Try to convert to string
                return value.dump();
            }
        }
    } catch (const std::exception& e) {
        LogJsonError("Error extracting field '" + fieldName + "': " + e.what());
    }

    return defaultValue;
}

int JsonParser::GetInt(const std::string& jsonString, 
                       const std::string& fieldName, 
                       int defaultValue) {
    auto json = Parse(jsonString);
    if (!json || !json->is_object()) {
        return defaultValue;
    }

    try {
        if (json->contains(fieldName)) {
            auto& value = (*json)[fieldName];
            if (value.is_number_integer()) {
                return value.get<int>();
            } else if (value.is_number_unsigned()) {
                return static_cast<int>(value.get<unsigned int>());
            } else if (value.is_string()) {
                // Try to parse string as int
                try {
                    return std::stoi(value.get<std::string>());
                } catch (...) {
                    return defaultValue;
                }
            }
        }
    } catch (const std::exception& e) {
        LogJsonError("Error extracting int field '" + fieldName + "': " + e.what());
    }

    return defaultValue;
}

bool JsonParser::GetBool(const std::string& jsonString, 
                         const std::string& fieldName, 
                         bool defaultValue) {
    auto json = Parse(jsonString);
    if (!json || !json->is_object()) {
        return defaultValue;
    }

    try {
        if (json->contains(fieldName)) {
            auto& value = (*json)[fieldName];
            if (value.is_boolean()) {
                return value.get<bool>();
            } else if (value.is_string()) {
                std::string str = value.get<std::string>();
                return (str == "true" || str == "1");
            } else if (value.is_number()) {
                return value.get<int>() != 0;
            }
        }
    } catch (const std::exception& e) {
        LogJsonError("Error extracting bool field '" + fieldName + "': " + e.what());
    }

    return defaultValue;
}

bool JsonParser::IsValid(const std::string& jsonString) {
    return Parse(jsonString) != nullptr;
}

std::string JsonParser::GetNestedString(const std::string& jsonString,
                                         const std::string& fieldPath,
                                         const std::string& defaultValue) {
    auto json = Parse(jsonString);
    if (!json) {
        return defaultValue;
    }

    try {
        // Split path by dots
        std::istringstream pathStream(fieldPath);
        std::string segment;
        nlohmann::json* current = json.get();

        while (std::getline(pathStream, segment, '.')) {
            if (current->is_object() && current->contains(segment)) {
                current = &(*current)[segment];
            } else {
                return defaultValue;
            }
        }

        if (current->is_string()) {
            return current->get<std::string>();
        } else if (current->is_null()) {
            return defaultValue;
        } else {
            return current->dump();
        }
    } catch (const std::exception& e) {
        LogJsonError("Error extracting nested field '" + fieldPath + "': " + e.what());
    }

    return defaultValue;
}

std::vector<nlohmann::json> JsonParser::ParseArray(const std::string& jsonString) {
    std::vector<nlohmann::json> result;

    auto json = Parse(jsonString);
    if (!json) {
        return result;
    }

    try {
        if (json->is_array()) {
            for (const auto& item : *json) {
                result.push_back(item);
            }
        } else {
            LogJsonError("JSON is not an array");
        }
    } catch (const std::exception& e) {
        LogJsonError("Error parsing array: " + std::string(e.what()));
    }

    return result;
}

std::string JsonParser::BuildJson(const std::vector<std::pair<std::string, std::string>>& pairs) {
    try {
        nlohmann::json json;
        for (const auto& pair : pairs) {
            json[pair.first] = pair.second;
        }
        return json.dump();
    } catch (const std::exception& e) {
        LogJsonError("Error building JSON: " + std::string(e.what()));
        return "{}";
    }
}

std::string JsonParser::BuildJson(const std::string& key, const std::string& value) {
    try {
        nlohmann::json json;
        json[key] = value;
        return json.dump();
    } catch (const std::exception& e) {
        LogJsonError("Error building JSON: " + std::string(e.what()));
        return "{}";
    }
}

std::string JsonParser::EscapeJson(const std::string& str) {
    try {
        nlohmann::json json = str;
        std::string escaped = json.dump();
        // Remove surrounding quotes that nlohmann/json adds
        if (escaped.length() >= 2 && escaped[0] == '"' && escaped[escaped.length() - 1] == '"') {
            return escaped.substr(1, escaped.length() - 2);
        }
        return escaped;
    } catch (const std::exception& e) {
        LogJsonError("Error escaping JSON string: " + std::string(e.what()));
        // Fallback to manual escaping
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
}

void JsonParser::LogError(const std::string& errorMessage) {
    LogJsonError(errorMessage);
}

