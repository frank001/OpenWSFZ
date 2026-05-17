cmake_minimum_required(VERSION 3.20)

# Version is the single source of truth. Substituted into version.hpp.
set(OPENWSFZ_VERSION_MAJOR 0)
set(OPENWSFZ_VERSION_MINOR 1)
set(OPENWSFZ_VERSION_PATCH 0)
set(OPENWSFZ_VERSION_STRING
    "${OPENWSFZ_VERSION_MAJOR}.${OPENWSFZ_VERSION_MINOR}.${OPENWSFZ_VERSION_PATCH}-dev")

project(openwsfz
    VERSION ${OPENWSFZ_VERSION_MAJOR}.${OPENWSFZ_VERSION_MINOR}.${OPENWSFZ_VERSION_PATCH}
    DESCRIPTION "OpenWSFZ - MIT-licensed clean-room weak-signal amateur-radio daemon"
    HOMEPAGE_URL "https://github.com/frank001/OpenWSFZ"
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Single output dir keeps the runtime artefacts next to the web/ tree.
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

list(APPEND CMAKE_MODULE_PATH ${CMAKE_SOURCE_DIR}/cmake)

include(CompileFlags)
include(Dependencies)

# Capture git SHA at configure time (best-effort; falls back to "unknown").
find_package(Git QUIET)
if(GIT_FOUND AND EXISTS "${CMAKE_SOURCE_DIR}/.git")
    execute_process(
        COMMAND ${GIT_EXECUTABLE} rev-parse --short=12 HEAD
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
        OUTPUT_VARIABLE OPENWSFZ_GIT_SHA
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
endif()
if(NOT OPENWSFZ_GIT_SHA)
    set(OPENWSFZ_GIT_SHA "unknown")
endif()

# Generate include/openwsfz/version.hpp from the template.
configure_file(
    ${CMAKE_SOURCE_DIR}/include/openwsfz/version.hpp.in
    ${CMAKE_BINARY_DIR}/generated/include/openwsfz/version.hpp
    @ONLY
)

add_executable(openwsfz
    src/main.cpp
    src/WsController.cc
)

target_include_directories(openwsfz PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_BINARY_DIR}/generated/include
)

target_link_libraries(openwsfz PRIVATE drogon)

openwsfz_apply_compile_flags(openwsfz)

# Copy web/ next to the binary so the daemon's default --doc-root works
# whether run from the source tree (cwd=repo root) or the build tree.
add_custom_command(TARGET openwsfz POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        ${CMAKE_SOURCE_DIR}/web
        $<TARGET_FILE_DIR:openwsfz>/web
    COMMENT "Staging web/ next to the binary"
)

message(STATUS "OpenWSFZ ${OPENWSFZ_VERSION_STRING} (git ${OPENWSFZ_GIT_SHA})")
