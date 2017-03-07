#!/usr/bin/env python3

__doc__ = """
Usage:
  bench.py [options]

Options:
 --scenario <scenario>  # publish-ack-<size> | publish-noack-<size> | subscribe
 --channel <channel>
 --endpoint <endpoint>
 --appkey <appkey>
 --profile
 --wsaccel
"""

import binascii
import docopt
import os
import re
import resource
import sys
import time

if '--wsaccel' in sys.argv:
    import satori.rtm.connection
    satori.rtm.connection.enable_wsaccel()

if '--profile' in sys.argv:
    from pyinstrument import Profiler

if '--uvloop' in sys.argv:
    import asyncio
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

import satori.rtm.connection
from test.utils import get_test_endpoint_and_appkey, make_channel_name

test_endpoint, test_appkey = get_test_endpoint_and_appkey()

publish_ack_re = re.compile(r'publish-ack-(\d+)')
publish_noack_re = re.compile(r'publish-noack-(\d+)')

sampling_interval = 5 # in seconds

def main():
    args = docopt.docopt(__doc__)    

    endpoint = args['--endpoint'] or test_endpoint
    appkey = args['--appkey'] or test_appkey
    scenario = args['--scenario']
    profile = args['--profile']

    publish_ack_match = publish_ack_re.match(scenario)
    publish_noack_match = publish_noack_re.match(scenario)

    if scenario == 'subscribe':
        channel = args['--channel']
        if not channel:
            return 1
        return bench_subscribe(endpoint, appkey, channel)
    elif publish_ack_match:
        size = int(publish_ack_match.group(1))
        channel = args['--channel'] or make_channel_name('publish_ack')
        return bench_publish_ack(endpoint, appkey, channel, size, profile)
    elif publish_noack_match:
        size = int(publish_noack_match.group(1))
        channel = args['--channel'] or make_channel_name('publish_no_ack')
        return bench_publish_noack(endpoint, appkey, channel, size, profile)
    else:
        print('Unknown scenario {}'.format(scenario))
        return 1


def bench_publish_ack(*args):
    return bench_publish(*args, ack=True)


def bench_publish_noack(*args):
    return bench_publish(*args, ack=False)


def bench_publish(endpoint, appkey, channel, size, profile, ack=True):
    publisher = satori.rtm.connection.Connection(endpoint + '?appkey=' + appkey)
    publisher.start()

    message = binascii.hexlify(os.urandom(size // 2)).decode('ascii')
    print('Message size is {}'.format(len(message)))

    last_usage = [resource.getrusage(resource.RUSAGE_SELF)]
    print('Duration, s\tRate, msgs/s\tMax RSS, MB\tUser time, s\tSystem time, s')
    def report(duration, count):
        usage = resource.getrusage(resource.RUSAGE_SELF)
        maxrss = usage.ru_maxrss // 1024
        if sys.platform == 'darwin':
            maxrss = maxrss // 1024
        print('{0:2.2f}\t\t{1}\t\t{2}\t\t{3:2.2f}\t\t{4:2.2f}'.format(
            duration,
            int(count / duration),
            maxrss,
            usage.ru_utime - last_usage[0].ru_utime,
            usage.ru_stime - last_usage[0].ru_stime))
        sys.stdout.flush()
        last_usage[0] = usage

    count = [0]

    def publish_without_ack():
        publisher.publish(channel, message)
        count[0] += 1

    def publish_with_ack():
        def callback(ack):
            count[0] += 1
        publisher.publish(channel, message, callback)

    publish = publish_with_ack if ack else publish_without_ack

    before = time.time()
    try:
        if profile:
            profiler = Profiler()
            profiler.start()
        while True:
            now = time.time()
            if now - before >= sampling_interval:
                report(now - before, count[0])
                if profile:
                    profiler.stop()
                    print(profiler.output_text(unicode=True, color=True))
                    profiler = Profiler()
                    profiler.start()
                count[0] = 0
                before = time.time()
            publish()
    except KeyboardInterrupt:
        sys.exit(0)


def bench_subscribe(endpoint, appkey, channel):
    print('subscribe')
    subscriber = satori.rtm.connection.Connection(endpoint + '?appkey=' + appkey)
    counter = [0]

    class CountingThingy(object):
        def __init__(self, c):
            self.c = counter
        def on_subscription_data(self, data):
            self.c[0] += len(data['messages'])
        def on_connection_closed(self):
            pass
        def on_fast_forward(self, channel, stuff):
            pass
    subscriber.delegate = CountingThingy(counter)

    before = time.time()

    last_usage = [resource.getrusage(resource.RUSAGE_SELF)]
    print('Duration, s\tRate, msgs/s\tMax RSS, MB\tUser time, s\tSystem time, s')
    def report(duration, count):
        usage = resource.getrusage(resource.RUSAGE_SELF)
        maxrss = usage.ru_maxrss // 1024
        if sys.platform == 'darwin':
            maxrss = maxrss // 1024
        print('{0:2.2f}\t\t{1}\t\t{2}\t\t{3:2.2f}\t\t{4:2.2f}'.format(
            duration,
            int(count / duration),
            maxrss,
            usage.ru_utime - last_usage[0].ru_utime,
            usage.ru_stime - last_usage[0].ru_stime))
        sys.stdout.flush()
        last_usage[0] = usage

    try:
        subscriber.start()
        subscriber.subscribe_sync(channel, args={'fast_forward': True})

        while True:
            time.sleep(sampling_interval)
            now = time.time()
            report(now - before, counter[0])
            before = now
            counter[0] = 0

    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    sys.exit(main())
