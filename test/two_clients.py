# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client, SubscriptionMode

from test.utils import ClientObserver, emulate_websocket_disconnect
from test.utils import get_test_endpoint_and_appkey
from test.utils import make_channel_name, sync_publish, sync_subscribe

endpoint, appkey = get_test_endpoint_and_appkey()
channel = make_channel_name('two_clients')


class TestTwoClients(unittest.TestCase):

    def test_two_clients(self):

        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=1) as subscriber:
            with make_client(endpoint=endpoint, appkey=appkey) as publisher:

                co1 = ClientObserver()
                subscriber.observer = co1
                co2 = ClientObserver()
                publisher.observer = co2

                try:
                    so = sync_subscribe(subscriber, channel)

                    sync_publish(publisher, channel, 'first-message')
                    so.wait_for_channel_data('First receive timeout')
                    emulate_websocket_disconnect(subscriber)
                    so.wait_not_subscribed()

                    # send a message while subscriber is disconnected
                    sync_publish(publisher, channel, 'second-message')

                    so.wait_subscribed('Second subscribe timeout')
                    so.wait_for_channel_data('Second receive timeout')

                    # send a message after subscribed reconnected
                    publisher.publish(channel, 'third-message')

                    so.wait_for_channel_data('Third receive timeout')
                    expected_messages =\
                        ['first-message', 'second-message', 'third-message']

                    got_messages = []
                    for log_entry in so.log:
                        if log_entry[0] == 'data':
                            got_messages += log_entry[1]['messages']

                    self.assertEqual(got_messages, expected_messages)
                except:
                    print('Subscriber log: {0}'.format(co1.log))
                    print('Publisher log: {0}'.format(co2.log))
                    print('Subscription log: {0}'.format(so.log))
                    raise

    def test_two_clients_with_best_effort_delivery(self):

        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=1) as subscriber:
            with make_client(endpoint=endpoint, appkey=appkey) as publisher:

                co1 = ClientObserver()
                subscriber.observer = co1
                co2 = ClientObserver()
                publisher.observer = co2

                try:
                    so = sync_subscribe(
                        subscriber,
                        channel,
                        mode=SubscriptionMode.RELIABLE)

                    sync_publish(publisher, channel, 'first-message')
                    so.wait_for_channel_data('First receive timeout')
                    emulate_websocket_disconnect(subscriber)
                    so.wait_not_subscribed()

                    # send a message while subscriber is disconnected
                    sync_publish(publisher, channel, 'second-message')

                    so.wait_subscribed('Second subscribe timeout')
                    so.wait_for_channel_data('Second receive timeout')

                    # send a message after subscribed reconnected
                    publisher.publish(channel, 'third-message')

                    so.wait_for_channel_data('Third receive timeout')
                    expected_messages =\
                        ['first-message', 'second-message', 'third-message']

                    got_messages = []
                    for log_entry in so.log:
                        if log_entry[0] == 'data':
                            got_messages += log_entry[1]['messages']

                    self.assertEqual(got_messages, expected_messages)
                except:
                    print('Subscriber log: {0}'.format(co1.log))
                    print('Publisher log: {0}'.format(co2.log))
                    print('Subscription log: {0}'.format(so.log))
                    raise

    def test_two_clients_with_always_latest_delivery(self):

        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=5) as subscriber:
            with make_client(endpoint=endpoint, appkey=appkey) as publisher:

                co1 = ClientObserver()
                subscriber.observer = co1
                co2 = ClientObserver()
                publisher.observer = co2

                try:
                    so = sync_subscribe(
                        subscriber,
                        channel,
                        mode=SubscriptionMode.SIMPLE)

                    sync_publish(publisher, channel, 'first-message')
                    so.wait_for_channel_data('First receive timeout')
                    emulate_websocket_disconnect(subscriber)
                    so.wait_not_subscribed()

                    # send a message while subscriber is disconnected
                    sync_publish(publisher, channel, 'second-message')

                    so.wait_subscribed('Second subscribe timeout')

                    # send a message after subscribed reconnected
                    publisher.publish(channel, 'third-message')

                    so.wait_for_channel_data('Third receive timeout')
                    expected_messages = ['first-message', 'third-message']

                    got_messages = []
                    for log_entry in so.log:
                        if log_entry[0] == 'data':
                            got_messages += log_entry[1]['messages']

                    self.assertEqual(got_messages, expected_messages)
                except:
                    print('Subscriber log: {0}'.format(co1.log))
                    print('Publisher log: {0}'.format(co2.log))
                    print('Subscription log: {0}'.format(so.log))
                    raise


if __name__ == '__main__':
    unittest.main()
