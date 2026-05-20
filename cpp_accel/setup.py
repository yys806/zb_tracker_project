from __future__ import annotations

import sys

from setuptools import Extension, setup

import pybind11


extra_compile_args = ["/O2"] if sys.platform.startswith("win") else ["-O3", "-std=c++17"]

ext_modules = [
    Extension(
        "morphology_ext",
        ["src/morphology_ext.cpp"],
        include_dirs=[pybind11.get_include()],
        language="c++",
        extra_compile_args=extra_compile_args,
    )
]


setup(
    name="morphology_ext",
    version="0.1.0",
    description="Binary morphology accelerator for the OrangePi tracking project",
    python_requires=">=3.10",
    install_requires=["numpy", "pybind11"],
    ext_modules=ext_modules,
)
