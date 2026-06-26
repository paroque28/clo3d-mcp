# cpp-plugin — build scaffold (placeholder, not yet implemented)
#
# Fill in once the C++ backend is built. It must:
#   - link against the CLO SDK headers in ../../sdk/CLOAPIInterface
#   - enable Qt MOC (AUTOMOC) for the signal/slot main-thread marshaling
#   - export the CLO plugin entry points (DoFunction, GetActionName, ...)
#   - run a socket server on a worker thread, marshaling to the main thread
#
# See README.md for the design and gregor124/clo-mcp for a reference PoC.

cmake_minimum_required(VERSION 3.16)
project(clo_cpp_plugin LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

# find_package(Qt6 COMPONENTS Core REQUIRED)   # or Qt5
# include_directories(${CMAKE_CURRENT_SOURCE_DIR}/../../sdk/CLOAPIInterface
#                     ${CMAKE_CURRENT_SOURCE_DIR}/../../sdk/CLOAPIInterface/include)
# add_library(clo_cpp_plugin SHARED src/Plugin.cpp)
# target_link_libraries(clo_cpp_plugin PRIVATE Qt6::Core)

message(STATUS "cpp-plugin is a scaffold; see README.md before implementing.")
