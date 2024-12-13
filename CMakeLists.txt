cmake_minimum_required(VERSION 3.15)

# Use c++ 17 for std::optional
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

project(no5 LANGUAGES CXX)

# Allow installing one target at a time, so the python wheel from pyproject.toml
# can build and install only the python bits.
set(CMAKE_SKIP_INSTALL_ALL_DEPENDENCY true)

# Default install to build/results
if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    set(CMAKE_INSTALL_PREFIX "${CMAKE_BINARY_DIR}/../results" CACHE PATH "Default install path" FORCE)
endif()

include(FetchContent)

# Download the json library so it can be linked to dump.
FetchContent_Declare(json URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz)
FetchContent_MakeAvailable(json)


# Dumper

add_executable(nitrodump ./src/dump.cpp ./src/lib_no5.cpp)
target_link_libraries(nitrodump PRIVATE nlohmann_json::nlohmann_json)

install(TARGETS nitrodump DESTINATION . OPTIONAL)

# Python Bindings

# Download pybind so it can be linked.
FetchContent_Declare(
    pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11
    GIT_TAG        v2.11.1
)
FetchContent_MakeAvailable(pybind11)


find_package(Python REQUIRED COMPONENTS Interpreter Development)

pybind11_add_module(no5 ./src/no5_py.cpp ./src/lib_no5.cpp)
target_link_libraries(no5 PRIVATE nlohmann_json::nlohmann_json)

install(TARGETS no5 DESTINATION . OPTIONAL COMPONENT NO5_PY)

install(DIRECTORY ./nxt2no5 DESTINATION . OPTIONAL COMPONENT NO5_PY)