# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest

from satori.rtm.client import make_client

from test.utils import get_test_endpoint_and_appkey

endpoint, _appkey = get_test_endpoint_and_appkey()


class TestConnectionError(unittest.TestCase):
    def test_invalid_appkey(self):
        with self.assertRaises(RuntimeError):
            with make_client(endpoint=endpoint, appkey='invalid_appkey'):
                pass


if __name__ == '__main__':
    unittest.main()