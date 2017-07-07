# -*- coding: utf-8 -*-

from __future__ import print_function

from contextlib import contextmanager
import logging
import sys
import threading
from satori.rtm.client import SubscriptionMode
from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()


@contextmanager
def in_chat(*args, **kwargs):
    chat = Chat(*args, **kwargs)
    try:
        yield chat
    finally:
        chat.leave()


class Chat(object):

    def __init__(self, nick, channel, platform_client):
        self.nick = nick
        if isinstance(channel, bytes):
            self.channel = channel.decode('utf8')
        else:
            self.channel = channel
        self.client = platform_client

        self.after_subscribe_event = threading.Event()
        self.after_unsubscribe_event = threading.Event()

        platform_client.subscribe(
            channel_or_subscription_id=self.channel,
            mode=SubscriptionMode.ADVANCED,
            subscription_observer=self)

        if not self.after_subscribe_event.wait(10):
            raise RuntimeError('Timeout while subscribing to chat channel')

    def on_enter_subscribed(self):
        join_line = u'{0} joined the channel'.format(self.nick)

        def exit(ack):
            if not ack['action'] == 'rtm/publish/ok':
                logging.error('Failed to publish join message to chat channel')
            self.after_subscribe_event.set()

        self.client.publish(
            self.channel,
            message=join_line,
            callback=exit)

    def on_subscription_data(self, data):
        for message in data['messages']:
            print(message)
            sys.stdout.flush()

    def leave(self):
        leave_line = '{0} left the channel'.format(self.nick)
        self.after_unsubscribe_event.clear()

        def unsub(ack):
            if ack['action'] == 'rtm/publish/ok':
                self.client.unsubscribe(self.channel)
            else:
                logging.error('Failed to publish exit message to chat channel')
                self.after_unsubscribe_event.set()

        self.client.publish(
            self.channel,
            message=leave_line,
            callback=unsub)

        if not self.after_unsubscribe_event.wait(10):
            raise RuntimeError('Timeout while announcing leaving the chat')

    def on_enter_unsubscribed(self):
        self.after_unsubscribe_event.set()

    def say(self, message):
        chat_line = '{0}> {1}'.format(self.nick, message)
        say_complete = threading.Event()

        def message_sent(ack):
            say_complete.set()

        self.client.publish(
            self.channel,
            message=chat_line,
            callback=message_sent)

        if not say_complete.wait(10):
            raise RuntimeError('Timeout while saying "{0}"'.format(message))
