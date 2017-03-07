#!/usr/bin/env python

from setuptools import setup, find_packages

py_modules =\
    ['satori.rtm.' + m for m in (
        'client',
        'auth',
        'connection')]

setup(name='satori-sdk-python',
      version='1.0.0',
      description='Satori SDK',
      author='Satori',
      author_email='sdk@satori.com',
      url='http://www.satori.com/',
      packages=find_packages(exclude='ez_setup'),
      py_modules=py_modules,
      install_requires=['certifi', 'enum34', 'six']
     )
