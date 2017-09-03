#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import time

from satori.rtm.client import make_client, SubscriptionMode

endpoint = "YOUR_ENDPOINT"
appkey = "YOUR_APPKEY"


def main():
    import logging
    logging.basicConfig(level=logging.WARNING)

    class SubscriptionObserver(object):
        def on_enter_subscribed(self):
            print('Subscribed to: zebras')

        def on_subscription_data(self, pdu):
            for animal in pdu['messages']:
                print('Got animal {0}: {1}'.format(animal['who'], animal))

        def on_enter_failed(self, reason):
            print('Subscription failed:', reason, file=sys.stderr)

    with make_client(endpoint=endpoint, appkey=appkey) as client:
        print('Connected to Satori RTM!')

        observer = SubscriptionObserver()
        client.subscribe(
            u'zebras',
            SubscriptionMode.SIMPLE,
            observer,
            args={u'filter': u"select * from `animals` where `who` = 'zebra'"})

        print('Press CTRL-C to exit', file=sys.stderr)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
