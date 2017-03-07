# -*- coding: utf-8 -*-

from __future__ import print_function
import six
import unittest

from satori.rtm.client import Client

from test.utils import make_channel_name, print_resource_usage
from test.utils import get_test_endpoint_and_appkey

message = 'hello'
channel = make_channel_name('pathologic')
endpoint, appkey = get_test_endpoint_and_appkey()
secret_key = b'FF6FFFCfB2f7F3fe0E627d9fE2DB2EcD'


class TestPathologicCases(unittest.TestCase):
    def test_rapid_stop_start(self):
        client = Client(endpoint=endpoint, appkey=appkey)
        for i in six.moves.range(100):
            client.start()
            client.stop()
        print_resource_usage()

    def test_many_queued_publishes(self):
        client = Client(endpoint=endpoint, appkey=appkey)
        for i in six.moves.range(1000000):
            client.publish(channel=channel, message=message)
        print_resource_usage()

    def test_many_idle_subscriptions(self):
        client = Client(endpoint=endpoint, appkey=appkey)
        for i in six.moves.range(10000):
            client.subscribe(channel='{0}.{1}'.format(channel, i))
        print_resource_usage()


if __name__ == '__main__':
    unittest.main()
