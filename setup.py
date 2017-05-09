from setuptools import setup, find_packages

setup(
    name="basejmpr",
    version='0.0.1',
    author="Edward Hope-Morley",
    author_email="opentastic@gmail.com",
    description="basejmpr is a tool for creating kvm instances",
    url="https://github.com/dosaboy/basejmpr",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "basejmpr = basejmpr.cli:main",
        ]
    }
)
