# -*- coding: utf-8 -*-

from __future__ import print_function
import time
import unittest

from satori.rtm.client import make_client

from test.utils import make_channel_name, sync_subscribe, sync_publish
from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()
channel = make_channel_name('two_identical_subscribers')


class TestIdenticalSubscribers(unittest.TestCase):
    def test_single_publisher_few_messages(self):

        with make_client(endpoint=endpoint, appkey=appkey) as pub:
            with make_client(endpoint=endpoint, appkey=appkey) as sub1:
                with make_client(endpoint=endpoint, appkey=appkey) as sub2:

                    origin = sync_publish(pub, channel, 'prime')

                    so1 = sync_subscribe(sub1, channel, {'position': origin})
                    so2 = sync_subscribe(sub2, channel, {'position': origin})

                    for i in range(10):
                        pub.publish(channel, i)

                    time.sleep(5)

                    self.assertEqual(
                        so1.extract_received_messages(),
                        so2.extract_received_messages())

    def test_single_publisher_lots_of_messages(self):

        with make_client(endpoint=endpoint, appkey=appkey) as pub:
            with make_client(endpoint=endpoint, appkey=appkey) as sub1:
                with make_client(endpoint=endpoint, appkey=appkey) as sub2:

                    origin = sync_publish(pub, channel, 'prime')

                    so1 = sync_subscribe(sub1, channel, {'position': origin})
                    so2 = sync_subscribe(sub2, channel, {'position': origin})

                    for i in range(1000):
                        pub.publish(channel, i)

                    time.sleep(5)

                    self.assertEqual(
                        so1.extract_received_messages(),
                        so2.extract_received_messages())


if __name__ == '__main__':
    unittest.main()
