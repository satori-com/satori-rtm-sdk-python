# -*- coding: utf-8 -*-

from __future__ import print_function
import six
import threading
import time
import unittest

from satori.rtm.client import make_client

from test.utils import make_channel_name, print_resource_usage
from test.utils import sync_publish, sync_subscribe
from test.utils import get_test_endpoint_and_appkey

message = 'hello'
channel = make_channel_name('pathologic')
endpoint, appkey = get_test_endpoint_and_appkey()
secret_key = b'FF6FFFCfB2f7F3fe0E627d9fE2DB2EcD'


class TestMultithreadedUsage(unittest.TestCase):
    def test_concurrent_publishes_in_one_client(self):
        with make_client(endpoint=endpoint, appkey=appkey) as client:
            mailbox = []
            self.publish_errors = []

            so = sync_subscribe(client, channel)
            so.on_subscription_data = lambda data:\
                mailbox.extend(data['messages'])

            def work():
                    for i in six.moves.range(100):
                        try:
                            sync_publish(client, channel, message)
                        except Exception as e:
                            self.publish_errors.append(e)

            threads = []
            for i in range(10):
                threads.append(threading.Thread(target=work))
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            print('Waiting for the rest of messages')
            time.sleep(3)
            print("We've hopefully waited long enough")

        self.assertEqual([], self.publish_errors)
        # assertEqual seems to choke on 1000 of 'hello's
        self.assertEqual(len(mailbox), 1000)
        self.assertTrue(all((m == 'hello' for m in mailbox)))

    def test_concurrent_publishes_in_different_clients(self):
        mailbox2 = []
        self.publish_errors = []

        def work():
            with make_client(endpoint=endpoint, appkey=appkey) as publisher:
                for i in six.moves.range(100):
                    try:
                        sync_publish(publisher, channel, message)
                    except Exception as e:
                        self.publish_errors.append(e)

        with make_client(endpoint=endpoint, appkey=appkey) as subscriber:
            so = sync_subscribe(subscriber, channel)
            so.on_subscription_data = lambda data:\
                mailbox2.extend(data['messages'])

            threads = []
            for i in range(10):
                threads.append(threading.Thread(target=work))
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            time.sleep(3)

        self.assertEqual([], self.publish_errors)
        # assertEqual seems to choke on 1000 of 'hello's
        self.assertEqual(len(mailbox2), 1000)
        self.assertTrue(all((m == 'hello' for m in mailbox2)))


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        print_resource_usage()
