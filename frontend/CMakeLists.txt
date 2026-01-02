cmake_minimum_required(VERSION 3.14)
project(SenAIFrontend LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Include nlohmann/json using single header file
# Download the single header file if it doesn't exist
set(JSON_HEADER_DIR ${CMAKE_CURRENT_BINARY_DIR}/json_include)
set(JSON_HEADER_FILE ${JSON_HEADER_DIR}/nlohmann/json.hpp)

if(NOT EXISTS ${JSON_HEADER_FILE})
    file(MAKE_DIRECTORY ${JSON_HEADER_DIR}/nlohmann)
    message(STATUS "Downloading nlohmann/json single header...")
    file(DOWNLOAD 
        https://github.com/nlohmann/json/releases/download/v3.11.3/json.hpp
        ${JSON_HEADER_FILE}
        SHOW_PROGRESS
        STATUS DOWNLOAD_STATUS
    )
    list(GET DOWNLOAD_STATUS 0 STATUS_CODE)
    if(NOT STATUS_CODE EQUAL 0)
        message(FATAL_ERROR "Failed to download nlohmann/json header file")
    endif()
endif()

# Create interface library for nlohmann/json
add_library(nlohmann_json INTERFACE)
target_include_directories(nlohmann_json INTERFACE ${JSON_HEADER_DIR})

# Windows subsystem for GUI app
if(WIN32)
    set(CMAKE_WIN32_EXECUTABLE ON)
endif()

# Source files
set(SOURCES
    src/main.cpp
    # UI files
    src/ui/MainWindow.cpp
    src/ui/MainWindowLogic.cpp
    src/ui/MainWindowConversations.cpp
    src/ui/MainWindowChatMessages.cpp
    src/ui/MainWindowUI.cpp
    src/ui/MainWindowRender.cpp
    src/ui/MainWindowSettings.cpp
    src/ui/MainWindowExitConfirm.cpp
    src/ui/MainWindowExport.cpp
    src/ui/MainWindowExportMessage.cpp
    src/ui/MainWindowRenderControls.cpp
    src/ui/MainWindowRenderSidebar.cpp
    src/ui/MainWindowHelpers.cpp
    src/ui/MainWindowMessageHelpers.cpp
    src/ui/MainWindowMessageHandlers.cpp
    src/ui/MainWindowSearch.cpp
    # Core files
    src/core/HttpClient.cpp
    src/core/JsonParser.cpp
    src/core/GDIResourceManager.cpp
    src/core/ErrorHandler.cpp
    src/core/ExportService.cpp
)

set(HEADERS
    # UI headers
    src/ui/MainWindow.h
    src/ui/MainWindowHelpers.h
    src/ui/UiConstants.h
    src/ui/UiConfig.h
    # Core headers
    src/core/HttpClient.h
    src/core/JsonParser.h
    src/core/GDIResourceManager.h
    src/core/ErrorHandler.h
    src/core/ExportService.h
)

# Create executable
add_executable(${PROJECT_NAME} WIN32 ${SOURCES} ${HEADERS})

# Link Windows libraries
target_link_libraries(${PROJECT_NAME} PRIVATE
    wininet
    comctl32
    ole32
    uxtheme
    dwmapi
    gdiplus
    msimg32
)

# nlohmann/json is header-only, link to our interface library
target_link_libraries(${PROJECT_NAME} PRIVATE nlohmann_json)

# Include directories
target_include_directories(${PROJECT_NAME} PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/core
    ${CMAKE_CURRENT_SOURCE_DIR}/src/ui
)

# Set output directory
set_target_properties(${PROJECT_NAME} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)