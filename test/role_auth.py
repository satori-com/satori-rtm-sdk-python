# -*- coding: utf-8 -*-

from __future__ import print_function
import threading
import unittest

import satori.rtm.auth as auth
from satori.rtm.client import make_client, Client

from test.utils import make_channel_name, sync_publish
from test.utils import get_test_endpoint_and_appkey, get_test_secret_key

message = 'hello'
channel = make_channel_name('$python.sdk')
endpoint, appkey = get_test_endpoint_and_appkey()
secret_key = get_test_secret_key()


class TestRoleAuth(unittest.TestCase):

    def test_ok_case(self):
        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            auth_event = threading.Event()
            auth_delegate = auth.RoleSecretAuthDelegate('superuser', secret_key)
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

    def test_auth_before_start(self):
        client = Client(
            endpoint=endpoint,
            appkey=appkey)

        auth_event = threading.Event()
        auth_delegate = auth.RoleSecretAuthDelegate('superuser', secret_key)
        mailbox = []

        def auth_callback(auth_result):
            if type(auth_result) == auth.Done:
                mailbox.append('Auth success')
                auth_event.set()
            else:
                mailbox.append('Auth failure: {0}'.format(auth_result))
                auth_event.set()

        client.authenticate(auth_delegate, auth_callback)

        client.start()

        if not auth_event.wait(60):
            raise RuntimeError('Auth never finished')

        self.assertEqual(mailbox, ['Auth success'])

        client.stop()
        client.dispose()

    def test_auth_error(self):

        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            auth_event = threading.Event()
            auth_delegate = auth.RoleSecretAuthDelegate('superuser', b'bad_key')
            mailbox = []

            def auth_callback(auth_result):
                if type(auth_result) == auth.Done:
                    mailbox.append('Auth success')
                    auth_event.set()
                else:
                    mailbox.append('Auth failure: {0}'.format(
                        auth_result.message))
                    auth_event.set()

            client.authenticate(auth_delegate, auth_callback)

            if not auth_event.wait(60):
                raise RuntimeError('Auth never finished')

            self.assertEqual(mailbox, ['Auth failure: Unauthenticated'])

    @unittest.skip('Need a channel that only a superuser has access to')
    def test_publish_to_restricted_channel(self):

        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            auth_event = threading.Event()
            auth_delegate = auth.RoleSecretAuthDelegate('superuser', secret_key)
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

            if not mailbox == ['Auth success']:
                raise RuntimeError(mailbox)

            sync_publish(client, channel, 'ohai')

    def test_publish_to_restricted_channel_while_not_authenticated(self):

        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            self.mailbox = []
            self.after_publish = threading.Event()

            def publish_callback(ack):
                self.mailbox.append(ack)
                self.after_publish.set()

            client.publish(channel, 'ohai', callback=publish_callback)

            if not self.after_publish.wait(20):
                raise RuntimeError("Publish timeout")

            self.assertEqual(
                self.mailbox,
                [{'action': 'rtm/publish/error',
                  'body': {
                      'error': 'authorization_denied',
                      'reason': 'Unauthorized'},
                  'id': 0}])

    def test_handshake_error(self):
        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            auth_event = threading.Event()
            auth_delegate = auth.RoleSecretAuthDelegate('waldo', secret_key)
            mailbox = []

            def auth_callback(auth_result):
                if type(auth_result) == auth.Done:
                    mailbox.append('Auth success')
                    auth_event.set()
                else:
                    mailbox.append('Auth failure: {0}'.format(
                        auth_result.message))
                    auth_event.set()

            client.authenticate(auth_delegate, auth_callback)

            if not auth_event.wait(60):
                raise RuntimeError('Auth never finished')

            self.assertEqual(
                mailbox,
                ['Auth failure: Unauthenticated'])


if __name__ == '__main__':
    unittest.main()
