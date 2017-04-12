from __future__ import print_function

import sys
from threading import Event

from satori.rtm.client import make_client, SubscriptionMode
import satori.rtm.auth as auth

# Replace these values with your project's credentials
# from DevPortal (https://developer.satori.com/#/projects).
endpoint = 'ENDPOINT'
appkey = 'APPKEY'
role = 'ROLE'
secret = 'SECRET'

channel = 'my_channel'
message = {'Hello': 'world'}

def main():

    print('Creating RTM client instance')
    auth_delegate = auth.RoleSecretAuthDelegate(role, secret)

    with make_client(
            endpoint=endpoint, appkey=appkey,
            auth_delegate=auth_delegate) as client:

        # Here the 'with make_client' inner scope begins
        # it means that 'client' is already connected and
        # since we have passed auth_delegate to make_client
        # 'client' is also already authenticated.

        print('Subscribing to a channel')

        # client.subscribe(...) method is asynchronous so we need
        # to perform synchronization ourself in order not to begin
        # publishing until the subscription is established.
        # Here we use an 'Event' object from the standard 'threading' module
        # See https://docs.python.org/2/library/threading.html#event-objects
        # for reference if you're not familiar with the concept.

        subscribed_event = Event()
        got_message_event = Event()

        # In order to observe a subscription, that is to see the incoming
        # data, state changes and errors, we must have a subscription observer
        # object.

        class SubscriptionObserver(object):

            # This callback allows us to know when the subscription
            # is established.
            def on_enter_subscribed(self):
                subscribed_event.set()

            # This callback allows us to observe incoming messages
            def on_subscription_data(self, data):
                for message in data['messages']:
                    print('Client got message {0}'.format(message))
                got_message_event.set()

        subscription_observer = SubscriptionObserver()

        # Send subscribe request (remember, it's asyncronous)
        client.subscribe(
            channel,
            SubscriptionMode.SIMPLE,
            subscription_observer)

        if not subscribed_event.wait(10):
            print("Couldn't establish the subscription in time")
            sys.exit(1)

        # At this point we're subscribed

        # client.publish(...) method is also asynchronous, again we
        # use an 'Event' to wait until we have a reply for publish
        # request.
        publish_finished_event = Event()

        # In case of publishing, there's no observer object involved because
        # the process is simpler: we're guaranteed to receive exactly one
        # reply callback and need only to inspect it to see if it's an OK or
        # an error.
        # See 'Publish PDU' section at
        # https://www.satori.com/docs/references/rtm-api for reference.
        def publish_callback(ack):
            if ack['action'] == 'rtm/publish/ok':
                print('Publish OK')
                publish_finished_event.set()
            elif ack['action'] == 'rtm/publish/ok':
                print(
                    'Publish request failed, error {0}, reason {1}'.format(
                        ack['body']['error'], ack['body']['reason']))
                sys.exit(1)
            else:
                print('Unrecognized publish ack: {0}'.format(ack))
                sys.exit(1)

        client.publish(
            channel, message=message, callback=publish_callback)

        if not publish_finished_event.wait(10):
            print("Couldn't publish the message in time")
            sys.exit(1)

        # At this point we have successfully published the message
        # (we know this because we just received a PDU with 'rtm/publish/ok'
        # and even may have already gotten that message back via the
        # subscription. Either can come first or second.

        if not got_message_event.wait(10):
            print("Couldn't receive the message in time")
            sys.exit(1)

        # At this point we have definitely received the message
        # and printed it to stdout (via code in on_subscription_data callback)

        print('Unsubscribing from a channel')
        client.unsubscribe(channel)

        # here the 'with make_client' inner scope ends
        # this triggers the disconnect from RTM
        # and destruction of the 'client' object

if __name__ == '__main__':
    main()