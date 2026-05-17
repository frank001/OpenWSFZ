# Dependency acquisition strategy for OpenWSFZ.
#
# We use FetchContent so a clean checkout configures and builds with no
# external package manager. Drogon (MIT) is the only direct dependency
# at this stage; it transitively pulls Trantor (also MIT), and we let
# its own CMake handle jsoncpp/zlib resolution.
#
# Knobs are tuned for the skeleton: we don't need ORM, ctl, examples,
# tests, or TLS for a loopback-only daemon.

include(FetchContent)

set(OPENWSFZ_DROGON_TAG "v1.9.13" CACHE STRING
    "Git tag of drogonframework/drogon to fetch")
set(OPENWSFZ_DROGON_URL "https://github.com/drogonframework/drogon.git" CACHE STRING
    "Source URL for Drogon")
set(OPENWSFZ_JSONCPP_TAG "1.9.6" CACHE STRING
    "Git tag of open-source-parsers/jsoncpp to fetch")
set(OPENWSFZ_JSONCPP_URL "https://github.com/open-source-parsers/jsoncpp.git" CACHE STRING
    "Source URL for jsoncpp")

# ---- jsoncpp -------------------------------------------------------------
#
# Drogon hard-depends on jsoncpp via its own FindJsoncpp.cmake, which on
# Windows finds nothing because there's no system install. We fetch it
# first, build the static target, then point Drogon's find variables at
# the fetched tree so its `find_package(Jsoncpp REQUIRED)` is satisfied
# without anyone installing anything.

set(JSONCPP_WITH_TESTS              OFF CACHE BOOL "" FORCE)
set(JSONCPP_WITH_POST_BUILD_UNITTEST OFF CACHE BOOL "" FORCE)
set(JSONCPP_WITH_WARNING_AS_ERROR   OFF CACHE BOOL "" FORCE)
set(JSONCPP_WITH_PKGCONFIG_SUPPORT  OFF CACHE BOOL "" FORCE)
set(JSONCPP_WITH_CMAKE_PACKAGE      OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS               OFF CACHE BOOL "" FORCE)
set(BUILD_STATIC_LIBS               ON  CACHE BOOL "" FORCE)
set(BUILD_OBJECT_LIBS               OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    jsoncpp
    GIT_REPOSITORY ${OPENWSFZ_JSONCPP_URL}
    GIT_TAG        ${OPENWSFZ_JSONCPP_TAG}
    GIT_SHALLOW    TRUE
)
message(STATUS "Fetching jsoncpp ${OPENWSFZ_JSONCPP_TAG} ...")
FetchContent_MakeAvailable(jsoncpp)

# Satisfy Drogon's FindJsoncpp.cmake. INCLUDE_DIRS points at the in-tree
# headers; LIBRARIES points at the static target jsoncpp's CMake created.
# Drogon passes JSONCPP_LIBRARIES to target_link_libraries, which accepts
# either a path or a CMake target name.
set(JSONCPP_INCLUDE_DIRS "${jsoncpp_SOURCE_DIR}/include"
    CACHE PATH "Path to jsoncpp headers (set by OpenWSFZ)" FORCE)
set(JSONCPP_LIBRARIES    jsoncpp_static
    CACHE STRING "jsoncpp static target name (set by OpenWSFZ)" FORCE)

# Drogon build-time switches: minimise surface area for the skeleton.
set(BUILD_ORM            OFF CACHE BOOL "" FORCE)
set(BUILD_CTL            OFF CACHE BOOL "" FORCE)
set(BUILD_EXAMPLES       OFF CACHE BOOL "" FORCE)
set(BUILD_TESTING        OFF CACHE BOOL "" FORCE)
set(BUILD_BROTLI         OFF CACHE BOOL "" FORCE)
set(BUILD_YAML_CONFIG    OFF CACHE BOOL "" FORCE)
set(BUILD_DROGON_SHARED  OFF CACHE BOOL "" FORCE)
set(BUILD_POSTGRESQL     OFF CACHE BOOL "" FORCE)
set(BUILD_MYSQL          OFF CACHE BOOL "" FORCE)
set(BUILD_SQLITE         OFF CACHE BOOL "" FORCE)
set(BUILD_REDIS          OFF CACHE BOOL "" FORCE)
# TLS off for the skeleton; loopback bind makes it unnecessary.
set(USE_OPENSSL          OFF CACHE BOOL "" FORCE)

# ---- Drogon --------------------------------------------------------------

FetchContent_Declare(
    drogon
    GIT_REPOSITORY ${OPENWSFZ_DROGON_URL}
    GIT_TAG        ${OPENWSFZ_DROGON_TAG}
    GIT_SHALLOW    TRUE
    GIT_PROGRESS   TRUE
)

# MakeAvailable runs Drogon's CMakeLists which embeds Trantor via the
# `trantor/` submodule directory checked out by Git.
message(STATUS "Fetching Drogon ${OPENWSFZ_DROGON_TAG} ...")
FetchContent_MakeAvailable(drogon)
