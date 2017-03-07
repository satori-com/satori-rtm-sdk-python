#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import six
import sys

from satori.rtm.client import make_client

from common import in_chat, endpoint, appkey


def main():

    if len(sys.argv) != 3:
        print('Usage: {0} <name> <channel>'.format(sys.argv[0]))
        sys.exit(1)

    nick, channel = sys.argv[1:]
    with make_client(endpoint=endpoint, appkey=appkey) as platform:
        with in_chat(nick, channel, platform) as chat:
            while True:
                cmd = six.moves.input()
                if cmd == '/quit':
                    break
                if cmd == '/emulate_disconnect':
                    platform.connection.stop()
                    continue
                chat.say(cmd)


if __name__ == '__main__':
    main()
