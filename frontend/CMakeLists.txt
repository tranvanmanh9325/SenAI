cmake_minimum_required(VERSION 3.10)
project(SenAIFrontend LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Windows subsystem for GUI app
if(WIN32)
    set(CMAKE_WIN32_EXECUTABLE ON)
endif()

# Source files
set(SOURCES
    src/main.cpp
    src/MainWindow.cpp
    src/MainWindowLogic.cpp
    src/MainWindowConversations.cpp
    src/MainWindowChatMessages.cpp
    src/MainWindowUI.cpp
    src/MainWindowRender.cpp
    src/MainWindowRenderControls.cpp
    src/MainWindowRenderSidebar.cpp
    src/MainWindowHelpers.cpp
    src/MainWindowMessageHelpers.cpp
    src/HttpClient.cpp
)

set(HEADERS
    src/MainWindow.h
    src/MainWindowHelpers.h
    src/HttpClient.h
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

# Include directories
target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)

# Set output directory
set_target_properties(${PROJECT_NAME} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)