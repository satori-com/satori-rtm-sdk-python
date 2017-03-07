# -*- coding: utf-8 -*-

from __future__ import print_function
import threading
import unittest

import satori.rtm.auth as auth
from satori.rtm.client import make_client

from test.utils import make_channel_name, get_test_endpoint_and_appkey

message = 'hello'
channel = make_channel_name('test-auth-channel.python')
endpoint, appkey = get_test_endpoint_and_appkey()


class TestDummyAuth(unittest.TestCase):
    def test_ok_case(self):
        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            auth_event = threading.Event()
            auth_delegate = auth.AuthDelegate()
            mailbox = []

            def auth_callback(auth_result):
                if type(auth_result) == auth.Done:
                    mailbox.append('Auth success')
                    auth_event.set()
                else:
                    mailbox.append('Auth failure: {0}'.format(auth_result))
                    auth_event.set()

            client.authenticate(auth_delegate, auth_callback)

            if not auth_event.wait(60):
                raise RuntimeError('Auth never finished')

            self.assertEqual(mailbox, ['Auth success'])


if __name__ == '__main__':
    unittest.main()
