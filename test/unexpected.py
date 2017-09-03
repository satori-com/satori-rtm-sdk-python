# -*- coding: utf-8 -*-

from __future__ import print_function
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

            client._internal.connection.on_incoming_json(
                {u'action': u'rtm/subscription/data',
                 u'body':
                 {u'subscription_id': channel,
                  u'position': u'1',
                  u'messages': [u'spam', u'spam', u'spam']}})
            # TODO check that on_error callback is called

    def test_unexpected_channel_error(self):

        with make_client(
                endpoint=endpoint,
                appkey=appkey) as client:

            client._internal.connection.on_incoming_json(
                {u'action': u'rtm/subscription/error',
                 u'body':
                 {u'subscription_id': channel,
                  u'error': u'oh well'}})

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

    def test_exception_in_subscription_state_change_callback(self):

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
                args={u'position': '123'})
            so.wait_deleted()
            client.unsubscribe(channel)
            client._queue.join()

            if not exit.wait(20):
                raise RuntimeError('Timeout')

    def test_exception_in_subscription_data_callback(self):

        observer = ClientObserver()

        with make_client(
                endpoint=endpoint,
                appkey=appkey,
                observer=observer) as client:

            class CrashyObserver(SubscriptionObserver):
                def on_subscription_data(this, data):
                    SubscriptionObserver.on_subscription_data(this, data)
                    raise ValueError('Error in on_subscription_data')

            observer.stopped.clear()
            so = CrashyObserver()
            client.subscribe(channel, SubscriptionMode.SIMPLE, so)
            so.wait_subscribed()
            client.publish(channel, 'message')
            observer.wait_stopped()

    def test_exception_in_solicited_pdu_callback(self):

        observer = ClientObserver()

        with make_client(
                endpoint=endpoint,
                appkey=appkey,
                observer=observer) as client:

            def crashy(ack):
                print(ack["no-such-field"])

            observer.stopped.clear()
            client.publish(channel, 'message', callback=crashy)
            observer.wait_stopped()


if __name__ == '__main__':
    unittest.main()
