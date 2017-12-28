#!/usr/bin/env python

from setuptools import setup

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
This is a debugging and exploration tool for `Satori <https://www.satori.com>`_ RTM.

See `README <https://github.com/satori-com/satori-rtm-sdk-python/tree/master/cli>`_
'''

setup(
    name='satori-rtm-cli',
    version='1.5.3',
    description='Satori RTM CLI',
    long_description=long_description,
    author='Satori',
    author_email='sdk@satori.com',
    url='http://www.satori.com/',
    entry_points={
        'console_scripts': ['satori-rtm-cli=satori_rtm_cli:main']
    },
    packages=['satori_rtm_cli'],
    install_requires=['satori-rtm-sdk >=1.5.0', 'docopt', 'toml', 'xdg>=1.0.4,<2', 'cbor2'],
    classifiers=classifiers,
    keywords='satori',
    license='Proprietary',
    zip_safe=False)
