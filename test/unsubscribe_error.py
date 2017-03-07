# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client

from test.utils import ClientObserver, get_test_endpoint_and_appkey
from test.utils import make_channel_name, sync_subscribe

channel = make_channel_name('unsubscribe_error')
endpoint, appkey = get_test_endpoint_and_appkey()


class TestUnsubscribeError(unittest.TestCase):

    def test_double_unsubscribe_error(self):
        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            client.unsubscribe(channel)

            so = sync_subscribe(client, channel)
            client.unsubscribe(channel)

            so.wait_deleted()

            expected_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed',
                'on_leave_subscribed',
                'on_enter_unsubscribing',
                'on_leave_unsubscribing',
                'on_enter_unsubscribed',
                'on_deleted'
                ]
            self.assertEqual(so.log, expected_log)
            self.assertTrue(
                channel not in client._internal.subscriptions)

            client.unsubscribe(channel)

    def test_unsubscribe_nack_error(self):
        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            client.unsubscribe(channel)

            so = sync_subscribe(client, channel)

            old_received_message =\
                client._internal.connection.on_incoming_text_frame
            client._internal.connection.on_incoming_text_frame =\
                lambda *args: None

            client.unsubscribe(channel)

            client._queue.join()

            old_received_message(
                b'{"action":"rtm/unsubscribe/error","body":{},"id":1}')

            client._queue.join()

            expected_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed',
                'on_leave_subscribed',
                'on_enter_unsubscribing',
                'on_leave_unsubscribing',
                'on_enter_subscribed']

            self.assertEqual(so.log, expected_log)

    def test_wrong_unsubscribe_ack(self):
        with make_client(endpoint=endpoint, appkey=appkey) as client:

            client.observer = ClientObserver()
            sync_subscribe(client, channel)

            old_received_message =\
                client._internal.connection.on_incoming_text_frame
            client._internal.connection.on_incoming_text_frame =\
                lambda *args: None

            client.unsubscribe(channel)

            client._queue.join()

            old_received_message(
                b'{"action":"rtm/publish/ok","body":{},"id":1}')

            client._queue.join()

            client.observer.wait_connected()

            expected_log = [
                'on_leave_connected',
                'on_enter_awaiting',
                'on_leave_awaiting',
                'on_enter_connecting',
                'on_leave_connecting',
                'on_enter_connected',
                ]

            self.assertEqual(client.observer.log, expected_log)


if __name__ == '__main__':
    unittest.main()
