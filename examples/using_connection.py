#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import threading
from satori.rtm.connection import Connection

from test.utils import get_test_endpoint_and_appkey
endpoint, appkey = get_test_endpoint_and_appkey()
channel = 'test.channel'
message = 'test_message'
timeout = 20


def main():
    connection = Connection(endpoint, appkey, delegate=None)

    after_receive = threading.Event()

    class ConnectionDelegate(object):
        def on_connection_closed(self):
            print('connection closed')

        def on_internal_error(self, error):
            print('internal error', error)

        def on_subscription_data(self, data):
            print('data:', data)
            after_receive.set()

    connection.delegate = ConnectionDelegate()
    connection.start()

    position = connection.publish_sync(channel, message)
    connection.subscribe_sync(channel, {'position': position})

    if not after_receive.wait(timeout):
        raise RuntimeError(
            "Expected channel data hasn't arrived in reasonable time")


if __name__ == '__main__':
    main()
