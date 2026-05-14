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

# 拷贝MinGW运行时DLL到输出目录 (Windows)
if(WIN32)
    get_filename_component(COMPILER_DIR "${CMAKE_C_COMPILER}" DIRECTORY)
    # MinGW运行时DLL白名单，添加新依赖时在此列表追加即可
    set(MINGW_RUNTIME_DLLS
        libwinpthread-1.dll
        libstdc++-6.dll
        libgcc_s_seh-1.dll
        libgcc_s_dw2-1.dll
        libiconv.dll
        libintl.dll
        libiconv-2.dll
        libintl-8.dll
        pthread.dll
        msvcrt.dll
        msvcr120.dll
    )
    foreach(DLL_NAME ${MINGW_RUNTIME_DLLS})
        find_file(DLL_PATH NAMES ${DLL_NAME} PATHS ${COMPILER_DIR} ${COMPILER_DIR}/..)
        if(DLL_PATH)
            add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_if_different ${DLL_PATH} ${OUTPUT_DIR}/
            )
        endif()
    endforeach()
endif()

# 编译并打包: cmake --build build --config Release --target package 
# 创建打包配置 (ZIP格式)
set(CPACK_PACKAGE_NAME ${PROJECT_NAME})
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_GENERATOR ZIP)
set(CPACK_ARCHIVE_ZIP)
set(CPACK_PACKAGE_DIRECTORY ${CMAKE_SOURCE_DIR}/release)

# 打包运行时输出目录的所有内容
install(DIRECTORY ${OUTPUT_DIR}/ DESTINATION . FILES_MATCHING PATTERN "*")

include(CPack)
