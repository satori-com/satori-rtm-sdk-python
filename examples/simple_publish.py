#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import time

from satori.rtm.client import make_client
from test.utils import get_test_endpoint_and_appkey

message = 'hello'
channel = 'whatever'
endpoint, appkey = get_test_endpoint_and_appkey()


def main():

    global channel
    global message
    if len(sys.argv) > 1:
        channel = sys.argv[1]

    if len(sys.argv) > 2:
        message = sys.argv[2]

    print('Creating satori client')
    with make_client(
            endpoint=endpoint, appkey=appkey) as client:

        print('Publishing a message')
        client.publish(channel, message=message)

        print('Sleeping')
        time.sleep(1)

        print('Publishing another message')
        client.publish(channel, message=message)

        print('Sleeping some more')
        time.sleep(1)


if __name__ == '__main__':
    main()
