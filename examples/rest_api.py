#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import json
from satori.rtm.kv import KV

endpoint = "YOUR_ENDPOINT"
appkey = "YOUR_APPKEY"


def main():
    kv = KV(endpoint, appkey)

    kv.write('zebra', {'stripe_count': 101})

    # rewrite
    kv.write('zebra', {'stripe_count': 101})

    # read to get the last written value
    zebra = kv.read('zebra')

    print(json.dumps(zebra, indent=4))

    # delete
    kv.delete('zebra')

    # reading after delete yields None
    no_animal = kv.read('zebra')


if __name__ == '__main__':
    main()
