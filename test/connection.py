# -*- coding: utf-8 -*-

from __future__ import print_function
import time
import unittest

import satori.rtm.connection as sc
import threading

from test.utils import make_channel_name, get_test_endpoint_and_appkey
from test.utils import print_resource_usage

endpoint, appkey = get_test_endpoint_and_appkey()


class TestConnection(unittest.TestCase):
    def test_stop_before_start(self):
        conn = sc.Connection(endpoint, appkey)
        self.assertRaises(
            RuntimeError,
            lambda: conn.stop())

    def test_double_start(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        self.assertRaises(
            RuntimeError,
            lambda: conn.start())
        conn.stop()

    def test_stop_after_closing(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        conn.stop()
        time.sleep(2)
        self.assertRaises(
            RuntimeError,
            lambda: conn.stop())

    def test_forgot_to_stop(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        del conn

    def test_subscribe_before_start(self):
        conn = sc.Connection(endpoint, appkey)
        channel = make_channel_name('subscribe_before_start')
        self.assertRaises(
            RuntimeError,
            lambda: conn.subscribe_sync(channel))

    def test_publish_before_start(self):
        conn = sc.Connection(endpoint, appkey)
        channel = make_channel_name('publish_before_start')
        self.assertRaises(
            RuntimeError,
            lambda: conn.publish_sync(channel, 'test'))

    def test_sync_operations(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        channel = make_channel_name('sync_connection_operations')
        conn.subscribe_sync(channel)
        conn.publish_sync(channel, 'test')
        conn.unsubscribe_sync(channel)
        conn.stop()

    def test_subscribe_sync_fail(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        channel = make_channel_name('invalid_position')
        self.assertRaises(
            RuntimeError,
            lambda: conn.subscribe_sync(channel, {'position': 'invalid'}))
        conn.stop()

    def test_publish_sync_fail(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        self.assertRaises(
            RuntimeError,
            lambda: conn.publish_sync('$python.sdk.restricted', 'test'))
        conn.stop()

    def test_unsubscribe_sync_fail(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        self.assertRaises(
            RuntimeError,
            lambda: conn.unsubscribe_sync('any'))
        conn.stop()

    def test_write_read(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()

        k, v = make_channel_name('write_read'), 'value1'
        mailbox = []
        event = threading.Event()

        def callback(pdu):
            mailbox.append(pdu)
            event.set()

        conn.write(k, v, callback=callback)
        event.wait(10)
        event.clear()

        conn.read(k, callback=callback)
        event.wait(10)
        conn.stop()

        assert len(mailbox) == 2
        write_ack = mailbox[0]
        read_ack = mailbox[1]
        assert write_ack['action'] == 'rtm/write/ok'
        assert read_ack['action'] == 'rtm/read/ok'
        assert read_ack['body']['message'] == v

    def test_write_write_read(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        k, v1, v2 = make_channel_name('wwr'), 'wwr_value1', 'wwr_value2'

        mailbox = []
        event = threading.Event()

        def callback(pdu):
            mailbox.append(pdu)
            event.set()

        conn.write(k, v1, callback=callback)
        event.wait(10)
        event.clear()
        conn.write(k, v2, callback=callback)
        event.wait(10)

        assert len(mailbox) == 2
        for write_ack in mailbox:
            assert write_ack['action'] == 'rtm/write/ok'

        assert conn.read_sync(k) == v2
        conn.stop()

    def test_read(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        k = make_channel_name('read')
        assert conn.read_sync(k) is None
        conn.stop()

    def test_delete_read(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        k = make_channel_name('delete_read')

        mailbox = []
        event = threading.Event()

        def callback(pdu):
            mailbox.append(pdu)
            event.set()

        conn.delete(k, callback=callback)
        event.wait(10)

        assert len(mailbox) == 1
        assert mailbox[0]['action'] == 'rtm/delete/ok'
        assert conn.read_sync(k) is None
        conn.stop()

    def test_write_delete_read(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        k = make_channel_name('write_delete_read')

        mailbox = []
        event = threading.Event()

        def callback(pdu):
            mailbox.append(pdu)
            event.set()

        conn.write(k, 'v', callback=callback)
        event.wait(10)
        event.clear()
        conn.delete(k, callback=callback)
        event.wait(10)

        assert len(mailbox) == 2
        assert mailbox[0]['action'] == 'rtm/write/ok'
        assert mailbox[1]['action'] == 'rtm/delete/ok'

        assert conn.read_sync(k) is None
        conn.stop()

    def test_write_delete_write_read(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        k, v = make_channel_name('write_delete_write_read'), 'v'

        mailbox = []
        event = threading.Event()

        def callback(pdu):
            mailbox.append(pdu)
            event.set()

        conn.write(k, v, callback=callback)
        event.wait(10)
        event.clear()
        conn.delete(k, callback=callback)
        event.wait(10)
        event.clear()
        conn.write(k, v, callback=callback)
        event.wait(10)

        assert len(mailbox) == 3
        assert mailbox[0]['action'] == 'rtm/write/ok'
        assert mailbox[1]['action'] == 'rtm/delete/ok'
        assert mailbox[2]['action'] == 'rtm/write/ok'

        assert conn.read_sync(k) == v
        conn.stop()

    def test_sync_timeouts(self):
        conn = sc.Connection(endpoint, appkey)
        conn.start()
        channel = make_channel_name('sync_timeout')
        conn.on_incoming_text_frame = lambda *args: None
        with self.assertRaises(RuntimeError):
            conn.subscribe_sync(channel, timeout=0)
        with self.assertRaises(RuntimeError):
            conn.unsubscribe_sync(channel, timeout=0)
        with self.assertRaises(RuntimeError):
            conn.publish_sync(channel, 'msg', timeout=0)
        with self.assertRaises(RuntimeError):
            conn.read_sync(channel, timeout=0)
        conn.stop()

    def test_filter(self):
        mailbox = []

        class ConnDelegate(object):
            def on_subscription_data(this, stuff):
                mailbox.append(stuff)
                event.set()

            def on_connection_closed(this):
                pass

        conn = sc.Connection(endpoint, appkey)
        conn.delegate = ConnDelegate()
        conn.start()
        ch = make_channel_name('filter')
        event = threading.Event()

        def callback(ack):
            mailbox.append(ack)
            event.set()

        query = 'select test from ' + ch
        conn.subscribe(ch, args={'filter': query}, callback=callback)
        event.wait(5)
        self.assertEqual(mailbox[0]['action'], 'rtm/subscribe/ok')

        event.clear()
        conn.publish(ch, {'test': 42, 'unused': 'whatever'})

        event.wait(5)
        self.assertEqual(mailbox[1]['messages'], [{'test': 42}])
        self.assertEqual(mailbox[1]['subscription_id'], ch)

        conn.stop()

    def test_explicit_version(self):
        versioned_endpoint = endpoint + '/v2'
        conn = sc.Connection(versioned_endpoint, appkey)

        # this should still work
        conn.start()

        conn.stop()

    def test_send_exception(self):
        mailbox = []

        class Delegate(object):
            def on_connection_closed(this):
                mailbox.append('close')

        delegate = Delegate()
        conn = sc.Connection(endpoint, appkey, delegate=delegate)
        conn.start()

        def fail(*args):
            return 1 / 0

        conn.ws._write = fail

        with self.assertRaises(ZeroDivisionError):
            conn.publish('channel', 'message')

        self.assertEqual(mailbox, ['close'])

    def test_request_throttling(self):
        wm = sc.high_ack_count_watermark
        sc.high_ack_count_watermark = 3
        mailbox = []
        try:
            conn = sc.Connection(endpoint, appkey)
            conn.start()

            def callback(ack):
                mailbox.append(ack)
            channel = make_channel_name('request_throttling')
            for i in range(1000):
                conn.publish(channel, 'message', callback=callback)

            time.sleep(2)
        finally:
            conn.stop()
            sc.high_ack_count_watermark = wm

        self.assertEqual(len(mailbox), 1000)
        self.assertTrue(
            all(ack['action'] == 'rtm/publish/ok' for ack in mailbox))


if __name__ == '__main__':
    unittest.main()
    print_resource_usage()