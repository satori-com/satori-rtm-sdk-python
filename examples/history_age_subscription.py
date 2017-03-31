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

        class SubscriptionObserver(object):
            def __init__(self, sub_id):
                self._sub_id = sub_id

            def on_enter_subscribed(self):
                print('Established subscription {0}'.format(self._sub_id))

            def on_leave_subscribed(self):
                print('Lost subscription to {0}'.format(self._sub_id))

            def on_subscription_data(self, data):
                for message in data['messages']:
                    print('{0}: {1}'.format(self._sub_id, message))

        subscription_observer = SubscriptionObserver(channel)

        client.subscribe(
            channel,
            SubscriptionMode.SIMPLE,
            subscription_observer,
            args={'history': {'age': 60}})  # in seconds

        print('Sleeping')
        time.sleep(10)
        print('Enough sleep')

        client.unsubscribe(channel)


if __name__ == '__main__':
    main()