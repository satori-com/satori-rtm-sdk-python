from __future__ import print_function

import sys
from threading import Event

from satori.rtm.client import make_client, SubscriptionMode
import satori.rtm.auth as auth

# For tutorial purposes, we subscribe to the same channel that we publish a
# message to. So we receive our own published message. This allows end-to-end
# illustration of data flow with just a single client.

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

        # Entering here means that 'client' has already connected and
        # also authenticated (because we have passed auth_delegate to
        # make_client)

        print('Subscribing to a channel')

        # At this point we need to be aware of two facts:
        # 1. client.subscribe(...) method is asynchronous
        # 2. We want to receive the message we are publishing ourselves
        #
        # That means that we must publish the message *only after* we get
        # a confirmation that subscription is established (this is not a
        # general principle: some applications may not care to receive the
        # messages they publish).

        # We use an `Event` object from the standard 'threading' module, which
        # is a mechanism for communication between threads: one thread
        # signals an event and other threads wait for it.

        subscribed_event = Event()
        got_message_event = Event()

        # We create a subscription observer object in order to receive callbacks
        # for incoming data, state changes and errors.

        class SubscriptionObserver(object):

            # Called when the subscription is established.
            def on_enter_subscribed(self):
                subscribed_event.set()

            # This callback allows us to observe incoming messages
            def on_subscription_data(self, data):
                for message in data['messages']:
                    print('Client got message {0}'.format(message))
                got_message_event.set()

        subscription_observer = SubscriptionObserver()

        # Send subscribe request. This call is asynchronous:
        # client implementation internally queues the request and lets the
        # function exit. Request is then processed from a background thread,
        # while our main thread goes on.
        client.subscribe(
            channel,
            SubscriptionMode.SIMPLE,
            subscription_observer)

        # Wait on a subscribed_event is going to put our main thread to sleep
        # (block).  As soon as SDK invokes our on_enter_subscribed callback
        # (from a background thread),  the callback notifies this event (`set`),
        # which wakes up the main thread.  To avoid indefinite hang in case of a
        # failure, the wait is limited to 10 second timeout.
        # The result value of `wait` indicates notification (True)
        # or timeout (False).
        if not subscribed_event.wait(10):
            print("Couldn't establish the subscription in time")
            sys.exit(1)

        # At this point we're subscribed

        # client.publish(...) method is also asynchronous, again we
        # use an 'Event' to wait until we have a reply for publish
        # request or timeout.
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
            elif ack['action'] == 'rtm/publish/error':
                print(
                    'Publish request failed, error {0}, reason {1}'.format(
                        ack['body']['error'], ack['body']['reason']))
                sys.exit(1)

        client.publish(
            channel, message=message, callback=publish_callback)

        if not publish_finished_event.wait(10):
            print("Couldn't publish the message in time")
            sys.exit(1)

        # At this point we have successfully published the message
        # (we know this because we just received a PDU with 'rtm/publish/ok')
        # and we even may have already received that message back via the
        # subscription. Publish confirmation could come after or before the
        # subscription data.

        if not got_message_event.wait(10):
            print("Couldn't receive the message in time")
            sys.exit(1)

        # At this point we have received the message
        # and printed it to stdout (in on_subscription_data callback code)

        print('Unsubscribing from a channel')
        client.unsubscribe(channel)

        # Exiting 'with make_client' triggers the disconnect from RTM
        # and destruction of the 'client' object

if __name__ == '__main__':
    main()