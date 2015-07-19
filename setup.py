# -*- encoding: utf-8 -*-
# Copyright (c) 2015, Nicolas Despres

# Relevant documentation used when writing this file:
#   https://docs.python.org/3/library/distutils.html
#   http://www.diveinto.org/python3/packaging.html
#   http://www.scotttorborg.com/python-packaging/
# and of course several example projects such as: csvkit, nose or buildout.

from setuptools import setup
import os
import sys
import codecs

ROOT_DIR = os.path.dirname(__file__)

def read(*rnames):
    with codecs.open(os.path.join(ROOT_DIR, *rnames),
                     mode="r",
                     encoding="utf-8") as stream:
        return stream.read()

setup(
    name="hunittest",
    version="0.1.0",
    # We only have a single package to distribute and no individual modules
    packages=["hunittest"],
    py_modules=[],
    # We only depends on Python standard library.
    # Other dependencies are soft dependencies users can opt-in or not.
    install_requires=[],
    # Generate a command line interface driver.
    entry_points={
        'console_scripts': [
            "hunittest=hunittest.cli:sys_main",
        ],
    },
    # How to run the test suite.
    # TODO(Nicolas Despres): Maybe we should use hunittest itself here...
    test_suite='nose.collector',
    tests_require=['nose'],
    # What it does, who wrote it and where to find it.
    description="User friendly command line interface for unittest",
    long_description=read('README.rst'),
    author="Nicolas Despres",
    author_email='nicolas.despres@gmail.com',
    license="Simplified BSD",
    keywords='utility testing cli unittest',
    url='https://github.com/nicolasdespres/hunittest',
    # Pick some from https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
        'Topic :: Utilities',
    ],
)
