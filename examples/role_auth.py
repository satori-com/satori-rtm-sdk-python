#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import threading

import satori.rtm.auth as auth
from satori.rtm.client import make_client
from test.utils import get_test_endpoint_and_appkey, get_test_secret_key

message = 'hello'
channel = 'whatever'
role = 'superuser'
secret = get_test_secret_key()
endpoint, appkey = get_test_endpoint_and_appkey()


def main():
    with make_client(
            endpoint=endpoint,
            appkey=appkey) as client:

        auth_finished_event = threading.Event()
        auth_delegate = auth.RoleSecretAuthDelegate(role, secret)

        def auth_callback(auth_result):
            if type(auth_result) == auth.Done:
                print('Auth success')
                auth_finished_event.set()
            else:
                print('Auth failure: {0}'.format(auth_result))
                sys.exit(1)

        client.authenticate(auth_delegate, auth_callback)

        if not auth_finished_event.wait(60):
            raise RuntimeError('Auth never finished')

        #
        # At this point we are authenticated and can publish
        #

        publish_finished_event = threading.Event()

        def publish_callback(ack):
            print('Publish ack:', ack)
            publish_finished_event.set()

        client.publish(
            channel, message=message, callback=publish_callback)

        if not publish_finished_event.wait(60):
            raise RuntimeError('Publish never finished')


if __name__ == '__main__':
    main()
