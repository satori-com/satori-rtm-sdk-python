# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client, SubscriptionMode
import threading

from test.utils import ClientObserver, SubscriptionObserver
from test.utils import get_test_endpoint_and_appkey
from test.utils import make_channel_name, sync_subscribe, sync_publish


channel = make_channel_name('subscribe_error')
endpoint, appkey = get_test_endpoint_and_appkey()


class TestSubscribeError(unittest.TestCase):

    def test_subscribe_error(self):
        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=1) as client:

            client.observer = ClientObserver()
            so = SubscriptionObserver()
            client.subscribe(
                channel,
                SubscriptionMode.ADVANCED,
                so,
                {'position': 'this_is_invalid_position'})
            so.wait_failed()

            expected_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                ('on_enter_failed', 'Subscribe error')]

            self.assertEqual(so.log, expected_log)

    def test_subscribe_error_and_resubscribe_with_no_position(self):
        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=1) as client:

            client.observer = ClientObserver()
            ev = threading.Event()

            threads = []

            class RecoveringSubscriptionObserver(SubscriptionObserver):
                def on_enter_failed(this, error):
                    this.log.append(('on_enter_failed', error))
                    if error == 'Subscribe error':
                        import threading

                        def resubscribe_sans_position():
                            client.unsubscribe(channel)
                            client.subscribe(
                                channel,
                                SubscriptionMode.ADVANCED,
                                this)
                            ev.set()
                        t = threading.Thread(
                            target=resubscribe_sans_position,
                            name='test_resubscribe_sans_position')
                        t.start()
                        threads.append(t)
            so = RecoveringSubscriptionObserver()
            client.subscribe(
                channel,
                SubscriptionMode.ADVANCED,
                so,
                args={'position': 'this_is_invalid_position'})
            ev.wait(10)

            so.wait_subscribed()

            expected_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                ('on_enter_failed', 'Subscribe error'),
                'on_leave_failed',
                'on_enter_unsubscribed',
                'on_deleted',
                'on_created',
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed']

            self.assertEqual(so.log, expected_log)

            sync_publish(client, channel, 'message')
            data = so.wait_for_channel_data()

            self.assertEqual(data['subscription_id'], channel)
            self.assertEqual(data['messages'], ['message'])

            threads[0].join()

    def test_double_subscribe(self):
        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=1) as client:

            client.observer = ClientObserver()
            so = sync_subscribe(client, channel)
            client.subscribe(
                channel,
                SubscriptionMode.ADVANCED,
                subscription_observer=so)

            sync_publish(client, channel, 'message')
            data = so.wait_for_channel_data()

            expected_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed',
                ('data', data)]

            self.assertEqual(so.log, expected_log)

    def test_wrong_subscribe_ack(self):
        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=10) as client:

            client.observer = ClientObserver()
            old_received_message =\
                client._internal.connection.on_incoming_text_frame
            client._internal.connection.on_incoming_text_frame =\
                lambda *args: None

            so = SubscriptionObserver()
            client.subscribe(
                'test_wrong_subscribe_ack',
                SubscriptionMode.ADVANCED,
                so)

            client._queue.join()

            old_received_message(
                '{"action":"rtm/publish/ok","body":{},"id":0}')

            client._queue.join()

            expected_log = [
                'on_leave_connected',
                'on_enter_awaiting']

            self.assertEqual(client.observer.log[:2], expected_log)

    def test_subscribe_error_after_a_cycle(self):
        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=1) as client:

            old_received_message =\
                client._internal.connection.on_incoming_text_frame
            client._internal.connection.on_incoming_text_frame =\
                lambda *args: None

            so = SubscriptionObserver()
            so2 = SubscriptionObserver()
            client.subscribe(channel, SubscriptionMode.ADVANCED, so)
            client.unsubscribe(channel)
            client.subscribe(channel, SubscriptionMode.ADVANCED, so2)

            client._queue.join()

            self.assertEqual(
                client._internal.subscriptions[channel]._mode,
                'cycle')
            old_received_message(
                '{"action":"rtm/subscribe/ok","body":{"channel":"' +
                channel +
                '","position":"position"},"id":0}')

            so.wait_subscribed()

            self.assertEqual(
                client._internal.subscriptions[channel]._mode,
                'cycle')
            old_received_message(
                '{"action":"rtm/unsubscribe/ok","body":{},"id":1}')

            so.wait_not_subscribed()

            self.assertEqual(
                client._internal.subscriptions[channel]._mode,
                'linked')
            old_received_message(
                '{"action":"rtm/subscribe/error","body":{},"id":2}')

            self.assertEqual(
                client._internal.subscriptions[channel]._mode,
                'linked')
            self.assertEqual(
                client._internal
                .subscriptions[channel]._sm.get_state_name(),
                'Subscription.Failed')
            so2.wait_failed()

            expected_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_unsubscribing',
                'on_leave_unsubscribing',
                'on_enter_unsubscribed',
                'on_deleted']

            expected_log2 = [
                'on_created',
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                ('on_enter_failed', 'Subscribe error')
                ]

            self.assertEqual(so.log, expected_log)
            self.assertEqual(so2.log, expected_log2)

    def test_subscribe_error_in_cycle_mode(self):
        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=1) as client:

            old_received_message =\
                client._internal.connection.on_incoming_text_frame
            client._internal.connection.on_incoming_text_frame =\
                lambda *args: None

            so = SubscriptionObserver()
            so2 = SubscriptionObserver()
            client.subscribe(channel, SubscriptionMode.ADVANCED, so)
            client.unsubscribe(channel)
            client.subscribe(channel, SubscriptionMode.ADVANCED, so2)

            client._queue.join()

            self.assertEqual(
                client._internal.subscriptions[channel]._mode,
                'cycle')
            old_received_message(
                '{"action":"rtm/subscribe/error","body":{},"id":0}')

            self.assertEqual(
                client._internal.subscriptions[channel]._mode,
                'linked')
            old_received_message(
                '{"action":"rtm/subscribe/ok","body":{},"id":1}')
            so2.wait_subscribed()

            expected_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_deleted']

            expected_log2 = [
                'on_created',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed'
                ]

            self.assertEqual(so.log, expected_log)
            self.assertEqual(so2.log, expected_log2)


if __name__ == '__main__':
    unittest.main()
