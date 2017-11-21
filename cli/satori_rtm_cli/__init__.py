#!/usr/bin/env python

from __future__ import print_function

import docopt
try:
    import rapidjson as json
except ImportError:
    import json
import logging
import os
from six.moves import queue
import sys
import threading
import time
import toml
from xdg import XDG_CONFIG_HOME

import satori.rtm.connection
from satori.rtm.client import make_client, SubscriptionMode
from satori.rtm.auth import RoleSecretAuthDelegate

try:
    satori.rtm.connection.enable_wsaccel()
except Exception:
    pass

__doc__ = '''Satori RTM CLI

Usage:
  satori-rtm-cli --help
  satori-rtm-cli [options] [--prettify_json] subscribe [--position=<position>] [(--count=<count> | --age=<age>)] <channels>...
  satori-rtm-cli [options] [--prettify_json] view [--position=<position>] [--count=<count>] [--age=<age>] [--period=<period_in_seconds>] <query>
  satori-rtm-cli [options] publish [--disable_acks] <channel>
  satori-rtm-cli [options] [--prettify_json] read <key>
  satori-rtm-cli [options] write [--disable_acks] <key> <value>
  satori-rtm-cli [options] delete [--disable_acks] <key>
  satori-rtm-cli [options] record [--output_file=<output_file>] [--size_limit_in_bytes=<size_limit>] [--time_limit_in_seconds=<time_limit>] [--message_count_limit=<message_limit>] [--position=<position>] [(--count=<count> | --age=<age>)] <channels>...
  satori-rtm-cli [options] replay [--disable_acks] [--input_file=<input_file> [--loop=<N|inf>]] [--rate=<rate_or_unlimited>] [--override_channel=<override_channel>]

Options:
    -v <verbosity> --verbosity=<verbosity>  # one of 0, 1, 2 or 3, default is 1
    -e <endpoint> --endpoint=<endpoint>  # default is Open Data endpoint
    -a <appkey> --appkey=<appkey>
    -i <input_file> --input_file=<input_file>
    -o <output_file> --output_file=<output_file>
    -n <role-name> --role_name=<role-name>
    -s <role-secret> --role_secret=<role-secret>
    -j --prettify_json
    -q --disable_acks
    -p <period_in_seconds>, --period=<period_in_seconds>
    -r <rate_or_unlimited>, --rate=<rate_or_unlimited>  # relative rate of replaying, can be a <number>x (2x for double speed, 0.5x for half speed) or "unlimited" for replaying as fast as possible, default is 1x
    -d simple|reliable|advanced, --delivery=simple|reliable|advanced
    -c <config_file_path> --config <config_file_path>
    --position <position>  # subscribe from this position, makes sense only when subscribing to a single channel
    --count <count>  # include this many past messages in the subscription data
    --age <age>  # include this many past seconds worth of messages in the subscription data
    -l <N|inf> --loop <N|inf>  # loop playback N times, `--loop inf` means loop forever, compatible only with --input_file option
'''


default_endpoint = 'wss://open-data.api.satori.com'


logger = logging.getLogger('satori-rtm-cli')


class ClientObserver(object):
    def on_leave_awaiting(self):
        logger.debug('on_leave_awaiting')

    def on_enter_awaiting(self):
        logger.debug('on_enter_awaiting')

    def on_leave_connecting(self):
        logger.debug('on_leave_connecting')

    def on_enter_connecting(self):
        logger.debug('on_enter_connecting')

    def on_leave_connected(self):
        logger.warning('Disconnected')

    def on_enter_connected(self):
        logger.warning('Connected')

    def on_enter_stopped(self):
        logger.debug('on_enter_stopped')


def get_args():
    docopt_args = docopt.docopt(__doc__)
    config_file_path = docopt_args['--config']
    args = load_args_from_config_file(config_file_path)
    args.update(load_args_from_env())

    for k, v in docopt_args.items():
        if k not in args or v is not None:
            args[k] = v
    return args


