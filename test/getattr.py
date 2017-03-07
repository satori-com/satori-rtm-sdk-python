# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client, SubscriptionMode
from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()


class TestGetattrErrors(unittest.TestCase):
    def test_client_getattr(self):
        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            self.assertRaises(AttributeError, lambda: client.bogus())

    def test_subscription_getattr(self):
        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            client.subscribe(
                'test_getattr',
                SubscriptionMode.ADVANCED,
                None)

            subs = list(client._internal.subscriptions.items())

            for _, subscription in subs:
                self.assertRaises(AttributeError, lambda: subscription.bogus())


if __name__ == '__main__':
    unittest.main()
