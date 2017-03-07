#!/usr/bin/env python

from __future__ import print_function

from contextlib import contextmanager
import docopt
try:
    import rapidjson as json
except ImportError:
    import json
import logging
from six.moves import queue
import sys
import threading
import time

import satori.rtm.connection
from satori.rtm.client import make_client, SubscriptionMode
from satori.rtm.auth import RoleSecretAuthDelegate, Done

try:
    satori.rtm.connection.enable_wsaccel()
except Exception:
    pass

__doc__ = '''Satori CLI

Usage:
  satori_cli.py [options] [--prettify_json] subscribe <channels>...
  satori_cli.py [options] [--prettify_json] filter <channel> <query>
  satori_cli.py [options] publish <channel>
  satori_cli.py [options] [--prettify_json] read <key>
  satori_cli.py [options] write <key> <value>
  satori_cli.py [options] delete <key>
  satori_cli.py [options] record [--output_file=<output_file>] [--size_limit_in_bytes=<size_limit>] [--time_limit_in_seconds=<time_limit>] [--message_count_limit=<message_limit>] <channels>...
  satori_cli.py [options] replay [--input_file=<input_file>] [--rate=<rate_or_unlimited>] [--override_channel=<override_channel>]

Options:
    --verbosity=<verbosity>  # one of 0, 1, 2 or 3, default is 2
    --endpoint=<endpoint>  # default is Open Data Platform endpoint
    --appkey=<appkey>      # default is Open Data Platform key
    -i <input_file> --input_file=<input_file>
    -o <input_file> --output_file=<input_file>
    --role_name=<role-name>
    --role_secret=<role-key>
    --delivery=simple|reliable|advanced
'''


default_endpoint = 'wss://localhost'
default_appkey = 'to_be_provided'


logger = logging.getLogger('satori_cli')
verbosity = 1


def main():
    args = docopt.docopt(__doc__)

    endpoint = args['--endpoint'] or default_endpoint
    appkey = args['--appkey'] or default_appkey
    role_name=args['--role_name']
    role_secret=args['--role_secret']
    prettify_json = args['--prettify_json']
    delivery = args['--delivery']

    if delivery == 'advanced':
        delivery = SubscriptionMode.ADVANCED
    elif delivery == 'reliable':
        delivery = SubscriptionMode.RELIABLE
    elif delivery == 'simple':
        delivery = SubscriptionMode.SIMPLE
    elif delivery is not None:
        print('Invalid delivery mode ' + delivery)
        sys.exit(1)

    global verbosity
    if args['--verbosity'] in ('0', '1', '2', '3'):
        verbosity = int(args['--verbosity'])
    elif args['--verbosity']:
        print('Unexpected verbosity value {0}'.format(args['--verbosity']))
        sys.exit(1)
    else:
        verbosity = 1

    int_to_loglevel = {
        0: logging.ERROR,
        1: logging.WARNING,
        2: logging.INFO,
        3: logging.DEBUG}
    configure_logger(int_to_loglevel[verbosity])

    logger.info('Connecting to %s using appkey %s', endpoint, appkey)

    if args['subscribe']:
        return subscribe(
            args['<channels>'], endpoint, appkey, prettify_json,
            role_name=role_name, role_secret=role_secret, delivery=delivery)
    if args['filter']:
        return subscribe(
            [args['<channel>']], endpoint, appkey, prettify_json,
            role_name=role_name, role_secret=role_secret,
            query=args['<query>'], delivery=delivery)
    elif args['publish']:
        return publish(
            args['<channel>'], endpoint, appkey,
            role_name=role_name, role_secret=role_secret)
    elif args['record']:
        size_limit = parse_size(args['--size_limit_in_bytes'])
        if size_limit:
            logger.info('Log size limit: %s bytes', size_limit)

        count_limit = parse_size(args['--message_count_limit'])
        if count_limit:
            logger.info('Log size limit: %s messages', count_limit)

        time_limit = parse_size(args['--time_limit_in_seconds'])
        if time_limit:
            logger.info('Time limit: %s seconds', time_limit)

        return record(
            args['<channels>'], endpoint, appkey,
            role_name=role_name, role_secret=role_secret,
            size_limit=size_limit, count_limit=count_limit,
            time_limit=time_limit, output_file=args['--output_file'],
            delivery=delivery)
    elif args['replay']:
        fast = args['--rate'] == 'unlimited'
        return replay(
            endpoint, appkey,
            role_name=role_name, role_secret=role_secret,
            override_channel=args['--override_channel'], fast=fast,
            input_file=args['--input_file'])
    elif args['read']:
        return kv_read(
            endpoint, appkey,
            role_name, role_secret,
            args['<key>'], prettify_json=prettify_json)
    elif args['write']:
        value = args['<value>']
        try:
            value = json.loads(value)
        except:
            pass

        return kv_write(
            endpoint, appkey,
            role_name, role_secret,
            args['<key>'], value)
    elif args['delete']:
        return kv_delete(endpoint, appkey, role_name, role_secret, args['<key>'])


