#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import time

from satori.rtm.client import make_client, SubscriptionMode
from test.utils import get_test_endpoint_and_appkey

channel = 'my_channel'
endpoint, appkey = get_test_endpoint_and_appkey()


def main():

    global channel
    if len(sys.argv) > 1:
        channel = sys.argv[1]

    print('Creating satori client')
    with make_client(
            endpoint=endpoint, appkey=appkey) as client:

        print('Subscribing to a channel')

        class SubscriptionObserver(object):
            def on_subscription_data(self, data):
                for message in data['messages']:
                    print('Client got message {0}'.format(message))

        subscription_observer = SubscriptionObserver()
        client.subscribe(
            channel,
            SubscriptionMode.ADVANCED,
            subscription_observer)

        print('Sleeping')
        time.sleep(11)
        print('Enough sleep')

        print('Unsubscribing from a channel')
        client.unsubscribe(channel)


if __name__ == '__main__':
    main()
