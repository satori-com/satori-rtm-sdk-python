# -*- coding: utf-8 -*-

from __future__ import print_function
import threading
import unittest

from satori.rtm.client import make_client
from test.utils import ClientObserver, get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()


class TestChangingStateInStateCallbacks(unittest.TestCase):
    def test_client_state_callbacks(self):
        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            global step
            step = 1

            class TestClientObserver(ClientObserver):
                def on_enter_stopped(this):
                    ClientObserver.on_enter_stopped(this)
                    global step
                    if step == 1:
                        step = 2
                        client.start()
                    elif step == 3:
                        exit.set()

                def on_enter_connected(this):
                    ClientObserver.on_enter_connected(this)
                    global step
                    if step == 2:
                        step = 3
                        client.stop()

            co = TestClientObserver()
            client.observer = co

            exit = threading.Event()

            stop_timer = threading.Timer(1, lambda: client.stop())
            stop_timer.daemon = True
            stop_timer.name = 'StopTimer'
            stop_timer.start()

            if not exit.wait(20):
                raise RuntimeError('Timeout')

    def test_subscription_state_callbacks(self):
        # TODO
        pass


if __name__ == '__main__':
    unittest.main()
