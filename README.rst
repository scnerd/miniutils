.. image:: https://coveralls.io/repos/github/scnerd/miniutils/badge.svg?branch=master
    :target: https://coveralls.io/github/scnerd/miniutils?branch=master

.. image:: https://travis-ci.org/scnerd/miniutils.svg?branch=master
    :target: https://travis-ci.org/scnerd/miniutils

Overview
--------

Full documentation for this module is available over at `ReadTheDocs <http://miniutils.readthedocs.io/>`_.

This module provides numerous helper utilities for Python3.X code to add functionality with minimal code footprint. It has tools for the following tasks:

- Progress bars on serial loops and parallel mappings (leveraging the excellent ``tqdm`` library)
- Simple lazy-compute and caching of class properties, including dependency chaining
- Executing Python2 code from within a Python3 program
- More intuitive contract decorator (leveraging ``pycontracts``)
