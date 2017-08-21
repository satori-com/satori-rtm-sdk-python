#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys

import satori.rtm.auth as auth
from satori.rtm.exceptions import AuthError
from satori.rtm.client import make_client

endpoint = "YOUR_ENDPOINT"
appkey = "YOUR_APPKEY"
role = "YOUR_ROLE"
role_secret_key = "YOUR_SECRET"


def main():
    import logging
    logging.basicConfig(level=logging.WARNING)

    auth_delegate = auth.RoleSecretAuthDelegate(role, role_secret_key)

    try:
        with make_client(
                endpoint=endpoint,
                appkey=appkey,
                auth_delegate=auth_delegate) as client:

            print('Connected to Satori RTM and authenticated as', role)
    except AuthError as e:
        print('Failed to authenticate:', e, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print('Error occurred:', e, file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
