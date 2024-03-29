from pathlib import Path

from read_version import read_version
from setuptools import find_namespace_packages, setup

setup(
    name="hydra-clusterly",
    version=read_version("hydra_plugins/hydra_clusterly", "__init__.py"),
    author="Manuel Dahnert",
    author_email="manuel.dahnert@gmail.com",
    description="Customized slurm launcher",
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/xheon/hydra_clusterly",
    packages=find_namespace_packages(include=["hydra_plugins.*"]),
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "hydra-core>=1.1.0.dev7",
        "submitit>=1.3.3",
        "hydra-submitit-launcher>=1.1.6",
        "sysrsync",
        "tailhead"
    ],
    include_package_data=True,
)
