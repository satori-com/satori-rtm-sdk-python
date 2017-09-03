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
        def __init__(self, sub_id):
            self._sub_id = sub_id

        def on_enter_subscribed(self):
            print('Established subscription {0}'.format(self._sub_id))

        def on_subscription_data(self, data):
            for message in data['messages']:
                print('Got a {0}: {1}'.format(self._sub_id, message))

        def on_enter_failed(self, reason):
            print(
                'Subscription {0} failed: {1}'.format(self._sub_id, reason),
                file=sys.stderr)

    with make_client(
            endpoint=endpoint, appkey=appkey) as client:
        print('Connected to Satori RTM!')

        zebra_view = u"select * from `animals` where who = 'zebra'"
        zebra_observer = SubscriptionObserver('zebra')
        count_view = u'select count(*) as count from `animals` group by who'
        count_observer = SubscriptionObserver('count')

        client.subscribe(
            u'zebras',
            SubscriptionMode.SIMPLE,
            zebra_observer,
            args={u'filter': zebra_view})
        client.subscribe(
            u'count',
            SubscriptionMode.SIMPLE,
            count_observer,
            args={u'filter': count_view})

        print('Press CTRL-C to exit', file=sys.stderr)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
