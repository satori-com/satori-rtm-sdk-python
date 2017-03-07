#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import threading

import satori.rtm.auth as auth
from satori.rtm.client import make_client
from test.utils import get_test_endpoint_and_appkey, get_test_secret_key

message = 'hello'
channel = 'whatever'
role = 'superuser'
secret_key = get_test_secret_key()
endpoint, appkey = get_test_endpoint_and_appkey()


def main():
    with make_client(
            endpoint=endpoint,
            appkey=appkey) as client:

        auth_event = threading.Event()
        auth_delegate = auth.RoleSecretAuthDelegate(role, secret_key)

        def auth_callback(auth_result):
            if type(auth_result) == auth.Done:
                print('Auth success')
                auth_event.set()
            else:
                print('Auth failure: {0}'.format(auth_result))
                auth_event.set()

        client.authenticate(auth_delegate, auth_callback)

        if not auth_event.wait(60):
            raise RuntimeError('Auth never finished')

        exit = threading.Event()

        def publish_callback(ack):
            print('Publish ack:', ack)
            exit.set()

        client.publish(
            channel, message=message, callback=publish_callback)

        if not exit.wait(60):
            raise RuntimeError('Publish never finished')


if __name__ == '__main__':
    main()
