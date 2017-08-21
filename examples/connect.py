#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

from satori.rtm.client import make_client

endpoint = "YOUR_ENDPOINT"
appkey = "YOUR_APPKEY"


def main():
    import logging
    logging.basicConfig(level=logging.WARNING)

    with make_client(endpoint=endpoint, appkey=appkey) as client:
        print('Connected to Satori RTM!')


if __name__ == '__main__':
    main()
