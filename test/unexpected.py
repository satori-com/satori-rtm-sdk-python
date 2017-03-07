# -*- coding: utf-8 -*-

from __future__ import print_function
import json
import unittest

import threading
from satori.rtm.client import make_client, SubscriptionMode

from test.utils import make_channel_name, ClientObserver, SubscriptionObserver
from test.utils import get_test_endpoint_and_appkey

message = 'hello'
channel = make_channel_name('whatever')
endpoint, appkey = get_test_endpoint_and_appkey()
secret_key = b'FF6FFFCfB2f7F3fe0E627d9fE2DB2EcD'


class TestUnexpected(unittest.TestCase):
    def test_unexpected_channel_data(self):

        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            client._internal.connection.on_incoming_text_frame(
                json.dumps({
                    'action': 'rtm/subscription/data',
                    'body': {
                        'subscription_id': channel,
                        'position': '1',
                        'messages': ['spam', 'spam', 'spam']}}))
            # TODO check that on_error callback is called

    def test_unexpected_channel_error(self):

        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            client._internal.connection.on_incoming_text_frame(
                json.dumps({
                    'action': 'rtm/subscription/error',
                    'body': {
                        'subscription_id': channel,
                        'error': 'oh well'}}))

            # TODO check that on_error callback is called

    def test_failed_connect(self):

        def bad_connect():
            with make_client(
                    endpoint='ws://qwerty:9999',
                    appkey=appkey,
                    reconnect_interval=0, fail_count_threshold=2):

                pass

        self.assertRaises(RuntimeError, bad_connect)

    def test_exception_in_client_state_callback(self):

        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            exit = threading.Event()

            class CrashyObserver(ClientObserver):
                def on_enter_stopped(this):
                    ClientObserver.on_enter_stopped(this)
                    client.dispose()
                    raise ValueError('Division by zero')

                def on_enter_disposed(this):
                    this.log.append('on_enter_disposed')
                    exit.set()

            co = CrashyObserver()
            client.observer = co
            client.stop()
            if not exit.wait(20):
                raise RuntimeError('Timeout')

    def test_exception_in_subscription_callback(self):

        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            exit = threading.Event()

            class CrashyObserver(SubscriptionObserver):
                def on_deleted(this):
                    SubscriptionObserver.on_deleted(this)
                    exit.set()
                    raise ValueError('Error in on_deleted')

                def on_enter_subscribing(this):
                    SubscriptionObserver.on_enter_subscribing(this)
                    raise ValueError('Error in on_enter_subscribing')

            so = CrashyObserver()
            client.subscribe(channel, SubscriptionMode.ADVANCED, so)
            so.wait_subscribed()
            client.unsubscribe(channel)
            client.subscribe(
                channel,
                SubscriptionMode.ADVANCED,
                CrashyObserver())
            client.unsubscribe(channel)
            client.subscribe(
                channel,
                SubscriptionMode.ADVANCED,
                SubscriptionObserver(),
                args={'position': '123'})
            so.wait_deleted()
            client.unsubscribe(channel)

            if not exit.wait(20):
                raise RuntimeError('Timeout')


if __name__ == '__main__':
    unittest.main()
