#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import curses
import six
import sys
import threading
import time

from satori.rtm.client import make_client, SubscriptionMode
from threading import Event
from test.utils import get_test_endpoint_and_appkey

endpoint, appkey = get_test_endpoint_and_appkey()
announce_interval = 5


class ChatState(object):
    def __init__(self, name, channel):
        self.channel = channel
        self.history = []
        self.users = {name: time.time()}
        self.input_buffer = b""


def to_unicode(s):
    if isinstance(s, six.text_type):
        return s
    else:
        return s.decode('utf8')


def main():
    (name, channel) = [to_unicode(s) for s in sys.argv[1:3]]

    with make_client(endpoint=endpoint, appkey=appkey) as client:

        time_to_announce_leaving = Event()
        time_to_exit = Event()

        def presence():
            client.publish(
                channel + '.presence',
                {'name': name, 'status': 'joined'})

            while True:
                client.publish(
                    channel + '.presence',
                    {'name': name, 'status': 'alive'})

                if time_to_announce_leaving.wait(announce_interval):
                    client.publish(
                        channel + '.presence',
                        {'name': name, 'status': 'leaving'})
                    time_to_exit.set()
                    break

        presence_announcing_thread = threading.Thread(target=presence)
        presence_announcing_thread.daemon = True
        presence_announcing_thread.start()

        chat_state = ChatState(name, channel)

        class MessageChannelObserver(object):
            def on_subscription_data(self, data):
                for m in data['messages']:
                    chat_state.history.append(m)

        class PresenceChannelObserver(object):
            def on_subscription_data(self, data):
                now = time.time()

                def add_user(username):
                    if username not in chat_state.users:
                        chat_state.history.append(
                            u'{0} has joined #{1}'.format(
                                username, channel))
                    chat_state.users[username] = now

                for m in data['messages']:
                    if m['status'] == 'joined':
                        add_user(m['name'])
                        client.publish(
                            channel + '.presence',
                            {'name': name, 'status': 'alive'})
                    if m['status'] == 'leaving':
                        try:
                            del chat_state.users[m['name']]
                        except Exception:
                            pass
                        chat_state.history.append(
                            u'{0} has left #{1}'.format(
                                m['name'], channel))
                    else:
                        add_user(m['name'])

                lost_users = []
                for user, last_seen in chat_state.users.items():
                    if now - last_seen > 3 * announce_interval:
                        lost_users.append(user)
                for user in lost_users:
                    chat_state.history.append(
                        '{0} has disconnected'.format(
                            user, channel))
                    del chat_state.users[user]

        client.subscribe(
            channel,
            SubscriptionMode.SIMPLE,
            MessageChannelObserver())
        client.subscribe(
            channel + '.presence',
            SubscriptionMode.SIMPLE,
            PresenceChannelObserver())

        try:
            screen = curses.initscr()
            curses.noecho()
            curses.cbreak()
            curses.start_color()
            screen.nodelay(1)
            screen.keypad(1)
            while True:
                ch = screen.getch()
                try:
                    if ch == curses.ERR:
                        time.sleep(1.0 / 30.0)
                    elif ch == curses.KEY_RESIZE:
                        pass
                    elif ch == ord('\n'):
                        if not chat_state.input_buffer:
                            continue

                        if chat_state.input_buffer == b'/quit':
                            time_to_announce_leaving.set()
                            break

                        client.publish(
                            channel,
                            {'user': name,
                             'message':
                                 chat_state.input_buffer.decode('utf8')})
                        chat_state.input_buffer = b""
                    elif ch in [curses.KEY_BACKSPACE, curses.KEY_DC]:
                        chat_state.input_buffer = chat_state.input_buffer[:-1]
                    else:
                        chat_state.input_buffer += bytes(bytearray([ch]))
                    render(chat_state, screen)
                except KeyboardInterrupt:
                    time_to_announce_leaving.set()
                    break
        finally:
            screen.keypad(0)
            curses.echo()
            curses.nocbreak()
            curses.endwin()

        time_to_exit.wait(10)


def render(chat_state, screen):
    h, w = screen.getmaxyx()
    screen.erase()
    render_header(chat_state.channel, screen, 0, 0, w, 1)
    render_users(chat_state.users, screen, 0, 2, 20, h - 4)
    render_chat(
        chat_state.users, chat_state.history, screen, 20, 2, w - 20, h - 4)
    render_input_area(chat_state.input_buffer, screen, 0, h - 1, w, 2)
    screen.refresh()


def render_header(channel, screen, x, y, w, h):
    screen.addstr(0, (w - len(channel)) // 2, channel.encode('utf8'))


def render_users(users, screen, x, y, w, h):
    screen.addstr(y, x + 1, 'Users:')
    for (i, user) in enumerate(users):
        screen.addstr(y + 2 + i, x + 1, user.encode('utf8'))


def render_chat(users, history, screen, x, y, w, h):
    for (i, a) in enumerate(history[-h:]):
        buffer = []
        if 'user' in a:
            if a['user'] in users:
                user_attr = curses.A_BOLD
            else:
                user_attr = curses.A_NORMAL
            if a['message'].startswith('/me '):
                text = '* {0} {1}'.format(a['user'], a['message'][4:])
                buffer = [
                    ('* ', curses.A_NORMAL),
                    (a['user'], user_attr),
                    (u' {0}'.format(a['message'][4:]), curses.A_NORMAL)]
            else:
                buffer = [
                    (a['user'], user_attr),
                    (u'> {0}'.format(a['message']), curses.A_NORMAL)]
        else:
            buffer = [(u'* {0}'.format(a), curses.A_NORMAL)]
        x_ = x + 1
        for (text, attr) in buffer:
            if not isinstance(text, six.binary_type):
                text = text.encode('utf8')
            screen.addstr(y + 1 + i, x_, text, attr)
            x_ += len(text.decode('utf8'))


def render_input_area(input_buffer, screen, x, y, w, h):
    screen.addstr(y, x + 1, b'> ' + input_buffer)


if __name__ == '__main__':
    main()