def configure_logger(level):
    import satori.rtm.logger
    satori.rtm.logger.configure(level)

    formatter = logging.Formatter(
        'satori_cli:%(asctime)s: %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(handler)


def parse_size(size_string):
    if not size_string:
        return None

    s = size_string[:]
    suffix_to_size = {
        'k': 1000,
        'm': 1000 * 1000,
        'g': 1000 * 1000 * 1000,
    }
    multiplier = 1
    while not s.isdigit():
        if not s:
            return None
        suffix = s[-1].lower()
        multiplier *= suffix_to_size.get(suffix, 1)
        s = s[:-1]
    return int(s) * multiplier


assert parse_size(None) == None
assert parse_size('1') == 1
assert parse_size('1k') == 1000
assert parse_size('3kk') == 3000000
assert parse_size('1M') == 1000000
assert parse_size('1g') == 1000000000
assert parse_size('24k') == 24000


def authenticate(client, role_name, role_secret):
    auth_event = threading.Event()

    logger.info('Authenticating as %s...', role_name)

    def callback(ack):
        logger.info('Auth reply: %s', ack)

        if type(ack) == Done:
            auth_event.set()
        else:
            sys.exit(1)

    auth_delegate = RoleSecretAuthDelegate(role_name, role_secret)
    client.authenticate(auth_delegate, callback)

    auth_success = auth_event.wait(10)

    if auth_success:
        logger.info('Authenticating complete')
    else:
        logger.error('Authenticating failed')
        sys.exit(1)

    return auth_success


class ClientObserver(object):
    def on_leave_awaiting(self):
        logger.warning('on_leave_awaiting')

    def on_enter_awaiting(self):
        logger.warning('on_enter_awaiting')

    def on_leave_connecting(self):
        logger.warning('on_leave_connecting')

    def on_enter_connecting(self):
        logger.warning('on_enter_connecting')

    def on_leave_connected(self):
        logger.warning('on_leave_connected')

    def on_enter_connected(self):
        logger.warning('on_enter_connected')

    def on_enter_stopped(self):
        logger.warning('on_enter_stopped')


@contextmanager
def make_client_(endpoint, appkey, role_name=None, role_secret=None, **kwargs):
    with make_client(
            endpoint, appkey,
            restore_auth_on_reconnect=True, **kwargs) as client:

        client.observer = ClientObserver()

        if role_name and role_secret:
            authenticate(client, role_name, role_secret)

        yield client


def publish(channel, endpoint, appkey, role_name=None, role_secret=None):
    with make_client_(
            endpoint=endpoint, appkey=appkey,
            role_name=role_name, role_secret=role_secret) as client:

        print('Sending input to {0}, press C-d or C-c to stop'.format(channel))

        try:
            counter = Counter()

            while True:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.rstrip()
                try:
                    message = json.loads(line)
                except:
                    message = line
                counter.increment()
                client.publish(
                    channel,
                    message,
                    callback=lambda *args: counter.decrement())
        except KeyboardInterrupt:
            pass
        if counter.value() > 0:
            sleep = 0.1
            while sleep < 1.0:
                time.sleep(sleep)
                sleep += sleep
                if not counter.value():
                    break
            else:
                logger.info('%s publishes remain unacked', counter.value())


def replay(endpoint, appkey, role_name=None, role_secret=None, override_channel=None, fast=False, input_file=None):
    with make_client_(
            endpoint=endpoint, appkey=appkey,
            role_name=role_name, role_secret=role_secret) as client:

        try:
            counter = Counter()

            first_message_send_date = None
            first_message_recv_date = None

            if input_file:
                input_stream = open(input_file)
            else:
                input_stream = sys.stdin

            while True:
                line = input_stream.readline()
                if not line:
                    break
                line = line.rstrip()
                try:
                    data = json.loads(line)
                    current_message_recv_date = data['timestamp']
                    channel = override_channel or data['subscription_id']
                    messages = data['messages']
                    now = time.time()

                    if first_message_send_date is not None and not fast:
                        sleep_amount = (first_message_send_date
                            + (current_message_recv_date - first_message_recv_date)
                            - now)
                    else:
                        sleep_amount = 0

                    if sleep_amount > 0:
                        time.sleep(sleep_amount)

                    if first_message_send_date is None:
                        first_message_send_date = time.time()
                        first_message_recv_date = current_message_recv_date

                    for message in messages:
                        try:
                            client.publish(
                                channel,
                                message,
                                callback=lambda *args: counter.decrement())
                            counter.increment()
                        except queue.Full as e:
                            logger.error('Publish queue is full')

                except ValueError:
                    logger.error('Bad line: %s', line)
                except Exception as e:
                    logger.error('Exception: %s', e)
                    sys.exit(2)

        except KeyboardInterrupt:
            pass
        if counter.value() > 0:
            sleep = 0.1
            while sleep < 3.0:
                time.sleep(sleep)
                sleep += sleep
                if not counter.value():
                    break
                else:
                    logger.info('%s publishes remain unacked', counter.value())


def generic_subscribe(handle_channel_data, channels, endpoint, appkey,
        role_name=None, role_secret=None, query=None, delivery=None):
    with make_client_(
            endpoint=endpoint, appkey=appkey,
            role_name=role_name, role_secret=role_secret) as client:

        logger.info('Connected to %s %s', endpoint, appkey)
        logger.info(
            'Subscribing to %s, press C-c to stop',
            channels[0] if len(channels) == 1 else '{0} channels'.format(
                len(channels)))

        class SubscriptionObserver(object):
            def on_enter_subscribed(self):
                logger.info('Subscription became active')

            def on_enter_failed(self, reason):
                logger.error('Subscription failed because:\n%s', reason)
                sys.exit(1)

            def on_subscription_data(self, data):
                handle_channel_data(data)

        so = SubscriptionObserver()

        delivery = delivery or SubscriptionMode.ADVANCED

        for channel in channels:
            args = {}
            if query:
                args.update({'filter': query})
            client.subscribe(channel, delivery, so, args)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)


