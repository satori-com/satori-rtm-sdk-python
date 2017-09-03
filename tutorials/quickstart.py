from __future__ import print_function

import random
import sys
import time

from satori.rtm.client import make_client, SubscriptionMode
import satori.rtm.auth as auth

# For tutorial purposes, we subscribe to the same channel that we publish a
# message to. So we receive our own published message. This allows end-to-end
# illustration of data flow with just a single client.

# Replace these values with your project's credentials
# from Dev Portal (https://developer.satori.com/#/projects).
endpoint = 'YOUR_ENDPOINT'
appkey = 'YOUR_APPKEY'

# Role and secret are optional: replace only if you need to authenticate.
role = u'YOUR_ROLE'
role_secret_key = u'YOUR_SECRET'

channel = u'animals'


def main():
    import logging
    logging.basicConfig(level=logging.WARNING)

    should_authenticate = role and role_secret_key\
        and role_secret_key != 'YOUR_SECRET'
    if should_authenticate:
        auth_delegate = auth.RoleSecretAuthDelegate(role, role_secret_key)
    else:
        auth_delegate = None

    print("RTM client config:")
    print("\tendpoint =", endpoint)
    print("\tappkey =", appkey)
    if should_authenticate:
        print("\tauthenticate? = True (as {0})".format(role))
    else:
        print("\tauthenticate? = False")

    with make_client(
            endpoint=endpoint, appkey=appkey,
            auth_delegate=auth_delegate) as client:
        # Entering here means that 'client' has already connected and
        # also authenticated (because we have passed auth_delegate to
        # make_client)

        print('Connected to Satori RTM!')

        # We create a subscription observer object in order to receive callbacks
        # for incoming data, state changes and errors.

        class SubscriptionObserver(object):

            # Called when the subscription is established.
            def on_enter_subscribed(self):
                print('Subscribed to the channel: ' + channel)

            def on_enter_failed(self, reason):
                print('Subscription failed, reason:', reason)
                sys.exit(1)

            # This callback allows us to observe incoming messages
            def on_subscription_data(self, data):
                for message in data['messages']:
                    print('Animal is received:', message)

        subscription_observer = SubscriptionObserver()

        # Send subscribe request. This call is asynchronous:
        # client implementation internally queues the request and lets the
        # function exit. Request is then processed from a background thread,
        # while our main thread goes on.
        client.subscribe(
            channel,
            SubscriptionMode.SIMPLE,
            subscription_observer)

        print('\nPress CTRL-C to exit\n')

        try:
            while True:
                coords = [
                    34.134358 + random.random(),
                    -118.321506 + random.random()]
                animal = {u'who': u'zebra', u'where': coords}

                # In case of publishing, there's no observer object involved
                # because the process is simpler: we're guaranteed to receive
                # exactly one reply callback and need only to inspect it to see
                # if it's an OK or an error. See 'Publish PDU' section at
                # https://www.satori.com/docs/references/rtm-api for reference.
                def publish_callback(ack):
                    if ack['action'] == 'rtm/publish/ok':
                        print('Animal is published:', animal)
                    elif ack['action'] == 'rtm/publish/error':
                        print(
                            'Publish failed, error {0}, reason {1}'.format(
                                ack['body']['error'], ack['body']['reason']))

                client.publish(
                    channel, message=animal, callback=publish_callback)

                sys.stdout.flush()
                time.sleep(2)
        except KeyboardInterrupt:
            pass

        # Exiting 'with make_client' triggers the disconnect from RTM
        # and destruction of the 'client' object


if __name__ == '__main__':
    main()
