#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import threading
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
        subscribed_event = threading.Event()

        class SubscriptionObserver(object):
            def on_enter_subscribed(self):
                subscribed_event.set()
                print('Established subscription to {0}'.format(channel))

            def on_leave_subscribed(self):
                print('Lost subscription to {0}'.format(channel))

            def on_subscription_data(self, data):
                for message in data['messages']:
                    print('Client got message {0}'.format(message))

        subscription_observer = SubscriptionObserver()
        client.subscribe(
            channel,
            SubscriptionMode.SIMPLE,
            subscription_observer)

        if not subscribed_event.wait(10):
            print("Couldn't establish subscription in time")
            sys.exit(1)

        print('Sleeping')
        time.sleep(10)
        print('Enough sleep')

        print('Unsubscribing from a channel')
        client.unsubscribe(channel)


if __name__ == '__main__':
    main()
