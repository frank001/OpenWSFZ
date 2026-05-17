# Shared compile flags. We keep these as a function rather than dumping
# into CMAKE_CXX_FLAGS globally so that fetched dependencies (Drogon /
# Trantor) build with their own defaults and we only impose strict
# warnings on first-party targets.

function(openwsfz_apply_compile_flags TARGET)
    if(MSVC)
        target_compile_options(${TARGET} PRIVATE
            /W4
            /permissive-
            /utf-8
            /Zc:__cplusplus
            /EHsc
        )
        target_compile_definitions(${TARGET} PRIVATE
            _CRT_SECURE_NO_WARNINGS
            NOMINMAX
            WIN32_LEAN_AND_MEAN
        )
    else()
        target_compile_options(${TARGET} PRIVATE
            -Wall
            -Wextra
            -Wpedantic
            -Wshadow
            -Wconversion
            -Wsign-conversion
            -Wnon-virtual-dtor
            -Woverloaded-virtual
            -Wold-style-cast
            -Wcast-align
            -Wno-unused-parameter
        )
    endif()

    # Position-independent code where it matters; doesn't hurt the
    # executable target but lets shared libraries link cleanly later.
    set_target_properties(${TARGET} PROPERTIES
        POSITION_INDEPENDENT_CODE ON
    )
endfunction()
