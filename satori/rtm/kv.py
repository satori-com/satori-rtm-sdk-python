
import requests
import json
import os.path

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus


class KVError(Exception):
    def __init__(self, pdu):
        Exception.__init__(self)
        self.code = pdu['body']['code']
        self.reason = pdu['body']['reason']


class KV(object):
    def __init__(self, endpoint, appkey):
        if endpoint.startswith('ws://'):
            endpoint = 'http://' + endpoint[5:]
        elif endpoint.startswith('wss://'):
            endpoint = 'https://' + endpoint[6:]
        self.endpoint = endpoint
        self.appkey = appkey

    def make_url(self, key):
        url = os.path.join(self.endpoint, 'v2/kv', quote_plus(key))
        return url + '?id=0&appkey=' + self.appkey

    def read_with_position(self, k):
        url = self.make_url(k)
        resp = requests.get(url).text
        reply_pdu = json.loads(resp)
        if reply_pdu['action'] == 'rtm/read/error':
            raise KVError(reply_pdu)
        return reply_pdu['body']

    def read(self, k):
        return self.read_with_position(k)['message']

    def write(self, k, v):
        url = self.make_url(k)
        reply_pdu = json.loads(requests.put(url, data=json.dumps(v)).text)
        if reply_pdu['action'] == 'rtm/write/error':
            raise KVError(reply_pdu)
        return reply_pdu['body']['position']

    def delete(self, k):
        url = self.make_url(k)
        reply_pdu = json.loads(requests.delete(url).text)
        if reply_pdu['action'] == 'rtm/delete/error':
            raise KVError(reply_pdu)