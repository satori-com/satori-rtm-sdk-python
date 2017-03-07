# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import Client, SubscriptionMode

from test.utils import ClientObserver, SubscriptionObserver
from test.utils import make_channel_name, sync_publish
from test.utils import get_test_endpoint_and_appkey

channel = make_channel_name('unsubscribe_error')
endpoint, appkey = get_test_endpoint_and_appkey()


class TestSubscribeWhileDisconnected(unittest.TestCase):
    def test_before_start(self):
        client = Client(endpoint=endpoint, appkey=appkey)
        co = ClientObserver()
        client.observer = co
        so = SubscriptionObserver()
        client.subscribe(
            channel,
            SubscriptionMode.ADVANCED,
            subscription_observer=so)
        client.start()
        co.wait_connected()
        sync_publish(client, channel, 'message')
        channel_data = so.wait_for_channel_data()
        self.assertEqual(channel_data['messages'], ['message'])
        client.stop()
        co.wait_stopped()


if __name__ == '__main__':
    unittest.main()
