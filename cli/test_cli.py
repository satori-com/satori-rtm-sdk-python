#!/usr/bin/env python3

import json
import re
import signal
import subprocess
import sys
import time
import unittest

from test.utils import get_test_endpoint_and_appkey
from test.utils import get_test_role_name_secret_and_channel
from test.utils import make_channel_name

endpoint, appkey = get_test_endpoint_and_appkey('../credentials.json')
role, secret, restricted_channel =\
    get_test_role_name_secret_and_channel('../credentials.json')
string_message = make_channel_name('string').encode('utf8')
json_message = u'{{"text": ["{}", "message"]}}'.format(make_channel_name('m'))
json_message = json_message.encode('utf8')


class TestCLI(unittest.TestCase):
    def test_without_auth(self):
        generic_test(self, should_authenticate=False)

    def test_with_auth(self):
        generic_test(self, should_authenticate=True)

    def test_reconnect(self):
        def start_tcpkali():
            return subprocess.Popen(['tcpkali', '-T5s', '--ws', '-l', '8999'])
        tcpkali1 = start_tcpkali()

        satori_rtm_cli = subprocess.Popen(
            ['python', 'satori-rtm-cli',
                '--appkey', 'bogus',
                '--endpoint', 'ws://localhost:8999/',

                '--time_limit_in_seconds=8',
                'record', 'bogus'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        tcpkali1.communicate(timeout=20)

        satori_rtm_cli.poll()
        if satori_rtm_cli.returncode is not None:
            (out, err) = satori_rtm_cli.communicate(timeout=20)
            print('out:', out)
            print('err:', err)
            self.assertEqual(satori_rtm_cli.returncode, None)

        tcpkali2 = start_tcpkali()
        tcpkali2.communicate(timeout=20)

        (out, err) = satori_rtm_cli.communicate(timeout=20)
        if len(re.findall(b'on_enter_connected', err)) != 1:
            print('out:', out)
            raise RuntimeError(
                "Expected to find 'on_enter_connected' in {0}".format(err))

    def test_replayer_timing(self):

        channel = make_channel_name('replayer_timing')

        rerecorder = subprocess.Popen(
            ['python', 'satori-rtm-cli',
                '--appkey', appkey,
                '--endpoint', endpoint,

                'record', channel],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        replayer = subprocess.Popen(
            ['python', 'satori-rtm-cli',
                '--appkey', appkey,
                '--endpoint', endpoint,
                'replay'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        timestamps =\
            (list(range(0, 5)) +

                # range only works with ints, sorry
                [float(x) / 100 for x in range(600, 1000)]\
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

        replayer.communicate(timeout=20, input=b'\n'.join(replayer_stdin()))

        time.sleep(30)

        self.assertTrue(rerecorder.returncode is None)

        # double ctrl-c because we don't care about cleanup here
        for _ in range(2):
            rerecorder.send_signal(signal.SIGINT)

        rec_out, rec_err = rerecorder.communicate(timeout=20)

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
        cmd_prefix =\
            ['python', 'satori-rtm-cli', '--appkey', appkey,
                '--endpoint', endpoint]

        channel = make_channel_name('test_kv')

        def read():
            return subprocess.check_output(
                cmd_prefix + ['read', channel]).rstrip()

        def write(value):
            return subprocess.check_output(
                cmd_prefix + ['write', channel, value])

        def delete():
            return subprocess.check_output(
                cmd_prefix + ['delete', channel])

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

    if should_authenticate:
        auth_args = [
            '--role_name', role,
            '--role_secret', secret]
        channel = restricted_channel
    else:
        auth_args = []
        channel = make_channel_name('test_cli')

    publisher = subprocess.Popen(
        ['python', 'satori-rtm-cli',
            '--appkey', appkey,
            '--endpoint', endpoint,
            'publish', channel] + auth_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE)

    subscriber = subprocess.Popen(
        ['python', 'satori-rtm-cli',
            '--appkey', appkey,
            '--endpoint', endpoint,
            'subscribe', channel] + auth_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE)

    if subscriber.returncode is not None:
        (sub_out, sub_err) = subscriber.communicate(timeout=20)
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
        (pub_out, _) = publisher.communicate(timeout=20)

        self.assertEqual(
            0, publisher.returncode,
            "publisher failed with code {0}".format(publisher.returncode))
        self.assertEqual(
            u'Sending input to {0}, press C-d or C-c to stop\n'.format(
                channel),
            pub_out.decode('utf8'))

        time.sleep(1)

        subscriber.send_signal(signal.SIGINT)
        (sub_out, sub_err) = subscriber.communicate(timeout=20)
        self.assertEqual(
            subscriber.returncode, 0,
            "subscriber failed with code {0}".format(subscriber.returncode))

        u_string_message = string_message.decode('utf8')
        u_json_message = json_message.decode('utf8')
        u_sub_out = sub_out.decode('utf8')
        self.assertTrue(
            u'{0}: "{1}"'.format(channel, u_string_message) in u_sub_out,
            u_sub_out)
        self.assertTrue(
            u'{0}: {1}'.format(channel, u_json_message) in u_sub_out,
            u_sub_out)
    except Exception as e:
        e_type, e_value, e_traceback = sys.exc_info()
        try:
            print('Publisher out, err: {0}'.format(publisher.communicate(timeout=20)))
            print('Subscriber out, err: {0}'.format(subscriber.communicate(timeout=20)))
        except Exception:
            pass
        raise Exception from e


if __name__ == '__main__':
    unittest.main()
