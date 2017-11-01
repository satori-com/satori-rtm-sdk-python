#!/usr/bin/env python

from setuptools import setup, find_packages
import sys

install_requires = ['cbor2', 'certifi', 'enum34', 'requests', 'six']

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

long_description = '''
RTM is the realtime messaging service at the core of the
`Satori platform <https://www.satori.com>`_.

Python SDK makes it more convenient to use Satori RTM
from `Python programming language <https://www.python.org>`_.
'''

setup(
    name='satori-rtm-sdk',
    version='1.5.0',
    description='Python SDK for Satori RTM',
    long_description=long_description,
    author='Satori Worldwide, Inc.',
    author_email='sdk@satori.com',
    url='https://www.satori.com/',
    packages=find_packages(exclude=['doc', 'test', 'examples', 'tutorials']),
    install_requires=install_requires,
    classifiers=classifiers,
    license='Proprietary',
    keywords=['satori'],
    zip_safe=True)
