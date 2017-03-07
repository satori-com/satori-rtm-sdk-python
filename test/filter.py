# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client, SubscriptionMode

from test.utils import SubscriptionObserver
from test.utils import get_test_endpoint_and_appkey
from test.utils import make_channel_name, sync_publish

endpoint, appkey = get_test_endpoint_and_appkey()
channel = make_channel_name('two_clients')


class TestFilter(unittest.TestCase):
    def test_filter(self):
        with make_client(endpoint=endpoint, appkey=appkey) as client:
            ch = make_channel_name('filter')
            so = SubscriptionObserver()
            mode = SubscriptionMode.RELIABLE
            args = {'filter': 'select test from ' + ch}
            client.subscribe(ch, mode, so, args=args)
            so.wait_subscribed()

            sync_publish(client, ch, {'test': 42, 'unused': 1})
            message = so.wait_for_channel_data()['messages'][0]
            self.assertEqual(message, {'test': 42})

            sync_publish(client, ch, {'unused': 1})
            message = so.wait_for_channel_data()['messages'][0]
            self.assertEqual(message, {'test': None})


if __name__ == '__main__':
    unittest.main()