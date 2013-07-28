#!/usr/bin/env python
import os
from setuptools import setup

def read(filen):
    with open(os.path.join(os.path.dirname(__file__), filen), "r") as fp:
        return fp.read()
 
setup (
    name = "gitastic",
    version = "0.1",
    description="git-centric project management",
    long_description=read("README.md"),
    author="Alec Elton",
    author_email="alec.elton@gmail.com", # Removed to limit spam harvesting.
    url="http://github.com/basementcat/gitastic",
    packages=["gitastic", "tests"],
    test_suite="nose.collector",
    install_requires=["storm", "furl", "multiconfig", "bcrypt"],
    tests_require=["nose"]
)