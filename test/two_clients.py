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
                reconnect_interval=0) as subscriber:
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

                    got_messages = so.extract_received_messages()

                    self.assertEqual(got_messages, expected_messages)
                except Exception:
                    print('Subscriber log: {0}'.format(co1.log))
                    print('Publisher log: {0}'.format(co2.log))
                    print('Subscription log: {0}'.format(so.log))
                    raise

    def test_two_clients_with_best_effort_delivery(self):

        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=0) as subscriber:
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
                except Exception:
                    print('Subscriber log: {0}'.format(co1.log))
                    print('Publisher log: {0}'.format(co2.log))
                    print('Subscription log: {0}'.format(so.log))
                    raise

    def test_two_clients_with_always_latest_delivery(self):

        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=0) as subscriber:
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
                except Exception:
                    print('Subscriber log: {0}'.format(co1.log))
                    print('Publisher log: {0}'.format(co2.log))
                    print('Subscription log: {0}'.format(so.log))
                    raise

    def test_two_clients_big_string_messages(self):
        messages = ['a' * 600, 'b' * 6000, 'c' * 60000]
        self.generic_test_two_clients_with_message_list(messages)

    def test_two_clients_big_arrays(self):
        messages = [['a'] * 100, ['b'] * 1000, ['c'] * 10000]
        self.generic_test_two_clients_with_message_list(messages)

    def test_two_clients_big_dictionaries(self):
        def make_dict(n):
            result = {}
            alphabet = "qwfpgarstdzxcvbjluy;hneikm"
            alphabet = alphabet + alphabet.upper()
            i = 0
            for a in alphabet:
                for b in alphabet:
                    for c in alphabet:
                        key = a + b + c
                        try:
                            # for Python 2
                            key = key.decode('utf8')
                        except Exception:
                            pass
                        result[key] = i
                        i += 1
                        if i >= n:
                            return result
            return result
        messages = [make_dict(100), make_dict(1000), make_dict(5000)]
        self.generic_test_two_clients_with_message_list(messages)

    def generic_test_two_clients_with_message_list(self, message_list):

        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=0) as subscriber:
            with make_client(endpoint=endpoint, appkey=appkey) as publisher:

                co1 = ClientObserver()
                subscriber.observer = co1
                co2 = ClientObserver()
                publisher.observer = co2

                so = sync_subscribe(subscriber, channel)

                for msg in message_list:
                    publisher.publish(channel, msg)

                sync_publish(publisher, channel, 'finalizer')

                while 'finalizer' !=\
                        so.last_received_channel_data['messages'][-1]:
                    print(so.last_received_channel_data)
                    last_data = so.wait_for_channel_data()
                    if last_data['messages'][-1] == 'finalizer':
                        break

                got_messages = so.extract_received_messages()

                self.assertEqual(got_messages, message_list + ['finalizer'])

    def test_two_clients_with_deduplication(self):
        with make_client(endpoint=endpoint, appkey=appkey) as pub:
            with make_client(endpoint=endpoint, appkey=appkey) as sub:
                so = sync_subscribe(
                    sub,
                    channel,
                    args={'only': 'value_changes'})
                pub.publish(channel, "first")
                so.wait_for_channel_data()
                for _ in range(10):
                    pub.publish(channel, "second")
                so.wait_for_channel_data()
                pub.publish(channel, "third")
                so.wait_for_channel_data()
                got_messages = so.extract_received_messages()
                self.assertEqual(got_messages, ['first', 'second', 'third'])


if __name__ == '__main__':
    unittest.main()
