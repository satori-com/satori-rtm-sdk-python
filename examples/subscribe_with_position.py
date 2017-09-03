#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
from threading import Event
import time

from satori.rtm.client import make_client, SubscriptionMode

endpoint = "YOUR_ENDPOINT"
appkey = "YOUR_APPKEY"


def main():
    import logging
    logging.basicConfig(level=logging.WARNING)

    class SubscriptionObserver(object):
        def on_enter_subscribed(self):
            print('Subscribed to: animals')

        def on_subscription_data(self, pdu):
            for animal in pdu['messages']:
                print('Got animal {0}: {1}'.format(animal['who'], animal))

        def on_enter_failed(self, reason):
            print('Subscription failed:', reason, file=sys.stderr)

    with make_client(endpoint=endpoint, appkey=appkey) as client:
        print('Connected to Satori RTM!')

        position_mailbox = []
        got_publish_reply = Event()

        def publish_callback(reply):
            position_mailbox.append(reply['body']['position'])
            got_publish_reply.set()

        client.publish(
            u'animals',
            {u'who': 'owl', u'coords': [54.321724, 48.396704]},
            callback=publish_callback)

        got_publish_reply.wait()

        observer = SubscriptionObserver()
        client.subscribe(
            u'animals',
            SubscriptionMode.SIMPLE,
            observer,
            args={u'position': position_mailbox[0]})

        print('Press CTRL-C to exit', file=sys.stderr)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
