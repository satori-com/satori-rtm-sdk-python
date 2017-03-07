#!/usr/bin/env python3

from functools import wraps
import statistics as s
import sys
import time

from miniws4py.client import WebSocketBaseClient

import satori.rtm.connection as conn
from satori.rtm.client import make_client
from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()

if '--insecure' in sys.argv:
    endpoint = endpoint.replace('wss://', 'ws://')

experiments = {}

def timing(f, label=None):
    @wraps(f)
    def wrap(*args, **kw):
        before = time.time() * 1000
        result = f(*args, **kw)
        after = time.time() * 1000
        if not label in experiments:
            experiments[label] = []
        experiments[label].append(after - before)
        return result
    return wrap

conn.Connection.start = timing(conn.Connection.start, label='SDK.Connection.start')
WebSocketBaseClient.__init__ = timing(WebSocketBaseClient.__init__, label='WS.__init__')
conn.RtmWsClient.connect = timing(conn.RtmWsClient.connect, label='WS.connect')

def f():
    with make_client(endpoint, appkey):
        pass
f = timing(f, label='SDK.make_client')

for i in range(10):
    f()

print('Method | Time, ms')
for label in ['WS.__init__', 'WS.connect', 'SDK.Connection.start', 'SDK.make_client']:
    timings = experiments[label]
    print("{} | {:4.1f} ± {:4.1f}".format(label, s.mean(timings), s.pstdev(timings)))