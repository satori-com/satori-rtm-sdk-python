
import time
import unittest

from satori.rtm.client import Client, make_client, SubscriptionMode
from test.utils import ClientObserver, make_channel_name
from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()


class TestStateCallbacks(unittest.TestCase):

    def test_start_wait_stop(self):
        client = Client(endpoint=endpoint, appkey=appkey)
        client.observer = ClientObserver()

        client.start()
        client.observer.wait_connected()
        client.stop()
        client.observer.wait_stopped()
        client.dispose()

        expected_log = [
            'on_leave_stopped',
            'on_enter_connecting',
            'on_leave_connecting',
            'on_enter_connected',
            'on_leave_connected',
            'on_enter_stopping',
            'on_leave_stopping',
            'on_enter_stopped',
            'on_leave_stopped',
            'on_enter_disposed']

        self.assertEqual(client.observer.log, expected_log)

    def test_start_stop(self):
        client = Client(endpoint=endpoint, appkey=appkey)
        client.observer = ClientObserver()

        client.start()
        client.observer.wait_connected()
        client.stop()
        client.observer.wait_stopped()

        expected_log_1 = [
            'on_leave_stopped',
            'on_enter_connecting',
            'on_leave_connecting',
            'on_enter_connected',
            'on_leave_connected',
            'on_enter_stopping',
            'on_leave_stopping',
            'on_enter_stopped']

        expected_log_2 = [
            'on_leave_stopped',
            'on_enter_connecting',
            'on_leave_connecting',
            'on_enter_stopped']

        try:
            self.assertEqual(client.observer.log, expected_log_1)
        except:
            self.assertEqual(client.observer.log, expected_log_2)

    def test_stop_already_stopped(self):
        client = Client(endpoint=endpoint, appkey=appkey)
        client.observer = ClientObserver()
        client.stop()
        client.dispose()

        expected_log = [
            'on_leave_stopped',
            'on_enter_disposed']

        self.assertEqual(client.observer.log, expected_log)

    def test_missing_client_observer_callbacks_are_fine(self):

        client = Client(endpoint=endpoint, appkey=appkey)
        client.observer = object()
        client.start()
        client.stop()

    def test_missing_subscription_observer_callbacks_are_fine(self):

        with make_client(endpoint=endpoint, appkey=appkey) as client:
            client.subscribe(
                make_channel_name('missing_subscription_callbacks'),
                SubscriptionMode.ADVANCED,
                object())
            time.sleep(3)


if __name__ == '__main__':
    unittest.main()
