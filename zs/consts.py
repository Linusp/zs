import os

CONFIG_DIR = os.path.join(os.environ.get("HOME"), ".zs", "config")
DATA_DIR = os.path.join(os.environ.get("HOME"), ".zs", "data")


README_TEMPLATE = """{name}
=======

Support Python{version} or later

## Install

```shell
python setup.py install
```

## Develop

Create virtualenv and install dependencies:

```shell
make venv && make deps
```

Unit testing

```shell
make test
```
"""

SETUP_FILE_TEMPLATE = """#!/usr/bin/env python
# coding: utf-8

from setuptools import setup, find_packages


VERSION = '0.1.0'
REQS = []


setup(
    name='{name}',
    version=VERSION,
    description='',
    license='MIT',
    packages=find_packages(),
    install_requires=REQS,
    include_package_data=True,
    zip_safe=False,
)
"""

MAKEFILE_TEMPLATE = """lint: clean
\tflake8 {name} --format=pylint || true
test: lint
\tpy.test -vvv --cov {name} --cov-report term-missing --cov-report xml:cobertura.xml --junitxml=testresult.xml tests

clean:
\t- find . -iname "*__pycache__" | xargs rm -rf
\t- find . -iname "*.pyc" | xargs rm -rf
\t- rm cobertura.xml -f
\t- rm testresult.xml -f
\t- rm .coverage -f
\t- rm .pytest_cache/ -rf

venv:
\t- virtualenv --python=$(shell which python{version}) --prompt '<venv:{name}>' venv


lock-requirements:
\t- pip install pip-tools
\t- pip-compile --output-file requirements.txt requirements.in

deps:
\t- pip install -U pip setuptools
\t- pip install -r requirements.txt
"""  # noqa


SETUP_CFG = """[flake8]
max-line-length = 100
ignore = E201,E202

[pep8]
max-line-length = 100
ignore = E201,E202
"""

TEST_FILE_TEMPLATE = """import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from {name} import *


def test_init():
    assert True == True
"""

IGNORE_FILE_TEMPLATE = """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
*.egg-info/
.installed.cfg
*.egg

# PyInstaller
#  Usually these files are written by a python script from a template
#  before PyInstaller builds the exe, so as to inject date/other infos into it.
*.manifest
*.spec

# Django stuff:
*.log
local_settings.py

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# IPython Notebook
.ipynb_checkpoints

# pyenv
.python-version

# dotenv
.env

# virtualenv
env/
venv/
ENV/

# Spyder project settings
.spyderproject
"""
