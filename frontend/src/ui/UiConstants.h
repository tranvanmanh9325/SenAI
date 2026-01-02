#pragma once

// UI Constants - Centralized location for all magic numbers and hard-coded values
// This file helps maintain consistency and makes it easier to adjust UI parameters

namespace UiConstants {

    // Window dimensions
    namespace Window {
        constexpr int DEFAULT_WIDTH = 900;
        constexpr int DEFAULT_HEIGHT = 700;
    }

    // Sidebar dimensions and layout
    namespace Sidebar {
        constexpr int WIDTH = 280;
        constexpr int ITEM_HEIGHT = 75;
        constexpr int ITEM_PADDING_X = 16;
        constexpr int ITEM_PADDING_Y = 8;
        constexpr int TITLE_HEIGHT = 28;
        constexpr int BUTTON_HEIGHT = 34;
        constexpr int SPACING_AFTER_BUTTON = 12;
        constexpr int SPACING_AFTER_TITLE = 12;
        constexpr int SPACING_FROM_HEADER = 12;
        constexpr int SCROLL_PIXELS_PER_NOTCH = 50;
    }

    // Input field dimensions and layout
    namespace Input {
        constexpr int HEIGHT = 60;
        constexpr int PADDING_X = 50;
        constexpr int RADIUS = 28;
        constexpr int BUFFER_SIZE = 1024;
        constexpr int CHAT_SCROLL_PIXELS_PER_NOTCH = 60;
    }

    // Grid pattern
    namespace Grid {
        constexpr int SPACING_X = 80;
        constexpr int SPACING_Y = 80;
        constexpr int START_X = 60;
        constexpr int START_Y = 60;
    }

    // Orb decoration
    namespace Orb {
        constexpr int SIZE = 120;
        constexpr int OFFSET_X = 80;
        constexpr int OFFSET_Y = 80;
    }

    // Message bubble layout
    namespace Message {
        constexpr int MAX_BUBBLE_WIDTH_PERCENT = 75; // 75% of available width
        constexpr int SKIP_THRESHOLD_Y = 50; // Skip messages above visible area
        constexpr int ICON_INFLATE_SIZE = 4; // Inflate rect for copy icon feedback
    }

    // Animation and timing
    namespace Animation {
        constexpr int TIMER_ID_INPUT = 1;
        constexpr int TIMER_ID_HEALTH_CHECK = 2;
        constexpr int TIMER_ID_COPY_FEEDBACK = 3;
    }

    // User interaction timing
    namespace Interaction {
        constexpr DWORD DOUBLE_CLICK_WINDOW_MS = 500; // 500ms double-click window
    }

    // Colors - Status badges
    namespace Colors {
        namespace Status {
            constexpr COLORREF ONLINE_BG = RGB(50, 140, 80);      // Green
            constexpr COLORREF ONLINE_BORDER = RGB(90, 200, 120);
            constexpr COLORREF WARNING_BG = RGB(180, 150, 60);   // Amber/Yellow
            constexpr COLORREF WARNING_BORDER = RGB(220, 180, 80);
            constexpr COLORREF ERROR_BG = RGB(180, 60, 60);      // Red
            constexpr COLORREF ERROR_BORDER = RGB(220, 100, 100);
        }

        // Sidebar colors
        namespace Sidebar {
            constexpr COLORREF BORDER = RGB(40, 50, 70);
            constexpr COLORREF TEXT_NORMAL = RGB(200, 210, 230);
            constexpr COLORREF GLOW_BG = RGB(20, 50, 80);
            constexpr COLORREF GLOW_PEN = RGB(40, 100, 140);
            constexpr COLORREF HOVER_PEN = RGB(70, 140, 200);
            constexpr COLORREF SELECTED_GLOW_PEN = RGB(50, 100, 150);
            constexpr COLORREF TEXT_SELECTED = RGB(160, 200, 240);
            constexpr COLORREF TEXT_HOVER = RGB(215, 230, 250);
            constexpr COLORREF TEXT_META = RGB(60, 110, 150);
        }

        // Message bubble colors
        namespace MessageBubble {
            constexpr COLORREF USER_HOVER_FILL = RGB(38, 45, 75);
            constexpr COLORREF USER_HOVER_BORDER = RGB(100, 130, 180);
            constexpr COLORREF CODE_BORDER = RGB(80, 120, 160);
            constexpr COLORREF CODE_TEXT = RGB(255, 240, 200);
            constexpr COLORREF SYSTEM_FILL = RGB(30, 50, 70);
            constexpr COLORREF SYSTEM_BORDER = RGB(120, 200, 255);
            constexpr COLORREF SYSTEM_AVATAR = RGB(100, 180, 255);
            constexpr COLORREF CODE_AVATAR = RGB(120, 150, 200);
        }

        // Send button colors
        namespace SendButton {
            constexpr COLORREF HOVER = RGB(100, 235, 255);
            constexpr COLORREF NORMAL = RGB(74, 215, 255);
        }

        // Dialog colors
        namespace Dialog {
            constexpr COLORREF CLOSE_HOVER = RGB(255, 100, 100);
            constexpr COLORREF CLOSE_NORMAL = RGB(200, 210, 230);
            constexpr COLORREF BUTTON_BG_NORMAL = RGB(25, 36, 64);
            constexpr COLORREF BUTTON_BG_HOVER = RGB(40, 50, 70);
            constexpr COLORREF BUTTON_BORDER = RGB(60, 90, 130);
            constexpr COLORREF BUTTON_TEXT = RGB(200, 210, 230);
            constexpr COLORREF TEXT = RGB(200, 210, 230);
        }

        // Settings dialog
        namespace Settings {
            constexpr COLORREF CHECKBOX_BORDER = RGB(60, 90, 130);
            constexpr COLORREF CHECKBOX_BORDER_HOVER = RGB(100, 150, 200);
        }
    }

    // Layout spacing
    namespace Spacing {
        constexpr int SMALL = 4;
        constexpr int MEDIUM = 12;
        constexpr int LARGE = 16;
        constexpr int INPUT_TOP_MARGIN = 4; // Margin above input field
    }

    // Dialog dimensions
    namespace Dialog {
        namespace ExitConfirm {
            constexpr int YES_BUTTON_X = 200;
            constexpr int YES_BUTTON_Y = 130;
            constexpr int YES_BUTTON_WIDTH = 80;
            constexpr int YES_BUTTON_HEIGHT = 32;
        }
        namespace Settings {
            constexpr int LABEL_X = 20;
            constexpr int LABEL1_Y = 48;
            constexpr int LABEL1_HEIGHT = 18;
            constexpr int LABEL2_Y = 108;
            constexpr int LABEL2_HEIGHT = 18;
        }
    }

    // Scale factors
    namespace Scale {
        constexpr int SEND_BUTTON_ICON = 3;
    }

} // namespace UiConstants