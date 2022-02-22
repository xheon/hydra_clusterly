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
    url="https://github.com/facebookincubator/submitit",
    packages=find_namespace_packages(include=["hydra_plugins.*"]),
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 4 - Beta",
    ],
    install_requires=[
        "hydra-core>=1.1.0.dev7",
        "submitit>=1.3.3",
        "hydra-submitit-launcher>=1.1.6"
    ],
    include_package_data=True,
)
