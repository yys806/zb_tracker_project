from __future__ import annotations

from setuptools import Extension, setup

import pybind11


ext_modules = [
    Extension(
        "morphology_ext",
        ["src/morphology_ext.cpp"],
        include_dirs=[pybind11.get_include()],
        language="c++",
    )
]


setup(
    name="morphology_ext",
    version="0.1.0",
    description="Binary morphology accelerator for the OrangePi tracking project",
    ext_modules=ext_modules,
)

