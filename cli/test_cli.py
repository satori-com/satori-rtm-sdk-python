#!/usr/bin/env python

import binascii
import json
import os
import re
import signal
import subprocess
import time
import unittest

from test.utils import get_test_endpoint_and_appkey, get_test_secret_key
from test.utils import make_channel_name

endpoint, appkey = get_test_endpoint_and_appkey('../credentials.json')
channel = b'test_cli.' + binascii.hexlify(os.urandom(5))
string_message = b'string message'
json_message = b'{"text": ["json", "message"]}'


class TestCLI(unittest.TestCase):
    def test_without_auth(self):
        generic_test(self, should_authenticate=False)

    def test_with_auth(self):
        generic_test(self, should_authenticate=True)

    def test_reconnect(self):
        def start_tcpkali():
            return subprocess.Popen(['tcpkali', '--ws', '-l', '8999'])
        tcpkali1 = start_tcpkali()

        satori_cli = subprocess.Popen(
            ['python', 'satori_cli.py',
                '--appkey', 'bogus',
                '--endpoint', 'ws://localhost:8999/',

                '--time_limit_in_seconds=15',
                'record', 'bogus'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        tcpkali1.communicate()

        satori_cli.poll()
        if satori_cli.returncode is not None:
            (out, err) = satori_cli.communicate()
            print('out:', out)
            print('err:', err)
            self.assertEqual(satori_cli.returncode, None)

        tcpkali2 = start_tcpkali()
        tcpkali2.communicate()

        (out, err) = satori_cli.communicate()
        if len(re.findall(b'on_enter_connected', err)) != 1:
            print('out:', out)
            self.assertTrue(
                False,
                "Expected to find 'on_enter_connected' in {0}".format(err))

    def test_replayer_timing(self):

        channel = make_channel_name('replayer_timing')

        rerecorder = subprocess.Popen(
            ['python', 'satori_cli.py',
                '--appkey', appkey,
                '--endpoint', endpoint,

                'record', channel],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        replayer = subprocess.Popen(
            ['python', 'satori_cli.py',
                '--appkey', appkey,
                '--endpoint', endpoint,
                'replay'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        timestamps =\
            (list(range(0, 5)) +

            # range only works with ints, sorry
            [float(x) / 100 for x in range(600, 1000)]

            + list(range(11, 13)))

        # give recorder and replayer some time to connect
        time.sleep(10)

        def replayer_stdin():
            for ts in timestamps:
                yield json.dumps({
                        'timestamp': ts,
                        'messages': [ts],
                        'subscription_id': channel
                    }).encode('utf8')

        rep_out, rep_err = replayer.communicate(input=b'\n'.join(replayer_stdin()))

        time.sleep(30)

        self.assertTrue(rerecorder.returncode is None)

        # double ctrl-c because we don't care about cleanup here
        for _ in range(2):
            rerecorder.send_signal(signal.SIGINT)

        rec_out, rec_err = rerecorder.communicate()

        pdus = []
        message_count = 0

        for line in rec_out.split(b'\n'):
            line = line.strip()
            if line:
                pdu = json.loads(line.decode('utf8'))
                message_count += len(pdu['messages'])
                pdus.append(pdu)

        # some pdus could contain multiple messages
        self.assertTrue(len(pdus) <= len(timestamps))

        if message_count != len(timestamps):
            print('Rerecorder stderr:{0}'.format(rec_err))

        # no messages are lost
        self.assertEqual(message_count, len(timestamps))

        first_offset = pdus[0]['timestamp'] - pdus[0]['messages'][0]
        for pdu in pdus:
            offset = pdu['timestamp'] - pdu['messages'][0]

            # offset is stable within 1 seconds
            self.assertTrue(
                offset + 0.5 > first_offset,
                (offset, "is far from", first_offset))
            self.assertTrue(
                offset - 0.5 < first_offset,
                (offset, "is far from", first_offset))

    def test_kv(self):
        cmd_prefix = ['python', 'satori_cli.py',
            '--appkey', appkey,
            '--endpoint', endpoint]

        channel = make_channel_name('test_kv')

        def read():
            return subprocess.check_output(cmd_prefix + ['read', channel]).rstrip()

        def write(value):
            return subprocess.check_output(cmd_prefix + ['write', channel, value])

        def delete():
            return subprocess.check_output(cmd_prefix + ['delete', channel])

        mailbox = []
        mailbox.append(delete())
        mailbox.append(write('v1'))
        mailbox.append(read())
        mailbox.append(delete())
        mailbox.append(read())
        mailbox.append(write('v2'))
        mailbox.append(write('v3'))
        mailbox.append(read())

        self.assertEqual(
            mailbox,
            [b'', b'', b'"v1"', b'', b'null', b'', b'', b'"v3"'])


def generic_test(self, should_authenticate=False):

    endpoint, appkey = get_test_endpoint_and_appkey('../credentials.json')

    auth_args = []
    if should_authenticate:
        auth_args = [
            '--role_name', 'superuser',
            '--role_secret', get_test_secret_key('../credentials.json')]

    publisher = subprocess.Popen(
        ['python', 'satori_cli.py',
            '--appkey', appkey,
            '--endpoint', endpoint,
            'publish', channel] + auth_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE)

    subscriber = subprocess.Popen(
        ['python', 'satori_cli.py',
            '--appkey', appkey,
            '--endpoint', endpoint,
            'subscribe', channel] + auth_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE)

    if subscriber.returncode is not None:
        (sub_out, sub_err) = subscriber.communicate()
        print(sub_out)
        print(sub_err)

    self.assertEqual(subscriber.returncode, None)

    time.sleep(5)

    try:
        publisher.stdin.write(string_message + b'\n')
        publisher.stdin.flush()

        time.sleep(1)

        publisher.stdin.write(json_message + b'\n')
        publisher.stdin.flush()

        time.sleep(1)

        publisher.send_signal(signal.SIGINT)
        (pub_out, pub_err) = publisher.communicate()

        self.assertEqual(0, publisher.returncode,
            "publisher failed with code {0}".format(publisher.returncode))
        self.assertEqual(
            u'\n'.join(
                [u'Sending input to {0}, press C-d or C-c to stop\n'.format(
                    channel.decode('utf8'))
                ]),
            pub_out.decode('utf8'))

        time.sleep(1)

        subscriber.send_signal(signal.SIGINT)
        (sub_out, sub_err) = subscriber.communicate()
        self.assertEqual(subscriber.returncode, 0,
            "subscriber failed with code {0}".format(subscriber.returncode))
        self.assertEqual(
            u'\n'.join(
                [u'{0}: "{1}"',
                 u'{0}: {2}\n',
                ]).format(
                    channel.decode('utf8'),
                    string_message.decode('utf8'),
                    json_message.decode('utf8')),
            sub_out.decode('utf8'))
    except Exception as e:
        try:
            print('Publisher out, err: {0}'.format(publisher.communicate()))
            print('Subscriber out, err: {0}'.format(subscriber.communicate()))
        except:
            pass
        raise e

if __name__ == '__main__':
    unittest.main()
