#!/usr/bin/env python3
"""
Setup script for Cloud-to-IaC Resource Analyzer

This allows the package to be installed with:
    pip install -e .

or built and distributed with:
    python setup.py sdist bdist_wheel
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
current_dir = Path(__file__).parent
readme_file = current_dir / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

# Runtime-only dependencies (dev tools such as pytest, black, flake8, mypy, sphinx
# live in requirements.txt for local development but must not be shipped to end users)
_DEV_PACKAGES = {"pytest", "pytest-cov", "black", "flake8", "mypy", "sphinx", "sphinx-rtd-theme"}

requirements_file = current_dir / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text(encoding="utf-8").split("\n")
        if line.strip()
        and not line.startswith("#")
        and line.split("==")[0].strip() not in _DEV_PACKAGES
    ]

setup(
    name="cloud-iac-analyzer",
    version="1.0.0",
    author="Automation Engineer",
    description="Analyze configuration drift between cloud resources and IaC declarations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/cloud-iac-analyzer",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: System :: Systems Administration",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "cloud-iac-analyzer=cloud_iac_analyzer.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