def main():
    args = get_args()

    appkey = args['--appkey']

    if not appkey:
        print('Missing --appkey parameter', file=sys.stderr)
        sys.exit(1)

    endpoint = args['--endpoint'] or default_endpoint
    role_name = args['--role_name']
    role_secret = args['--role_secret']
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

    if args['--rate'] is not None:
        if args['--rate'] == 'unlimited':
            rate = float('inf')
        else:
            try:
                assert args['--rate'][-1] == 'x'
                rate = float(args['--rate'][:-1])
            except Exception:
                print('Invalid rate {}'.format(args['--rate']), file=sys.stderr)
                sys.exit(1)
    else:
        rate = 1

    if role_name and role_secret:
        auth_delegate = RoleSecretAuthDelegate(role_name, role_secret)
    else:
        auth_delegate = None

    if args['--verbosity'] is not None:
        if int(args['--verbosity']) in (0, 1, 2, 3):
            verbosity = int(args['--verbosity'])
        else:
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

    enable_acks = not args['--disable_acks']

    observer = ClientObserver()
    logger.warning('Connecting to %s using appkey %s', endpoint, appkey)

    with make_client(
            endpoint, appkey,
            auth_delegate=auth_delegate, observer=observer) as client:
        logger.warning('Connected')
        if args['subscribe']:
            extra_args = {}
            if args['--position']:
                extra_args['position'] = args['--position']
            if args['--age']:
                extra_args['history'] = {'age': int(args['--age'])}
            elif args['--count']:
                extra_args['history'] = {'count': int(args['--count'])}
            return subscribe(
                client,
                args['<channels>'], prettify_json, extra_args=extra_args,
                delivery=delivery)
        if args['view']:
            extra_args = {'filter': args['<query>']}
            if args['--period']:
                extra_args['period'] = int(args['--period'])
            if args['--position']:
                extra_args['position'] = args['--position']
            if args['--age']:
                extra_args['history'] = {'age': int(args['--age'])}
            elif args['--count']:
                extra_args['history'] = {'count': int(args['--count'])}
            return subscribe(
                client,
                ['view'], prettify_json,
                # TODO replace with 'view' when the time comes
                extra_args=extra_args, delivery=delivery)
        elif args['publish']:
            return publish(client, args['<channel>'], enable_acks)
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

            extra_args = {}
            if args['--position']:
                extra_args['position'] = args['--position']
            if args['--age']:
                extra_args['history'] = {'age': int(args['--age'])}
            elif args['--count']:
                extra_args['history'] = {'count': int(args['--count'])}

            return record(
                client,
                args['<channels>'],
                size_limit=size_limit, count_limit=count_limit,
                time_limit=time_limit, output_file=args['--output_file'],
                extra_args=extra_args,
                delivery=delivery)
        elif args['replay']:
            if args['--loop'] == 'inf':
                loop = float('inf')
            else:
                loop = int(args['--loop'] or 1)
            return replay(
                client,
                override_channel=args['--override_channel'], rate=rate,
                loop=loop,
                input_file=args['--input_file'], enable_acks=enable_acks)
        elif args['read']:
            return kv_read(
                client,
                args['<key>'], prettify_json=prettify_json)
        elif args['write']:
            value = args['<value>']
            try:
                value = json.loads(value)
            except Exception:
                pass

            return kv_write(client, args['<key>'], value, enable_acks)
        elif args['delete']:
            return kv_delete(client, args['<key>'], enable_acks)


def configure_logger(level):

    class Formatter(logging.Formatter):
        def format(self, record):
            if record.name == 'satori-rtm-cli':
                self._fmt = "%(message)s"
            else:
                self._fmt = "%(asctime)s %(module)s.%(funcName)s():%(lineno)s %(message)s"

            if record.levelno >= logging.ERROR:
                self._fmt = "%(levelname)s " + self._fmt
            return logging.Formatter.format(self, record)

    formatter = Formatter()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(handler)
    ws4py_formatter = formatter
    ws4py_handler = logging.StreamHandler()
    ws4py_handler.setFormatter(ws4py_formatter)

    ws4py_logger = logging.getLogger('miniws4py')
    ws4py_logger.setLevel(level)
    ws4py_logger.addHandler(ws4py_handler)

    satori_logger = logging.getLogger('satori.rtm')
    satori_formatter = formatter
    satori_handler = logging.StreamHandler()
    satori_handler.setFormatter(satori_formatter)
    satori_logger.addHandler(satori_handler)


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


