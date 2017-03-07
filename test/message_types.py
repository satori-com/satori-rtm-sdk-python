# -*- coding: utf-8 -*-

from __future__ import print_function

import random
import unittest
from satori.rtm.client import make_client

from test.utils import make_channel_name, sync_subscribe, sync_publish
from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()
channel = make_channel_name('message_types')

basic_messages =\
    [None, 42, 3.1415, 'hello', True, False, [], {}, '', u'Сообщение']
dict_messages = [{'key': m} for m in basic_messages]
list_messages =\
    [[random.choice(basic_messages + dict_messages)
        for _ in range(len)] for len in range(1, 5)]


class TestMessageTypes(unittest.TestCase):
    def test_all_types(self):
        messages = basic_messages + dict_messages + list_messages

        with make_client(endpoint=endpoint, appkey=appkey) as client:
            so = sync_subscribe(client, channel)

            for msg in messages:
                sync_publish(client, channel, msg)
                so.wait_for_channel_data()

            got_messages = []
            for x in so.log:
                try:
                    got_messages += x[1]['messages']
                except:
                    pass

            self.assertEqual(messages, got_messages)


if __name__ == '__main__':
    unittest.main()