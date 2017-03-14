# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client


class TestBadSSL(unittest.TestCase):
    def test_self_signed(self):
        assert self._bad_ssl('self-signed', 'certificate verify failed')

    def test_expired(self):
        assert self._bad_ssl('expired', 'certificate verify failed')

    def test_wrong_host(self):
        assert self._bad_ssl(
            'wrong.host',
            "wrong.host.badssl.com' doesn't match")

    def _bad_ssl(self, prefix, message):
        endpoint = 'wss://{0}.badssl.com'.format(prefix)
        try:
            with make_client(endpoint=endpoint, appkey='dummy') as client:
                client.subscribe(channel='test')
            return False
        except RuntimeError as e:
            is_expected_error = message in str(e)
            if not is_expected_error:
                print(str(e))
            return is_expected_error
        except Exception as e:
            print(str(e))
            return False


if __name__ == '__main__':
    unittest.main()
