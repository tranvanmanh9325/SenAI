cmake_minimum_required(VERSION 3.10)
project(SenAIFrontend LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Source files
add_executable(SenAIFrontend
    src/main.cpp
)

# Set output directory
set_target_properties(SenAIFrontend PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)
