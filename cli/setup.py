#!/usr/bin/env python

from setuptools import setup

setup(name='satori-rtm-cli',
      version='1.0.1',
      description='Satori RTM CLI',
      author='Satori',
      author_email='sdk@satori.com',
      url='http://www.satori.com/',
      scripts=['satori_rtm_cli.py'],
      install_requires=['satori-rtm-sdk >=1.2.0', 'docopt'])
