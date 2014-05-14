#!/usr/bin/env python
import os
from setuptools import setup

def read(filen):
    with open(os.path.join(os.path.dirname(__file__), filen), "r") as fp:
        return fp.read()
 
setup (
    name = "lunchroom",
    version = "0.1",
    description="Manage lunches and impromptu events",
    long_description=read("README.md"),
    author="Alec Elton",
    author_email="alec.elton@gmail.com",
    url="",
    packages=["lunchroom", "tests"],
    test_suite="nose.collector",
    install_requires=["bottle", "bcrypt"],
    tests_require=["nose"]
)