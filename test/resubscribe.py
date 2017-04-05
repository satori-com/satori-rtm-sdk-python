# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import Client, make_client, SubscriptionMode

from test.utils import ClientObserver, SubscriptionObserver
from test.utils import get_test_endpoint_and_appkey
from test.utils import make_channel_name, sync_publish, sync_subscribe

endpoint, appkey = get_test_endpoint_and_appkey()


class TestResubscribe(unittest.TestCase):

    def test_repeat_second_message(self):
        client = Client(
            endpoint=endpoint, appkey=appkey,
            reconnect_interval=1)
        client.observer = ClientObserver()

        channel = make_channel_name('resubscribe')

        client.start()
        client.observer.wait_connected()
        so = sync_subscribe(client, channel)
        sync_publish(client, channel, 'first-message')
        first_channel_data = so.wait_for_channel_data()
        sync_publish(client, channel, 'second-message')
        second_channel_data = so.wait_for_channel_data()
        client.unsubscribe(channel)
        client.subscribe(
            channel,
            SubscriptionMode.ADVANCED,
            so,
            args={'position': first_channel_data['position']})
        self.assertEqual(
            second_channel_data['messages'],
            so.wait_for_channel_data()['messages'])
        client.unsubscribe(channel)
        so.wait_not_subscribed()
        client.stop()
        client.dispose()

    def test_change_observer(self):
        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            co = ClientObserver()
            client.observer = co

            channel = make_channel_name('change_observer')
            so1 = sync_subscribe(client, channel)

            client.unsubscribe(channel)
            so2 = SubscriptionObserver()
            client.subscribe(
                channel,
                SubscriptionMode.ADVANCED,
                subscription_observer=so2)

            so2.wait_subscribed()

            client.stop()

            co.wait_disconnected()

            self.maxDiff = None
            expected_so1_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed',
                'on_leave_subscribed',
                'on_enter_unsubscribing',
                'on_leave_unsubscribing',
                'on_enter_unsubscribed',
                'on_deleted']

            expected_so2_log = [
                'on_created',
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed']

            self.assertEqual(so1.log, expected_so1_log)
            self.assertEqual(so2.log, expected_so2_log)

    def test_quickly_change_observer_twice(self):
        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            channel = make_channel_name('change_observer_twice')
            so2 = SubscriptionObserver()

            so1 = sync_subscribe(client, channel)
            client.unsubscribe(channel)
            client.subscribe(channel, SubscriptionMode.ADVANCED, so2)
            client.unsubscribe(channel)
            client.subscribe(channel, SubscriptionMode.ADVANCED, None)
            client.unsubscribe(channel)
            so3 = sync_subscribe(client, channel)

            expected_so1_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed',
                'on_leave_subscribed',
                'on_enter_unsubscribing',
                'on_leave_unsubscribing',
                'on_enter_unsubscribed',
                'on_deleted']

            expected_so2_log = ['on_deleted']

            expected_so3_log = [
                'on_created',
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed']

            self.assertEqual(so1.log, expected_so1_log)
            self.assertEqual(so2.log, expected_so2_log)
            self.assertEqual(so3.log, expected_so3_log)

    def test_change_observer_from_none(self):
        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            channel = make_channel_name('change_observer')
            client.subscribe(
                channel,
                SubscriptionMode.ADVANCED,
                subscription_observer=None)

            client.unsubscribe(channel)

            so2 = sync_subscribe(client, channel)

            self.maxDiff = None
            expected_so2_log = [
                'on_created',
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed']

            self.assertEqual(so2.log, expected_so2_log)

            client.stop()

    def test_resubscribe_after_manual_reconnect(self):
        with make_client(endpoint, appkey) as client:
            channel = make_channel_name('manual_reconnect')

            so = sync_subscribe(client, channel)

            sync_publish(client, channel, 'first-message')
            m = so.wait_for_channel_data()
            self.assertEqual(m['messages'], ['first-message'])

            client.observer = ClientObserver()
            client.stop()
            client.observer.wait_disconnected()

            client.start()
            client._queue.join()
            client.observer.wait_connected()

            sync_publish(client, channel, 'second-message')
            m = so.wait_for_channel_data()
            self.assertEqual(m['messages'], ['second-message'])


if __name__ == '__main__':
    unittest.main()