def subscribe(channels, endpoint, appkey,
        prettify_json=False, role_name=None, role_secret=None, query=None,
        delivery=None):
    def on_subscription_data(data):
        channel = data['subscription_id']
        indent = 2 if prettify_json else None
        for message in data['messages']:
            pretty_message = json.dumps(message, indent=indent)
            print('{0}: {1}'.format(channel, pretty_message))
        sys.stdout.flush()

    generic_subscribe(
        on_subscription_data, channels, endpoint, appkey,
        role_name=role_name, role_secret=role_secret, query=query, delivery=delivery)

def record(*args, **kwargs):

    # one does not simply pass a mutable variable inside an inner function
    size_limit = {'size_limit': kwargs['size_limit']}
    count_limit = {'count_limit': kwargs['count_limit']}

    if kwargs['time_limit']:
        def stop_recording():
            logger.info('Time limit reached')
            stop_main_thread()

        reconnect_timer = threading.Timer(
            kwargs['time_limit'], stop_recording)
        reconnect_timer.daemon = True
        reconnect_timer.start()

    del kwargs['size_limit']
    del kwargs['count_limit']
    del kwargs['time_limit']

    if kwargs.get('output_file') is not None:
        output_stream = open(kwargs.get('output_file'), 'w')
    else:
        output_stream = sys.stdout

    del kwargs['output_file']

    def on_subscription_data(data):
        data['timestamp'] = time.time()
        output = json.dumps(data)
        print(output, file=output_stream)
        sys.stdout.flush()

        if count_limit['count_limit'] is not None:
            count_limit['count_limit'] -= len(data['messages'])
            if count_limit['count_limit'] <= 0:
                logger.info('Message count limit reached')
                stop_main_thread()

        if size_limit['size_limit'] is not None:
            size_limit['size_limit'] -= len(output)
            if size_limit['size_limit'] <= 0:
                logger.info('Log size limit reached')
                stop_main_thread()

    generic_subscribe(on_subscription_data, *args, **kwargs)

