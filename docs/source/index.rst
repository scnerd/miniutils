.. miniutils documentation master file, created by
   sphinx-quickstart on Tue Nov  7 12:37:22 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to miniutils's documentation!
=====================================

.. image:: https://coveralls.io/repos/github/scnerd/miniutils/badge.svg?branch=master
    :target: https://coveralls.io/github/scnerd/miniutils?branch=master

.. image:: https://travis-ci.org/scnerd/miniutils.svg?branch=master
    :target: https://travis-ci.org/scnerd/miniutils

.. image:: https://readthedocs.org/projects/miniutils/badge/?version=latest
    :target: http://miniutils.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   progress_bar
   caching
   python2
   misc


Overview
--------

This module provides numerous helper utilities for Python3.X code to add functionality with minimal code footprint. It has tools for the following tasks:

- Progress bars on serial loops and parallel mappings (leveraging the excellent ``tqdm`` library)
- Simple lazy-compute and caching of class properties, including dependency chaining
- Executing Python2 code from within a Python3 program
- More intuitive contract decorator (leveraging ``pycontracts``)



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
