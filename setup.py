#!/usr/bin/env setup

try:
    from setuptools import setup
except ImportError:
    try:
        from ez_setup import use_setuptools
        use_setuptools()
        from setuptools import setup
    except ImportError:
        # Finally, fall back to disutils
        from distutils.core import setup

setup(
    name = 'vimeo-py-lib',
    version = '0.0.0',
    py_modules = [
        'vimeo',
    ],
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
