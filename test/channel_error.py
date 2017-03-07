# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client

from test.utils import make_channel_name, sync_publish, sync_subscribe
from test.utils import emulate_channel_error, get_test_endpoint_and_appkey
from test.utils import SubscriptionObserver

endpoint, appkey = get_test_endpoint_and_appkey()
channel = make_channel_name('channel_error')


class TestChannelError(unittest.TestCase):

    def test_non_fatal_channel_error(self):
        with make_client(endpoint=endpoint, appkey=appkey) as client:

            so = sync_subscribe(client, channel)

            emulate_channel_error(client, channel)
            client._queue.join()
            so.wait_subscribed()

            expected_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed',
                'on_leave_subscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed',
                ]
            self.assertEqual(so.log, expected_log)

    def test_fatal_channel_error_recovery_into_unsubscribed(self):
        with make_client(endpoint=endpoint, appkey=appkey) as client:

            threads = []

            class RecoveringObserver(SubscriptionObserver):
                def on_enter_failed(this, reason):
                    this.log.append(('on_enter_failed', reason))
                    import threading
                    t = threading.Thread(
                        target=lambda: client.unsubscribe(channel),
                        name='test_fatal_channel_error_recovery')
                    t.start()
                    threads.append(t)

            so = RecoveringObserver()

            sync_subscribe(client, channel, observer=so)

            emulate_channel_error(client, channel, 'out_of_sync')
            sync_publish(client, channel, 'should-be-missed')
            so.wait_not_subscribed()

            client._queue.join()

            threads[0].join()

            expected_log = [
                'on_leave_unsubscribed',
                'on_enter_subscribing',
                'on_leave_subscribing',
                'on_enter_subscribed',
                # note there's no message here
                'on_leave_subscribed',
                ('on_enter_failed',
                    {'subscription_id': channel, 'error': 'out_of_sync'}),
                'on_leave_failed',
                'on_enter_unsubscribed',
                'on_deleted'
                ]
            self.assertEqual(so.log, expected_log)

    def test_channel_error_during_unsubscribing(self):
        with make_client(endpoint=endpoint, appkey=appkey) as client:

            so = sync_subscribe(client, channel)
            client._internal.subscriptions[channel]\
                .on_unsubscribe_ok = lambda *args: None
            client.unsubscribe(channel)
            client._queue.join()
            emulate_channel_error(client, channel)
            so.wait_not_subscribed()
            sync_publish(client, channel, 'should-be-missed')
            so.wait_not_subscribed()

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


if __name__ == '__main__':
    unittest.main()
