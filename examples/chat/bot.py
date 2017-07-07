#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import random
import sys
import time

from satori.rtm.client import make_client

from common import in_chat, endpoint, appkey

message = 'hello'


def main():

    if len(sys.argv) != 4:
        print('Usage: {0} <name> <channel> <chattiness>'.format(sys.argv[0]))
        sys.exit(1)

    nick, channel = sys.argv[1:3]
    with make_client(
            endpoint=endpoint, appkey=appkey) as client:
        with in_chat(nick, channel, client) as chat:
            chat.say(u'Hi!')
            for _ in range(int(sys.argv[3])):
                time.sleep(random.randint(1, 3))
                chat.say(random.choice((u'Zero', u'One')))
            chat.say(u'Bye.')


if __name__ == '__main__':
    main()
