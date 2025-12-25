#pragma once
#include <string>
#include <map>

// Define string IDs for i18n support
enum StringID {
    IDS_APP_TITLE,
    IDS_HERO_TITLE,
    IDS_HERO_SUBTITLE,
    IDS_INPUT_PLACEHOLDER,
    IDS_INPUT_HINT,
    IDS_STATUS_ONLINE,
    IDS_STATUS_CHECKING,
    IDS_STATUS_OFFLINE,
    IDS_SETTINGS_TITLE,
    IDS_API_URL_LABEL,
    IDS_API_KEY_LABEL,
    IDS_OK_BUTTON,
    IDS_CANCEL_BUTTON,
    IDS_AI_LOADING_MESSAGE,
    IDS_ERROR_TIMEOUT,
    IDS_ERROR_BACKEND,
    IDS_ERROR_TECHNICAL_DETAILS,
    IDS_BACKEND_NO_CONTENT,
    IDS_SESSION_LABEL,
    IDS_MODEL_LABEL,
    IDS_MODEL_NOT_AVAILABLE,
    IDS_CONVERSATION_PREVIEW_DEFAULT,
    IDS_CONVERSATION_NEW,
    IDS_SIDEBAR_HISTORY_TITLE,
    IDS_SIDEBAR_NEW_CHAT,
    IDS_ERROR_DIALOG_TITLE,
    IDS_ERROR_WINDOW_CREATE_FAILED,
    IDS_ERROR_INPUT_CREATE_FAILED,
    IDS_EXIT_CONFIRM_TITLE,
    IDS_EXIT_CONFIRM_MESSAGE,
    IDS_YES_BUTTON,
    IDS_NO_BUTTON,
    // Add more as needed
};

// Class to manage UI strings (can be extended for actual i18n loading from JSON)
class UiStrings {
public:
    // Initialize default Vietnamese strings
    static void Initialize() {
        strings_[IDS_APP_TITLE] = L"SenAI";
        strings_[IDS_HERO_TITLE] = L"Hôm nay bạn có ý tưởng gì?";
        strings_[IDS_HERO_SUBTITLE] = L"Tiểu Bối sẵn sàng giúp bạn.";
        strings_[IDS_INPUT_PLACEHOLDER] = L"Hỏi bất kỳ điều gì";
        strings_[IDS_INPUT_HINT] = L"Enter để gửi, Ctrl+L để focus ô nhập";
        strings_[IDS_STATUS_ONLINE] = L"Online";
        strings_[IDS_STATUS_CHECKING] = L"Đang kết nối…";
        strings_[IDS_STATUS_OFFLINE] = L"Offline";
        strings_[IDS_SETTINGS_TITLE] = L"Cài đặt";
        strings_[IDS_API_URL_LABEL] = L"API URL:";
        strings_[IDS_API_KEY_LABEL] = L"API Key:";
        strings_[IDS_OK_BUTTON] = L"OK";
        strings_[IDS_CANCEL_BUTTON] = L"Hủy";
        strings_[IDS_AI_LOADING_MESSAGE] = L"AI đang trả lời…";
        strings_[IDS_ERROR_TIMEOUT] = L"Yêu cầu đến server mất quá nhiều thời gian. Vui lòng kiểm tra kết nối mạng hoặc thử lại sau.";
        strings_[IDS_ERROR_BACKEND] = L"Đã xảy ra lỗi khi gọi backend. Bạn hãy thử lại sau hoặc kiểm tra server.";
        strings_[IDS_ERROR_TECHNICAL_DETAILS] = L"Chi tiết kỹ thuật: ";
        strings_[IDS_BACKEND_NO_CONTENT] = L"(Backend không trả về nội dung.)";
        strings_[IDS_SESSION_LABEL] = L"Session: ";
        strings_[IDS_MODEL_LABEL] = L"Model: ";
        strings_[IDS_MODEL_NOT_AVAILABLE] = L"(chưa có)";
        strings_[IDS_CONVERSATION_PREVIEW_DEFAULT] = L"Cuộc trò chuyện";
        strings_[IDS_CONVERSATION_NEW] = L"Mới";
        strings_[IDS_SIDEBAR_HISTORY_TITLE] = L"Lịch sử";
        strings_[IDS_SIDEBAR_NEW_CHAT] = L"Chat Mới";
        strings_[IDS_ERROR_DIALOG_TITLE] = L"Error";
        strings_[IDS_ERROR_WINDOW_CREATE_FAILED] = L"Failed to create window!\nError code: %lu";
        strings_[IDS_ERROR_INPUT_CREATE_FAILED] = L"Failed to create input control\nError: %lu";
        strings_[IDS_EXIT_CONFIRM_TITLE] = L"Xác nhận thoát";
        strings_[IDS_EXIT_CONFIRM_MESSAGE] = L"Bạn có muốn thoát ứng dụng?";
        strings_[IDS_YES_BUTTON] = L"Có";
        strings_[IDS_NO_BUTTON] = L"Không";
    }

    // Get string by ID
    static const std::wstring& Get(StringID id) {
        if (strings_.empty()) {
            Initialize();
        }
        auto it = strings_.find(id);
        if (it != strings_.end()) {
            return it->second;
        }
        static const std::wstring empty = L"";
        return empty;
    }

    // Future: Load strings from JSON file
    // static bool LoadFromJson(const std::string& jsonPath);
    
    // Future: Set language
    // static void SetLanguage(const std::string& langCode);

private:
    static std::map<StringID, std::wstring> strings_;
};

// Initialize static member
inline std::map<StringID, std::wstring> UiStrings::strings_;