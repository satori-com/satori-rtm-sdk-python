#!/usr/bin/env python

from setuptools import setup

setup(name='satori-rtm-cli',
      version='1.4.2',
      description='Satori RTM CLI',
      author='Satori',
      author_email='sdk@satori.com',
      url='http://www.satori.com/',
      entry_points={
          'console_scripts': ['satori-rtm-cli=satori_rtm_cli:main']
      },
      packages=['satori_rtm_cli'],
      install_requires=['satori-rtm-sdk >=1.2.1', 'docopt', 'toml', 'xdg'])
