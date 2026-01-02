#pragma once

#include <windows.h>
#include <string>

// UI Configuration Structures
// These structs replace hard-coded values and provide a centralized way to configure UI behavior

namespace UiConfig {

    // Window configuration
    struct WindowConfig {
        int defaultWidth = 900;
        int defaultHeight = 700;
        std::wstring className = L"SenAIMainWindow";
        std::wstring title = L"SenAI";
    };

    // Sidebar configuration
    struct SidebarConfig {
        int width = 280;
        int itemHeight = 75;
        int itemPaddingX = 16;
        int itemPaddingY = 8;
        int titleHeight = 28;
        int buttonHeight = 34;
        int spacingAfterButton = 12;
        int spacingAfterTitle = 12;
        int spacingFromHeader = 12;
        int scrollPixelsPerNotch = 50;
        bool visible = true;
    };

    // Input field configuration
    struct InputConfig {
        int height = 60;
        int paddingX = 50;
        int radius = 28;
        int bufferSize = 1024;
        int chatScrollPixelsPerNotch = 60;
        bool enableCtrlEnterToSend = true;
        bool showPlaceholder = true;
    };

    // Grid pattern configuration
    struct GridConfig {
        int spacingX = 80;
        int spacingY = 80;
        int startX = 60;
        int startY = 60;
        bool enabled = true;
    };

    // Orb decoration configuration
    struct OrbConfig {
        int size = 120;
        int offsetX = 80;
        int offsetY = 80;
        bool enabled = true;
    };

    // Message bubble configuration
    struct MessageBubbleConfig {
        int maxWidthPercent = 75; // Max 75% of available width
        int skipThresholdY = 50; // Skip messages above visible area
        int iconInflateSize = 4; // Inflate rect for copy icon feedback
    };

    // Animation configuration
    struct AnimationConfig {
        UINT_PTR timerIdInput = 1;
        UINT_PTR timerIdHealthCheck = 2;
        UINT_PTR timerIdCopyFeedback = 3;
        int animationFrameRate = 16; // ~60fps
    };

    // User interaction configuration
    struct InteractionConfig {
        DWORD doubleClickWindowMs = 500; // 500ms double-click window
    };

    // Complete UI configuration
    struct UIConfig {
        WindowConfig window;
        SidebarConfig sidebar;
        InputConfig input;
        GridConfig grid;
        OrbConfig orb;
        MessageBubbleConfig messageBubble;
        AnimationConfig animation;
        InteractionConfig interaction;
    };

    // Get default configuration
    inline UIConfig GetDefaultConfig() {
        return UIConfig{};
    }

} // namespace UiConfig