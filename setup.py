#!/usr/bin/env setup

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name = 'vimeo',
    version = '0.0.0',
    packages = find_packages(exclude=['vimeo_tests']),
    author='Artlogic Media Limited',
    author_email='support@artlogic.net',
    description = open('README.md').read(),
    license = "MIT or GPLv3",
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv2+)',
        'License :: OSI Approved :: MIT License',
    ],
)
