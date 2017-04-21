#!/usr/bin/env python

from setuptools import setup

setup(name='satori-rtm-cli',
      version='1.0.0',
      description='Satori RTM CLI',
      author='Satori',
      author_email='sdk@satori.com',
      url='http://www.satori.com/',
      scripts=['satori_rtm_cli.py'],
      install_requires=['satori-sdk-python >=1.0.3', 'docopt'])
