#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import threading

import satori.rtm.auth as auth
from satori.rtm.client import make_client
from test.utils import get_test_endpoint_and_appkey
from test.utils import get_test_role_name_secret_and_channel

message = 'hello'
role, secret, restricted_channel =\
    get_test_role_name_secret_and_channel()
endpoint, appkey = get_test_endpoint_and_appkey()


def main():
    ad = auth.RoleSecretAuthDelegate(role, secret)
    with make_client(
            endpoint=endpoint,
            appkey=appkey,
            auth_delegate=ad) as client:

        #
        # At this point we are already authenticated and can publish
        #

        publish_finished_event = threading.Event()

        def publish_callback(ack):
            print('Publish ack:', ack)
            publish_finished_event.set()

        client.publish(
            restricted_channel, message=message, callback=publish_callback)

        if not publish_finished_event.wait(60):
            raise RuntimeError('Publish never finished')


if __name__ == '__main__':
    main()