def kv_read(endpoint, appkey, role_name, role_secret, key, prettify_json=False):
    with make_client_(
            endpoint=endpoint, appkey=appkey,
            role_name=role_name, role_secret=role_secret) as client:

        mailbox = []
        event = threading.Event()

        def callback(ack):
            mailbox.append(ack)
            event.set()

        client.read(key, callback=callback)

        if not event.wait(10):
            logger.error('rtm/read operation timed out')
            sys.exit(1)

        pdu = mailbox[0]
        if pdu['action'] != 'rtm/read/ok':
            logger.error('rtm/read operation failed:\n%s', pdu)
            sys.exit(1)

        indent = 2 if prettify_json else None
        json_value = json.dumps(pdu['body']['message'], indent=indent)
        print(json_value)


def kv_write(endpoint, appkey, role_name, role_secret, key, value):
    with make_client_(
            endpoint=endpoint, appkey=appkey,
            role_name=role_name, role_secret=role_secret) as client:

        mailbox = []
        event = threading.Event()

        def callback(ack):
            mailbox.append(ack)
            event.set()

        client.write(key, value, callback=callback)

        if not event.wait(10):
            logger.error('rtm/write operation timed out')
            sys.exit(1)

        pdu = mailbox[0]
        if pdu['action'] != 'rtm/write/ok':
            logger.error('rtm/write operation failed:\n%s', pdu)
            sys.exit(1)


def kv_delete(endpoint, appkey, role_name, role_secret, key):
    with make_client_(
            endpoint=endpoint, appkey=appkey,
            role_name=role_name, role_secret=role_secret) as client:

        mailbox = []
        event = threading.Event()

        def callback(ack):
            mailbox.append(ack)
            event.set()

        client.delete(key, callback=callback)

        if not event.wait(10):
            logger.error('rtm/delete operation timed out')
            sys.exit(1)

        pdu = mailbox[0]
        if pdu['action'] != 'rtm/delete/ok':
            logger.error('rtm/delete operation failed:\n%s', pdu)
            sys.exit(1)


def stop_main_thread():
    try:
        import thread
        thread.interrupt_main()
    except ImportError:
        import _thread
        _thread.interrupt_main()

class Counter(object):
    def __init__(self):
        self._lock = threading.Lock()
        self._value = 0

    def value(self):
        with self._lock:
            return self._value

    def increment(self):
        with self._lock:
            self._value += 1

    def decrement(self):
        with self._lock:
            self._value -= 1


if __name__ == '__main__':
    main()
