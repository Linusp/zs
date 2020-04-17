#!/usr/bin/env python
# coding: utf-8

from setuptools import setup, find_packages


VERSION = '0.3.0'
REQS = [
    'click',
    'pysocks',
    'telethon',
    'python-dateutil',
    'peewee',
    'requests',
]


setup(
    name='zs',
    version=VERSION,
    description='',
    license='MIT',
    packages=find_packages(),
    install_requires=REQS,
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'zs-tg=zs.cli:telegram',
            'zs-rss=zs.cli:rss',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',      # Define that your audience are developers
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    data_files=[('', ['zs/rss/kz_scenario_template.json',
                      'zs/rss/efb_scenario_template.json'])],

)
