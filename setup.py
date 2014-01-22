#!/usr/bin/env python

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name = 'vimeo',
    version = '0.0.1',
    packages = find_packages(),
    author='Artlogic Media Limited',
    author_email='support@artlogic.net',
    description = """
This library provides a `vimeo` Python (2.5-2.7) module for interacting with the
Vimeo Advanced API (v2). It is heavily based on
(Vimeo's own PHP library)[https://github.com/vimeo/vimeo-php-lib] for the same
purpose.
    """.strip(),
    license = "MIT or GPLv3",
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv2+)',
        'License :: OSI Approved :: MIT License',
    ],
)
