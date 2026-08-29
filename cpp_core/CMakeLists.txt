add_library(argus_core_lib STATIC
    src/signal_features.cpp
)
target_include_directories(argus_core_lib PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_compile_features(argus_core_lib PUBLIC cxx_std_20)
# Must be position-independent: this static lib is also linked into the
# pybind11 shared module below.
set_target_properties(argus_core_lib PROPERTIES POSITION_INDEPENDENT_CODE ON)

# Python extension module (built only when pybind11 is available).
find_package(pybind11 CONFIG QUIET)
if(pybind11_FOUND)
    pybind11_add_module(argus_core src/bindings.cpp)
    target_link_libraries(argus_core PRIVATE argus_core_lib)
    target_compile_features(argus_core PUBLIC cxx_std_20)
    message(STATUS "ARGUS-NEURO: pybind11 found, building Python extension 'argus_core'")
else()
    message(STATUS "ARGUS-NEURO: pybind11 not found, skipping Python extension "
                    "(set -Dpybind11_DIR=$(python3 -m pybind11 --cmakedir))")
endif()
