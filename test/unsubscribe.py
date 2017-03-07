# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

import threading
from satori.rtm.client import make_client, SubscriptionMode

from test.utils import make_channel_name, get_test_endpoint_and_appkey

channel = make_channel_name('unsubscribe')
endpoint, appkey = get_test_endpoint_and_appkey()


class TestUnsubscribe(unittest.TestCase):

    def on_enter_subscribed(self):
        self.step3()

    def on_enter_unsubscribed(self):
        if self.waiting_for_unsubscribe:
            self.waiting_for_unsubscribe = False
            self.step5()
        else:
            print('============== WTF ==============')

    def on_subscription_data(self, data):
        for message in data['messages']:
            self.mailbox.append(message)
        self.step4()

    def test_unsubscribe(self):
        with make_client(
                endpoint=endpoint, appkey=appkey,
                reconnect_interval=1) as client:

            self.step_reached = 0

            finish = threading.Event()
            global error
            error = None
            self.mailbox = []
            self.waiting_for_unsubscribe = False

            def step1():
                self.step_reached = 1
                client.publish(
                    channel=channel,
                    message='Before subscribing',
                    callback=step2)

            def step2(ack):
                self.step_reached = 2
                if ack['action'] == 'rtm/publish/ok':
                    client.subscribe(
                        channel_or_subscription_id=channel,
                        mode=SubscriptionMode.ADVANCED,
                        subscription_observer=self)
                else:
                    global error
                    error = 'First publish failed'
                    print('Error {0}'.format(error))
                    finish.set()

            def step3():
                self.step_reached = 3
                client.publish(
                    channel=channel,
                    message='Expected message',
                    callback=step3a)

            self.step3 = step3

            def step3a(ack):
                self.step_reached = '3a'
                if not ack['action'] == 'rtm/publish/ok':
                    global error
                    error = 'Second publish failed'
                    print('Error {0}'.format(error))
                    finish.set()

            def step4():
                self.step_reached = 4
                self.waiting_for_unsubscribe = True
                client.unsubscribe(channel_or_subscription_id=channel)

            self.step4 = step4

            def step5():
                self.step_reached = 5
                client.publish(
                    channel=channel,
                    message='After unsubscribing',
                    callback=step6)

            self.step5 = step5

            def step6(ack):
                self.step_reached = 6
                finish.set()

            step1()
            if not finish.wait(30):
                raise RuntimeError(
                    'Timeout at step {0}, error: {1}, mailbox {2}'.format(
                        self.step_reached, error, self.mailbox))

        self.assertEqual(error, None)
        self.assertEqual(self.mailbox, ['Expected message'])


if __name__ == '__main__':
    unittest.main()
