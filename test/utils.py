
from satori.rtm.client import SubscriptionMode

import binascii
import json
import os
import sys
import threading
import traceback


def make_channel_name(prefix):
    return '{0}{1}{2}'.format(
        prefix, '_test_', binascii.hexlify(os.urandom(5)).decode('utf8'))


def sync_publish(client, channel, message):
    exit = threading.Event()

    global reply
    reply = None

    def callback(ack):
        global reply
        reply = ack
        exit.set()

    client.publish(channel, message, callback)
    if not exit.wait(10):
        raise RuntimeError('Publish timeout: {0} {1}'.format(channel, message))

    if reply['action'] == 'rtm/publish/ok':
        return reply['body']['position']
    else:
        raise RuntimeError('Publish {1} {2} failed {0}'.format(
            reply, channel, message))


def sync_unsubscribe(client, channel, so):
    client.unsubscribe(channel)
    if not so.not_subscribed.wait(10):
        raise RuntimeError('Unsubscription to {0} timed out'.format(channel))


def sync_subscribe(client, channel, args=None, observer=None, mode=None):
    so = observer or SubscriptionObserver()
    client.subscribe(
        channel,
        mode or SubscriptionMode.ADVANCED,
        so,
        args=args)
    if not so.subscribed.wait(10):
        raise RuntimeError('Subscription to {0} timed out'.format(channel))
    return so


def emulate_websocket_disconnect(client):
    client._internal.connection.ws.close()


def emulate_broken_pipe(client):
    def break_pipe(stuff):
        raise IOError('fake broken pipe')
    client._internal.connection.ws.sock.sendall = break_pipe


def emulate_socket_disconnect(client):
    client._internal.connection.ws.sock.close()


def emulate_fast_forward(client, channel):
    client._internal.connection.on_fast_forward({
        'info': 'fast_forward',
        'subscription_id': channel})


def emulate_channel_error(client, channel, error=None):
    client._internal.connection.unsubscribe(channel)
    client._internal.connection.on_subscription_error({
        'error': error or 'Test error',
        'subscription_id': channel})


class ClientObserver(object):

    def __init__(self):
        self.log = []
        self.connected = threading.Event()
        self.disconnected = threading.Event()
        self.stopped = threading.Event()
        self.disconnected.set()
        self.stopped.set()

    def on_enter_stopped(self):
        self.log.append('on_enter_stopped')
        self.stopped.set()

    def on_leave_stopped(self):
        self.stopped = threading.Event()
        self.log.append('on_leave_stopped')

    def on_enter_connected(self):
        self.log.append('on_enter_connected')
        self.disconnected = threading.Event()
        self.connected.set()

    def on_leave_connected(self):
        self.connected = threading.Event()
        self.disconnected.set()
        self.log.append('on_leave_connected')

    def on_fast_forward(self, channel):
        self.log.append(('on_fast_forward', channel))

    def wait_connected(self, message='Connect timeout'):
        if not self.connected.wait(10):
            raise RuntimeError(message)

    def wait_disconnected(self, message='Disconnect timeout'):
        if not self.disconnected.wait(10):
            raise RuntimeError(message)

    def wait_stopped(self, message='Stop timeout'):
        if not self.stopped.wait(10):
            raise RuntimeError(message)

    def __getattr__(self, name):
        if name.startswith('on_enter') or name.startswith('on_leave'):
            return lambda: self.log.append(name)
        raise AttributeError('ClientObserver.{0}'.format(name))


class SubscriptionObserver(object):

    def __init__(self):
        self.log = []
        self.last_received_channel_data = None
        self.message_received = threading.Event()
        self.subscribed = threading.Event()
        self.not_subscribed = threading.Event()
        self.failed = threading.Event()
        self.deleted = threading.Event()
        self.not_subscribed.set()

    def on_enter_failed(self, error):
        self.log.append(('on_enter_failed', error))
        self.subscribed.clear()
        self.not_subscribed.set()
        self.failed.set()

    def on_enter_unsubscribing(self):
        self.log.append('on_enter_unsubscribing')
        self.subscribed.set()
        self.not_subscribed.clear()

    def on_enter_unsubscribed(self):
        self.log.append('on_enter_unsubscribed')
        self.subscribed.clear()
        self.not_subscribed.set()

    def on_enter_subscribed(self):
        self.log.append('on_enter_subscribed')
        self.not_subscribed.clear()
        self.subscribed.set()

    def on_enter_subscribing(self):
        self.log.append('on_enter_subscribing')
        self.subscribed.clear()
        self.not_subscribed.set()

    def on_deleted(self):
        self.log.append('on_deleted')
        self.subscribed.clear()
        self.not_subscribed.set()
        self.deleted.set()

    def on_leave_failed(self):
        self.log.append('on_leave_failed')
        self.failed.clear()

    def on_leave_subscribed(self):
        self.log.append('on_leave_subscribed')
        self.subscribed.clear()

    def on_subscription_data(self, data):
        self.last_received_channel_data = data
        self.log.append(('data', data))
        self.message_received.set()

    def on_subscription_error(self, error):
        self.log.append(('error', error))

    def on_created(self):
        self.log.append('on_created')

    def wait_for_channel_data(self, message='Receive timeout'):
        if not self.message_received.wait(10):
            raise RuntimeError(message)
        self.message_received.clear()
        return self.last_received_channel_data

    def wait_not_subscribed(
            self, message='Timeout while waiting for unsubscribed state'):
        if not self.not_subscribed.wait(10):
            raise RuntimeError(message)

    def wait_subscribed(
            self, message='Timeout while waiting for subscribed state'):
        if not self.subscribed.wait(10):
            raise RuntimeError(message)

    def wait_failed(
            self, message='Timeout while waiting for failed state'):
        if not self.failed.wait(10):
            raise RuntimeError(message)

    def wait_deleted(self, message='Timeout while waiting for deleted state'):
        if not self.deleted.wait(10):
            raise RuntimeError(message)

    def extract_received_messages(self):
        result = []
        for i in self.log:
            if isinstance(i, tuple) and i[0] == 'data':
                result += i[1]['messages']
        return result

    def __getattr__(self, name):
        if name.startswith('on_'):
            return lambda: self.log.append(name)
        raise AttributeError('SubscriptionObserver.{0}'.format(name))


def print_all_stacktraces():
    print("\n*** STACKTRACE - START ***\n")
    code = []
    for threadId, stack in sys._current_frames().items():
        code.append("\n# ThreadID: %s" % threadId)
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('File: "%s", line %d, in %s' % (filename,
                                                        lineno, name))
            if line:
                code.append("  %s" % (line.strip()))

    for line in code:
        print(line)
    print("\n*** STACKTRACE - END ***\n")


def print_resource_usage():
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        print('Max RSS: {0}'.format(usage.ru_maxrss))
        print('User time: {0}'.format(usage.ru_utime))
        print('System time: {0}'.format(usage.ru_stime))
        print('Active thread count: {0}'.format(threading.active_count()))
    except ImportError:
        print('Resource module is not available')


def get_test_credentials(config_path='credentials.json'):
    with open(config_path) as f:
        return json.load(f)


def get_test_endpoint_and_appkey(config_path='credentials.json'):
    creds = get_test_credentials(config_path)
    return creds['endpoint'], creds['appkey']


def get_test_role_name_secret_and_channel(config_path='credentials.json'):
    creds = get_test_credentials(config_path)
    return (
        creds['auth_role_name'],
        creds['auth_role_secret_key'],
        creds['auth_restricted_channel'])
