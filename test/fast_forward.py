# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client

from test.utils import make_channel_name, sync_subscribe, ClientObserver
from test.utils import emulate_fast_forward, get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()
channel = make_channel_name('channel_error')


class TestFastForward(unittest.TestCase):

    def test_fast_forward(self):
        with make_client(endpoint=endpoint, appkey=appkey) as client:

            sync_subscribe(client, channel)
            co = ClientObserver()
            client.observer = co

            emulate_fast_forward(client, channel)
            client._queue.join()

            self.assertEqual([('on_fast_forward', channel)], co.log)


if __name__ == '__main__':
    unittest.main()