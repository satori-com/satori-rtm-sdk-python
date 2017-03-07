# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client, SubscriptionMode

from test.utils import ClientObserver, SubscriptionObserver
from test.utils import make_channel_name, get_test_endpoint_and_appkey

channel = make_channel_name('subscribe_error')
endpoint, appkey = get_test_endpoint_and_appkey()


class TestInternalError(unittest.TestCase):

    def test_internal_error(self):
        with make_client(
                endpoint=endpoint, appkey=appkey, reconnect_interval=10)\
                as client:

            client.observer = ClientObserver()
            old_received_message =\
                client._internal.connection.on_incoming_text_frame
            client._internal.connection.on_incoming_text_frame =\
                lambda *args: None

            so = SubscriptionObserver()
            client.subscribe(
                'test_internal_error',
                SubscriptionMode.ADVANCED,
                so)

            old_received_message(b"not-a-json-object")

            client._queue.join()

            expected_log = [
                'on_leave_connected',
                'on_enter_awaiting']

            self.assertEqual(client.observer.log, expected_log)

    def test_pdu_with_no_body(self):
        with make_client(
                endpoint=endpoint, appkey=appkey, reconnect_interval=10)\
                as client:
            client.observer = ClientObserver()

            client._internal.connection.on_incoming_text_frame(
                b'{"action":"rtm/read/ok", "id":42}')

            client._queue.join()

            expected_log = [
                'on_leave_connected',
                'on_enter_awaiting']

            self.assertEqual(client.observer.log, expected_log)

    def test_pdu_with_no_action(self):
        with make_client(
                endpoint=endpoint, appkey=appkey, reconnect_interval=10)\
                as client:
            client.observer = ClientObserver()

            client._internal.connection.on_incoming_text_frame(
                b'{"body":{}, "id":42}')

            client._queue.join()

            expected_log = [
                'on_leave_connected',
                'on_enter_awaiting']

            self.assertEqual(client.observer.log, expected_log)

    def test_ack_with_no_id(self):
        with make_client(
                endpoint=endpoint, appkey=appkey, reconnect_interval=10)\
                as client:
            client.observer = ClientObserver()

            client._internal.connection.on_incoming_text_frame(
                b'{"action":"rtm/publish/ok", "body":{}}')

            client._queue.join()

            expected_log = [
                'on_leave_connected',
                'on_enter_awaiting']

            self.assertEqual(client.observer.log, expected_log)

    def test_unsolicited_error(self):
        with make_client(
                endpoint=endpoint, appkey=appkey, reconnect_interval=10)\
                as client:
            client.observer = ClientObserver()

            client._internal.connection.on_incoming_text_frame(
                b'{"action":"/error", "body":{"error":"bad"}}')

            client._queue.join()

            expected_log = [
                'on_leave_connected',
                'on_enter_awaiting']

            self.assertEqual(client.observer.log, expected_log)


if __name__ == '__main__':
    unittest.main()
