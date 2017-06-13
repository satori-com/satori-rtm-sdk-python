#!/usr/bin/env python

from setuptools import setup, find_packages
import sys

py_modules =\
    ['satori.rtm.' + m for m in (
        'client',
        'auth',
        'connection')]

install_requires = ['certifi', 'enum34', 'six']

if sys.version_info < (2, 7, 9):
    install_requires.append('PyOpenSSL>=0.15')
    install_requires.append('backports.ssl>=0.0.9')

classifiers = [
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'License :: Other/Proprietary License',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    ]

setup(name='satori-rtm-sdk',
      version='1.1.0',
      description='Satori SDK',
      author='Satori Worldwide, Inc.',
      author_email='sdk@satori.com',
      url='https://www.satori.com/',
      packages=find_packages(exclude='ez_setup'),
      py_modules=py_modules,
      install_requires=install_requires,
      classifiers=classifiers
     )
