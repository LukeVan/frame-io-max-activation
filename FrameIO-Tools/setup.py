from setuptools import setup, find_packages

setup(
    name="frame-io-v4-cli",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
        "python-dotenv>=0.19.0",
        "requests>=2.26.0",
        "rich>=10.0.0",
    ],
    entry_points={
        "console_scripts": [
            "fio=fio.cli:cli",
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A CLI tool for interacting with Frame.io V4 API",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/frame-io-v4-cli",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
) 