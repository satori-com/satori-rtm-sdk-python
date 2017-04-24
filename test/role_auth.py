# -*- coding: utf-8 -*-

from __future__ import print_function
import threading
import unittest

import satori.rtm.auth as auth
from satori.rtm.client import make_client, Client
from satori.rtm.exceptions import AuthError

from test.utils import sync_publish
from test.utils import get_test_endpoint_and_appkey
from test.utils import get_test_role_name_secret_and_channel

message = 'hello'
endpoint, appkey = get_test_endpoint_and_appkey()
role, secret, channel = get_test_role_name_secret_and_channel()


class TestRoleAuth(unittest.TestCase):

    def test_ok_case(self):
        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            auth_event = threading.Event()
            auth_delegate = auth.RoleSecretAuthDelegate(role, secret)
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

    def test_shorter_ok_case(self):
        ad = auth.RoleSecretAuthDelegate(role, secret)
        with make_client(
                endpoint=endpoint,
                appkey=appkey,
                auth_delegate=ad):

            pass

    def test_shorter_fail_case(self):
        ad = auth.RoleSecretAuthDelegate('superuser', 'bad_secret')
        with self.assertRaises(AuthError):
            with make_client(
                    endpoint=endpoint,
                    appkey=appkey,
                    auth_delegate=ad):

                pass

    def test_auth_before_start(self):
        client = Client(
            endpoint=endpoint,
            appkey=appkey)

        auth_event = threading.Event()
        auth_delegate = auth.RoleSecretAuthDelegate(role, secret)
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

    def test_publish_to_restricted_channel(self):

        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            auth_event = threading.Event()
            auth_delegate = auth.RoleSecretAuthDelegate(role, secret)
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
            auth_delegate = auth.RoleSecretAuthDelegate('waldo', secret)
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