assert parse_size(None) is None
assert parse_size('1') == 1
assert parse_size('1k') == 1000
assert parse_size('3kk') == 3000000
assert parse_size('1M') == 1000000
assert parse_size('1g') == 1000000000
assert parse_size('24k') == 24000


def publish(client, channel, enable_acks):
    print('Sending input to {0}, press C-d or C-c to stop'.format(channel))

    try:
        counter = Counter()

        if enable_acks:
            def callback(reply):
                if reply['action'] != 'rtm/publish/ok':
                    print('Publish failed: ', file=sys.stderr)
                    stop_main_thread()
                counter.decrement()
        else:
            callback = None

        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.rstrip()
            try:
                message = json.loads(line)
            except ValueError:
                message = line

            if enable_acks:
                counter.increment()
            client.publish(channel, message, callback=callback)
    except KeyboardInterrupt:
        pass

    if not enable_acks:
        return

    if counter.value() > 0:
        sleep = 0.1
        while sleep < 1.0:
            time.sleep(sleep)
            sleep += sleep
            if not counter.value():
                break
        else:
            logger.info('%s publishes remain unacked', counter.value())


def replay(client, override_channel=None, rate=1.0, loop=1, input_file=None, enable_acks=True):
    try:
        publish_counter = Counter()
        publish_ack_counter = Counter()
        start_timestamp = time.time()

        if enable_acks:
            def callback(reply):
                if reply['action'] != 'rtm/publish/ok':
                    print('Publish failed: ', file=sys.stderr)
                    stop_main_thread()
                publish_ack_counter.increment()
        else:
            callback = None

        input_stream = sys.stdin

        while loop >= 1:
            first_message_send_date = None
            first_message_recv_date = None

            if input_file:
                input_stream = open(input_file)

            while True:
                line = input_stream.readline()
                if not line:
                    if input_file:
                        input_stream.close()
                        loop -= 1
                        logger.warning(
                            'Messages published: %d', publish_counter.value())
                        if loop == float('inf'):
                            logger.warning('Playback cycle finished')
                        elif loop > 0:
                            logger.warning(
                                'Playback cycle finished, %d to go', loop)
                    else:
                        loop = 0
                    break
                line = line.rstrip()
                try:
                    data = json.loads(line)
                    current_message_recv_date = data['timestamp']
                    channel = override_channel or data['subscription_id']
                    messages = data['messages']
                    now = time.time()

                    if first_message_send_date is not None:
                        sleep_amount =\
                            ((current_message_recv_date - first_message_recv_date) / rate)\
                            - (now - first_message_send_date)
                    else:
                        sleep_amount = 0

                    if sleep_amount > 0:
                        time.sleep(sleep_amount)

                    if first_message_send_date is None:
                        first_message_send_date = time.time()
                        first_message_recv_date = current_message_recv_date

                    for message in messages:
                        try:
                            publish_counter.increment()
                            client.publish(channel, message, callback=callback)
                        except queue.Full as e:
                            logger.error('Publish queue is full')

                except ValueError:
                    logger.error('Bad line: %s', line)
                except Exception as e:
                    logger.error('Exception: %s', e)
                    stop_main_thread()

        logger.warning(
            'Playback finished, total time: %.2f seconds',
            time.time() - start_timestamp)

    except KeyboardInterrupt:
        pass
    if not enable_acks:
        return

    def unacked_count():
        return publish_counter.value() - publish_ack_counter.value()
    if unacked_count() > 0:
        sleep = 0.1
        while sleep < 3.0:
            time.sleep(sleep)
            sleep += sleep
            if not unacked_count():
                break
            else:
                logger.info('%s publishes remain unacked', unacked_count())


