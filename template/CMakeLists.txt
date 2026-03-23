cmake_minimum_required(VERSION 3.10)

project(atool VERSION 2.1.0 LANGUAGES C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# 输出路径
set(OUTPUT_DIR ${CMAKE_SOURCE_DIR}/dist)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${OUTPUT_DIR})
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${OUTPUT_DIR})
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${OUTPUT_DIR})

if(WIN32)
    set(PLATFORM "windows")
else()
    set(PLATFORM "linux")
endif()

add_executable(${PROJECT_NAME})

target_sources(${PROJECT_NAME} PRIVATE
    main.c
    cmdinfo.c
    port.c
    reg.c
    json/cJSON.c
    json/json.c
    logger/logger.c
    adapter/serial_${PLATFORM}.c
)

target_include_directories(${PROJECT_NAME} PRIVATE
    ${PROJECT_SOURCE_DIR}
    ${PROJECT_SOURCE_DIR}/adapter
    ${PROJECT_SOURCE_DIR}/json
    ${PROJECT_SOURCE_DIR}/logger
)
if(WIN32)
    target_include_directories(${PROJECT_NAME} PRIVATE
        ${PROJECT_SOURCE_DIR}/regex
    )
endif()

target_compile_options(${PROJECT_NAME} PRIVATE
    -fPIC
    -Wno-format-truncation
    -Wno-unused-result
    -Wno-unused-function
)

target_compile_definitions(${PROJECT_NAME} PRIVATE
    _GNU_SOURCE
    LOG_SIMPLE_FORMAT
)

if(WIN32)
    target_link_directories(${PROJECT_NAME} PRIVATE regex)
    target_link_libraries(${PROJECT_NAME} PRIVATE gnurx)

    add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${CMAKE_CURRENT_SOURCE_DIR}/regex/libgnurx-0.dll
            $<TARGET_FILE_DIR:${PROJECT_NAME}>
        COMMENT "Copying libgnurx-0.dll to output directory"
    )
else()
    target_link_libraries(${PROJECT_NAME} PRIVATE m pthread)
endif()
