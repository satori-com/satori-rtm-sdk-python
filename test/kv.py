
from __future__ import print_function
import unittest

from satori.rtm.client import make_client
from threading import Event

from test.utils import make_channel_name, get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()


class TestKV(unittest.TestCase):
    def test_write_read(self):
        with make_client(endpoint, appkey) as client:
            k = make_channel_name('kv')
            v = make_channel_name('message')

            mailbox = []
            event = Event()

            def callback(ack):
                mailbox.append(ack)
                event.set()

            client.write(k, v, callback=callback)
            event.wait(10)
            event.clear()

            client.read(k, callback=callback)
            event.wait(10)

            assert len(mailbox) == 2
            write_ack = mailbox[0]
            read_ack = mailbox[1]
            assert write_ack['action'] == 'rtm/write/ok'
            assert read_ack['action'] == 'rtm/read/ok'
            assert read_ack['body']['message'] == v

    def test_write_write_read(self):
        with make_client(endpoint, appkey) as client:
            k = make_channel_name('kv')
            v = make_channel_name('value')
            v2 = make_channel_name('value2')

            mailbox = []
            event = Event()

            def callback(ack):
                mailbox.append(ack)
                event.set()

            client.write(k, v, callback=callback)
            event.wait(10)
            event.clear()
            client.write(k, v2, callback=callback)
            event.wait(10)
            event.clear()

            client.read(k, callback=callback)
            event.wait(10)

            assert len(mailbox) == 3
            assert mailbox[0]['action'] == 'rtm/write/ok'
            assert mailbox[1]['action'] == 'rtm/write/ok'
            assert mailbox[2]['action'] == 'rtm/read/ok'
            assert mailbox[2]['body']['message'] == v2

    def test_delete_read(self):
        with make_client(endpoint, appkey) as client:
            k = make_channel_name('delete_read')

            mailbox = []
            event = Event()

            def callback(ack):
                mailbox.append(ack)
                event.set()

            client.delete(k, callback=callback)
            event.wait(10)
            event.clear()
            client.read(k, callback=callback)
            event.wait(10)

            assert len(mailbox) == 2
            assert mailbox[0]['action'] == 'rtm/delete/ok'
            assert mailbox[1]['action'] == 'rtm/read/ok'
            assert mailbox[1]['body']['message'] is None

    def test_write_delete_read(self):
        with make_client(endpoint, appkey) as client:
            k = make_channel_name('delete_read')
            v = make_channel_name('value')

            mailbox = []
            event = Event()

            def callback(ack):
                mailbox.append(ack)
                event.set()

            client.write(k, v, callback=callback)
            event.wait(10)
            event.clear()
            client.delete(k, callback=callback)
            event.wait(10)
            event.clear()
            client.read(k, callback=callback)
            event.wait(10)

            assert len(mailbox) == 3
            assert mailbox[0]['action'] == 'rtm/write/ok'
            assert mailbox[1]['action'] == 'rtm/delete/ok'
            assert mailbox[2]['action'] == 'rtm/read/ok'
            assert mailbox[2]['body']['message'] is None

    def test_write_delete_write_read(self):
        with make_client(endpoint, appkey) as client:
            k = make_channel_name('delete_read')
            v = make_channel_name('message')
            mailbox = []
            event = Event()

            def callback(ack):
                mailbox.append(ack)
                event.set()

            client.write(k, v, callback=callback)
            event.wait(10)
            event.clear()
            client.delete(k, callback=callback)
            event.wait(10)
            event.clear()
            client.write(k, v, callback=callback)
            event.wait(10)
            event.clear()

            client.read(k, callback=callback)
            event.wait(10)

            assert len(mailbox) == 4
            assert mailbox[0]['action'] == 'rtm/write/ok'
            assert mailbox[1]['action'] == 'rtm/delete/ok'
            assert mailbox[2]['action'] == 'rtm/write/ok'
            assert mailbox[3]['action'] == 'rtm/read/ok'
            assert mailbox[3]['body']['message'] == v


if __name__ == '__main__':
    unittest.main()