def generic_subscribe(
        client, handle_channel_data, channels,
        extra_args=None, delivery=None):
    logger.info(
        'Subscribing to %s, press C-c to stop',
        channels[0] if len(channels) == 1 else '{0} channels'.format(
            len(channels)))

    class SubscriptionObserver(object):
        def on_enter_subscribed(self):
            logger.info('Subscription became active')

        def on_enter_failed(self, reason):
            logger.error('Subscription failed because: %s', reason)
            stop_main_thread()

        def on_subscription_data(self, data):
            handle_channel_data(data)

    so = SubscriptionObserver()

    delivery = delivery or SubscriptionMode.ADVANCED

    for channel in channels:
        args = {}
        if extra_args:
            args.update(extra_args)
        client.subscribe(channel, delivery, so, args)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sys.exit(0)


def subscribe(
        client, channels,
        prettify_json=False, extra_args=None,
        delivery=None):
    def on_subscription_data(data):
        channel = data['subscription_id']
        indent = 2 if prettify_json else None
        for message in data['messages']:
            pretty_message = json.dumps(message, indent=indent)
            print('{0}: {1}'.format(channel, pretty_message))
        sys.stdout.flush()

    generic_subscribe(
        client, on_subscription_data, channels,
        extra_args=extra_args, delivery=delivery)


def record(client, *args, **kwargs):
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
        output_stream.flush()

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

    generic_subscribe(client, on_subscription_data, *args, **kwargs)


def kv_read(client, key, prettify_json=False):
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


def kv_write(client, key, value, enable_acks):
    if enable_acks:
        mailbox = []
        event = threading.Event()

        def callback(ack):
            mailbox.append(ack)
            event.set()
    else:
        callback = None

    client.write(key, value, callback=callback)

    if not enable_acks:
        return

    if not event.wait(10):
        logger.error('rtm/write operation timed out')
        sys.exit(1)

    pdu = mailbox[0]
    if pdu['action'] != 'rtm/write/ok':
        logger.error('rtm/write operation failed:\n%s', pdu)
        sys.exit(1)


def kv_delete(client, key, enable_acks):
    if enable_acks:
        mailbox = []
        event = threading.Event()

        def callback(ack):
            mailbox.append(ack)
            event.set()
    else:
        callback = None

    client.delete(key, callback=callback)

    if not enable_acks:
        return

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


def load_args_from_config_file(path=None):
    quiet = False
    if path is None:
        quiet = True
        path = os.path.join(XDG_CONFIG_HOME, 'satori', 'rtm-cli.config')
    result = {}
    try:
        try:
            with open(path) as f:
                fileconfig = toml.load(f)
                for k, v in fileconfig.items():
                    print(
                        "From config file: {0} = {1}".format(k, v),
                        file=sys.stderr)
                    result[u'--' + k] = v
        except toml.TomlDecodeError:
            try:
                # Just in case the config file has the format credentials.json
                with open(path) as f:
                    fileconfig = json.load(f)
                    for k, v in fileconfig.items():
                        if k == 'auth_role_name':
                            k = 'role_name'
                        if k == 'auth_role_secret_key':
                            k = 'role_secret'
                        print(
                            "From config file: {0} = {1}".format(k, v),
                            file=sys.stderr)
                        result[u'--' + k] = v
            except ValueError:
                print(
                    "Invalid config file at {0}".format(path),
                    file=sys.stderr)
    except (IOError, OSError):
        if not quiet:
            print(
                "Couldn't read the config file at {0}".format(path),
                file=sys.stderr)
    return result


def load_args_from_env():
    result = {}
    endpoint = os.environ.get("SATORI_ENDPOINT")
    appkey = os.environ.get("SATORI_APPKEY")
    role_name = os.environ.get("SATORI_ROLE_NAME")
    role_secret = os.environ.get("SATORI_ROLE_SECRET")
    if endpoint:
        result['--endpoint'] = endpoint
    if appkey:
        result['--appkey'] = appkey
    if role_name:
        result['--role_name'] = role_name
    if role_secret:
        result['--role_secret'] = role_secret
    return result


if __name__ == '__main__':
    main()
