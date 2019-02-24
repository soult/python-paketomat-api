#!/usr/bin/env python
# encoding=utf-8

from distutils.core import setup

setup(
    name="python-paketomat-api",
    version="0.1.0a2",
    description="Python3 library for interacting with the GW Paketomat as a registered customer",
    long_description="A Python3 library for interacting with the GW (Gebrüder Weiss) Web.Paketomat application. It supports creating new shipments and inspecting existing shipments. NB: This is not a shipment tracking library - it requires an account with GW.",
    author="David Triendl",
    author_email="david@triendl.name",
    packages=["paketomat"],
    python_requires=">=3.4.0",
    install_requires=["requests>=2.0.0"],
)
