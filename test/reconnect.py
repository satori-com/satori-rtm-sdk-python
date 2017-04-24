# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest
import threading

from satori.rtm.client import Client
import satori.rtm.auth as auth
import satori.rtm.connection

from test.utils import ClientObserver, emulate_websocket_disconnect
from test.utils import get_test_endpoint_and_appkey
from test.utils import get_test_role_name_secret_and_channel
from test.utils import make_channel_name, sync_publish, sync_subscribe

endpoint, appkey = get_test_endpoint_and_appkey()
role, secret, restricted_channel = get_test_role_name_secret_and_channel()


class TestReconnect(unittest.TestCase):

    def test_reconnect(self):
        client = Client(
            endpoint=endpoint, appkey=appkey,
            reconnect_interval=1, fail_count_threshold=1)
        client.observer = ClientObserver()

        client.start()
        client.observer.wait_connected('First connect timeout')
        emulate_websocket_disconnect(client)
        client.observer.wait_disconnected()
        client.observer.wait_connected('Second connect timeout')
        client.stop()
        client.observer.wait_stopped()
        client.dispose()

        expected_log = [
            'on_leave_stopped',
            'on_enter_connecting',
            'on_leave_connecting',
            'on_enter_connected',
            'on_leave_connected',
            'on_enter_awaiting',
            'on_leave_awaiting',
            'on_enter_connecting',
            'on_leave_connecting',
            'on_enter_connected',
            'on_leave_connected',
            'on_enter_stopping',
            'on_leave_stopping',
            'on_enter_stopped',
            'on_leave_stopped',
            'on_enter_disposed']

        self.assertEqual(client.observer.log, expected_log)

    def test_reconnect_zero_threshold(self):
        client = Client(
            endpoint=endpoint, appkey=appkey,
            reconnect_interval=1, fail_count_threshold=0)
        client.observer = ClientObserver()

        client.start()
        client.observer.wait_connected()

        client._internal._endpoint = 'ws://bogus'
        emulate_websocket_disconnect(client)

        client.observer.wait_disconnected()
        client.observer.wait_stopped()
        client.dispose()

        expected_log = [
            'on_leave_stopped',
            'on_enter_connecting',
            'on_leave_connecting',
            'on_enter_connected',
            'on_leave_connected',
            'on_enter_awaiting',
            'on_leave_awaiting',
            'on_enter_connecting',
            'on_leave_connecting',
            'on_enter_stopped',
            'on_leave_stopped',
            'on_enter_disposed']

        self.assertEqual(client.observer.log, expected_log)

    def test_automatic_resubscribe(self):
        client = Client(
            endpoint=endpoint, appkey=appkey,
            reconnect_interval=1)
        client.observer = ClientObserver()

        channel = make_channel_name('resubscribe')

        client.start()
        client.observer.wait_connected('First connect timeout')
        so = sync_subscribe(client, channel)
        sync_publish(client, channel, 'first-message')
        first_channel_data = so.wait_for_channel_data()
        emulate_websocket_disconnect(client)
        so.wait_not_subscribed()
        client.observer.wait_disconnected()
        client.observer.wait_connected('Second connect timeout')
        so.wait_subscribed('Second subscribe timeout')
        sync_publish(client, channel, 'second-message')
        second_channel_data = so.wait_for_channel_data()
        client.unsubscribe(channel)
        so.wait_not_subscribed()
        client.stop()
        client.dispose()

        expected_log = [
            'on_leave_unsubscribed',
            'on_enter_subscribing',
            'on_leave_subscribing',
            'on_enter_subscribed',
            ('data', first_channel_data),
            # point of disconnect
            'on_leave_subscribed',
            'on_enter_unsubscribed',
            # point of reconnect
            'on_leave_unsubscribed',
            'on_enter_subscribing',
            'on_leave_subscribing',
            'on_enter_subscribed',
            ('data', second_channel_data),
            'on_leave_subscribed',
            'on_enter_unsubscribing',
            'on_leave_unsubscribing',
            'on_enter_unsubscribed',
            'on_deleted']

        self.assertEqual(so.log, expected_log)

    def test_manual_resubscribe(self):
        client = Client(
            endpoint=endpoint, appkey=appkey)
        client.observer = ClientObserver()

        channel = make_channel_name('resubscribe')

        client.start()
        client.observer.wait_connected('First connect timeout')
        so = sync_subscribe(client, channel)
        sync_publish(client, channel, 'first-message')
        first_channel_data = so.wait_for_channel_data()
        emulate_websocket_disconnect(client)
        so.wait_not_subscribed()
        client.observer.wait_disconnected()
        client.start()
        client.observer.wait_connected('Second connect timeout')
        so.wait_subscribed('Second subscribe timeout')
        sync_publish(client, channel, 'second-message')
        second_channel_data = so.wait_for_channel_data()
        client.unsubscribe(channel)
        so.wait_not_subscribed()
        client.stop()
        client.dispose()

        expected_log = [
            'on_leave_unsubscribed',
            'on_enter_subscribing',
            'on_leave_subscribing',
            'on_enter_subscribed',
            ('data', first_channel_data),
            # point of disconnect
            'on_leave_subscribed',
            'on_enter_unsubscribed',
            # point of reconnect
            'on_leave_unsubscribed',
            'on_enter_subscribing',
            'on_leave_subscribing',
            'on_enter_subscribed',
            ('data', second_channel_data),
            'on_leave_subscribed',
            'on_enter_unsubscribing',
            'on_leave_unsubscribing',
            'on_enter_unsubscribed',
            'on_deleted']

        self.assertEqual(so.log, expected_log)

    def test_reauth(self):
        client = Client(endpoint=endpoint, appkey=appkey)
        auth_delegate = auth.RoleSecretAuthDelegate(role, secret)
        auth_event = threading.Event()
        mailbox = []

        co = ClientObserver()
        client.observer = co
        client.start()

        co.wait_connected()

        def auth_callback(auth_result):
            if type(auth_result) == auth.Done:
                mailbox.append('Auth success')
                auth_event.set()
            else:
                mailbox.append('Auth failure: {0}'.format(
                    auth_result.message))
                auth_event.set()
        client.authenticate(auth_delegate, auth_callback)

        if not auth_event.wait(30):
            raise RuntimeError("Auth timeout")

        self.assertEqual(mailbox, ['Auth success'])

        so = sync_subscribe(client, restricted_channel)

        sync_publish(client, restricted_channel, 'before disconnect')
        first_data = so.wait_for_channel_data()
        self.assertEqual(first_data['messages'], ['before disconnect'])

        emulate_websocket_disconnect(client)

        co.wait_disconnected()
        co.wait_connected()

        sync_publish(client, restricted_channel, 'after reconnect')
        second_data = so.wait_for_channel_data()
        self.assertEqual(second_data['messages'], ['after reconnect'])

        client.stop()
        client.dispose()

    def test_missing_pong(self):
        satori.rtm.connection.ping_interval_in_seconds = 1
        client = Client(endpoint=endpoint, appkey=appkey)
        co = ClientObserver()
        client.observer = co

        client.start()
        client.observer.wait_connected('First connect timeout')

        # emulate the absence of server pongs and silence in the socket
        client._internal.connection.on_ws_ponged = lambda: None
        client._internal.connection.last_ponged_time = 0
        client._internal.connection.on_ws_pong = lambda x, y: None

        client.observer.wait_disconnected('First disconnect timeout')
        client.observer.wait_connected('Second connect timeout')

        client.stop()
        client.dispose()
        satori.rtm.connection.ping_interval_in_seconds = 60


if __name__ == '__main__':
    unittest.main()
