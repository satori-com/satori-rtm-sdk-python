# -*- coding: utf-8 -*-

from __future__ import print_function
import threading
import unittest

from satori.rtm.client import make_client

from test.utils import get_test_endpoint_and_appkey, make_channel_name
from test.utils import sync_publish

endpoint, appkey = get_test_endpoint_and_appkey()
channel = make_channel_name('channel_search')


class TestChannelSearch(unittest.TestCase):
    @unittest.skip("Because backend")
    def test_channel_search(self):
        with make_client(endpoint=endpoint, appkey=appkey) as client:
            event = threading.Event()
            mailbox = []

            def callback(ack):
                mailbox.append(ack)
                if ack['action'] != 'rtm/search/data':
                    event.set()

            sync_publish(client, channel, 'ping')
            client.search('', callback=callback)

            event.wait(10)
            self.assertTrue(len(mailbox) > 0)
            last_pdu = mailbox[-1]

            self.assertEqual(last_pdu['action'], 'rtm/search/ok')
            for non_last_pdu in mailbox[:-1]:
                self.assertEqual(non_last_pdu['action'], 'rtm/search/data')

            result = []
            for pdu in mailbox:
                result += pdu['body']['channels']
            self.assertTrue(channel in result)


if __name__ == '__main__':
    unittest.main()