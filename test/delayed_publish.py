# -*- coding: utf-8 -*-

from __future__ import print_function
import threading
import unittest

from satori.rtm.client import Client
from test.utils import make_channel_name, get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()
channel = make_channel_name('delayed_publish')

error = None


class TestDelayedPublish(unittest.TestCase):

    def test_1(self):
        client = Client(endpoint=endpoint, appkey=appkey)

        global error
        error = "Publish didn't happen"
        exit = threading.Event()

        def after_publish(ack):
            global error
            if ack['action'] == 'rtm/publish/ok':
                error = None
            else:
                error = 'Publish failed {0}'.format(ack)
            exit.set()

        client.publish(channel, 'some-message', callback=after_publish)
        client.start()

        if not exit.wait(60):
            raise RuntimeError('Publish never finished')

        self.assertEqual(error, None)

        client.stop()
        client.dispose()


if __name__ == '__main__':
    unittest.main()
