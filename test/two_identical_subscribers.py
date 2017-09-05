# -*- coding: utf-8 -*-

from __future__ import print_function
import time
import unittest

from satori.rtm.client import make_client

from test.utils import make_channel_name, sync_subscribe, sync_publish
from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()


class TestIdenticalSubscribers(unittest.TestCase):

    def _run(self, N):
        channel = make_channel_name('two_identical_subscribers')
        with make_client(endpoint=endpoint, appkey=appkey) as pub:
            with make_client(
                    endpoint=endpoint, appkey=appkey, protocol='cbor') as sub1:
                with make_client(endpoint=endpoint, appkey=appkey) as sub2:

                    origin = sync_publish(pub, channel, u'prime')

                    so1 = sync_subscribe(sub1, channel, {u'position': origin})
                    so2 = sync_subscribe(sub2, channel, {u'position': origin})

                    for i in range(N):
                        pub.publish(channel, i)

                    msgs1 = []
                    msgs2 = []
                    origin = time.time()
                    while time.time() < origin + 5:
                        msgs1 = so1.extract_received_messages()
                        msgs2 = so2.extract_received_messages()
                        if len(msgs1) == N + 1 and len(msgs2) == N + 1:
                            break
                        time.sleep(0.1)

                    self.assertEqual(msgs1, msgs2)

    def test_single_publisher_one_message(self):
        self._run(1)

    def test_single_publisher_few_messages(self):
        self._run(10)

    def test_single_publisher_lots_of_messages(self):
        self._run(1000)


if __name__ == '__main__':
    unittest.main()
