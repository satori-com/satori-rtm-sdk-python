# -*- coding: utf-8 -*-

from __future__ import print_function
import threading
import unittest

import satori.rtm.auth as auth
from satori.rtm.client import make_client

from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()


class TestAuth(unittest.TestCase):
    def test_misbehaving_auth_delegate(self):

        class BadDelegate(object):
            def start(this):
                return None

        with make_client(endpoint=endpoint, appkey=appkey) as client:
            auth_event = threading.Event()
            auth_delegate = BadDelegate()
            mailbox = []

            def auth_callback(auth_result):
                mailbox.append(auth_result)
                auth_event.set()

            client.authenticate(auth_delegate, auth_callback)

            if not auth_event.wait(60):
                raise RuntimeError('Auth never finished')

            self.assertEqual(type(mailbox[0]), auth.Error)
            self.assertEqual(
                mailbox[0].message,
                'auth_delegate returned None instead of an auth action')


if __name__ == '__main__':
    unittest.main()
