#!/usr/bin/env python3

from collections import namedtuple as t
import json
import os
from subprocess import Popen, PIPE
import time

from test.utils import get_test_endpoint_and_appkey
_, test_appkey = get_test_endpoint_and_appkey()

PubAckConfig = t('PubAckConfig', ['size', 'tls', 'accel'])
PubNoAckConfig = t('PubNoAckConfig', ['size', 'tls', 'accel'])
SubConfig = t('SubConfig', ['size', 'tls', 'accel'])

ws_endpoint = "ws://rtm.local/"
wss_endpoint = "wss://rtm.local/"
script_dir = os.path.dirname(os.path.realpath(__file__))

sizes = [128, 512, 1024]
duration = 60
channel = 'py'

channel = 'lol'


def main():
    config_list = list(configs())
    for i, conf in enumerate(config_list):
        print('Bench {} out of {}'.format(i + 1, len(config_list)))
        cmd = conf_to_cmd(conf)

        print('Running', cmd)

        if type(conf) == SubConfig:
            tcpkali = start_tcpkali(conf.size)
            time.sleep(2)

        p = Popen(cmd, stdout=PIPE, shell=True)
        time.sleep(duration)
        p.terminate()
        out, err = p.communicate()

        if type(conf) == SubConfig:
            stop_tcpkali(tcpkali)

        filename = conf_to_filename(conf)

        with open(filename, 'wb') as fo:
            fo.write(out)


def start_tcpkali(size):
    pdu = {'action':'rtm/publish',
        'body': {
            'channel': channel,
            'message': '0' * size
        }}
    # target 50 MB/s of useful data
    rate = 50000000 // size
    url = ws_endpoint.replace('ws://', '').replace('/', ':80/')
    url += '?appkey=' + test_appkey
    cmd = ['tcpkali',
        '-r', str(rate),
        '--ws', url,
        '-T365d',
        '-m', json.dumps(pdu)]
    print('Launching tcpkali:', cmd)
    return Popen(cmd)


def stop_tcpkali(p):
    p.terminate()


def conf_to_cmd(conf):
    cmd = os.path.join(script_dir, 'bench.py')

    if conf.tls:
        cmd += ' --endpoint ' + wss_endpoint
    else:
        cmd += ' --endpoint ' + ws_endpoint

    if conf.accel:
        cmd += ' --wsaccel'

    if type(conf) == PubAckConfig:
        cmd += ' --scenario publish-ack-' + str(conf.size)
    elif type(conf) == PubNoAckConfig:
        cmd += ' --scenario publish-noack-' + str(conf.size)
    elif type(conf) == SubConfig:
        cmd += ' --scenario subscribe --channel ' + channel
    return cmd


def conf_to_filename(conf):
    result = ''

    if type(conf) == PubAckConfig:
        result += 'publish-ack'
    elif type(conf) == PubNoAckConfig:
        result += 'publish-noack'
    elif type(conf) == SubConfig:
        result += 'subscribe'

    result += '-accel' if conf.accel else '-noaccel'
    result += '-tls' if conf.tls else '-notls'
    result += '-' + str(conf.size)
    return result


def configs():
    for accel in [True, False]:
        for tls in [True, False]:
            for size in sizes:
                yield PubAckConfig(size, tls, accel)
                yield PubNoAckConfig(size, tls, accel)
                yield SubConfig(size, tls, accel)


if __name__ == '__main__':
    main()
