#!/usr/bin/env python
# coding: utf-8

from setuptools import setup, find_packages


VERSION = '0.1.0'
REQS = []


setup(
    name='zs',
    version=VERSION,
    description='',
    license='MIT',
    packages=find_packages(),
    install_requires=REQS,
    include_package_data=True,
    zip_safe=False,
)
