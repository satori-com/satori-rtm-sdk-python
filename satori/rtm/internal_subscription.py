
# -*- coding: utf-8 -*-

from __future__ import print_function
import threading
from enum import Enum

from satori.rtm.logger import logger

from satori.rtm.internal_state_machine_wrapper import StateMachineWrapper
import satori.rtm.generated.subscription_sm as sm


class SubscriptionMode(Enum):
    TRACK_POSITION = 1
    FAST_FORWARD = 2
    ADVANCED = TRACK_POSITION
    SIMPLE = FAST_FORWARD
    RELIABLE = TRACK_POSITION | FAST_FORWARD


def _lint_args(args):
    if not args:
        return
    if args.get('fast_forward') is not None:
        logger.error(
            'Setting "fast_forward" in "args" parameter '
            'is deprecated. Choose appropriate subscription mode instead.')
    if args.get('channel') is not None:
        logger.error(
            'Setting "channel" in "args" parameter is not supported')


class Subscription(object):
    def __init__(
            self, delivery_mode,
            send_subscribe_request, send_unsubscribe_request,
            args=None, observer=None):
        self._mode = 'linked'

        _lint_args(args)
        self._args = args

        self._delivery_mode = delivery_mode
        self._send_subscribe_request_ = send_subscribe_request
        self._send_unsubscribe_request_ = send_unsubscribe_request
        self._connected = False
        self.observer = observer
        self._next_observer = None
        self._next_args = {}
        self._sm = StateMachineWrapper(sm.Subscription_sm, self)
        self._lock = self._sm.lock
        self._last_error = None
        self._sm.advance(lambda sm: sm.ModeChange())

    def _set_last_error(self, reason):
        self._last_error = reason

    def is_failed(self):
        return self._sm.get_state_name() == 'Subscription.Failed'

    def subscribe(self, args=None, observer=None):
        with self._lock:
            logger.debug('subscribe')

            if self._mode in ['linked', 'cycle']:
                logger.error('Already subscribed or trying to')
                return

            if self._next_observer:
                try:
                    self._next_observer.on_deleted()
                except Exception:
                    pass

            self._next_observer = observer
            self._next_args = args
            self._mode = 'cycle'

            return self._sm.advance(lambda sm: sm.ModeChange())

    def unsubscribe(self):
        with self._lock:
            self._args = None
            if self.is_failed():
                self._mode = 'unlinked'
                self._sm.advance(lambda sm: sm.UnsubscribeOK())
            else:
                logger.debug('unsubscribe')
                self._mode = 'unlinked'
                self._sm.advance(lambda sm: sm.ModeChange())

    def deleted(self):
        if self._mode == 'unlinked':
            return self._sm.get_state_name() == 'Subscription.Unsubscribed'

    def _is_mode_linked(self):
        return self._mode == 'linked'

    def _is_mode_not_linked(self):
        return not self._is_mode_linked()

    def _is_mode_not_unlinked(self):
        return not self._is_mode_unlinked()

    def _is_mode_unlinked(self):
        return self._mode == 'unlinked'

    def _is_fatal_channel_error(self, error_body):
        if not (self._delivery_mode.value &
                SubscriptionMode.TRACK_POSITION.value):
            return False
        if self._delivery_mode.value & SubscriptionMode.FAST_FORWARD.value:
            return False
        return (error_body['error'] == 'out_of_sync')

    def _retire_position_if_necessary(self, error_body):
        if error_body['error'] == 'out_of_sync':
            self.update_position(None)
        return True

    def _change_mode_from_cycle_to_linked(self):
        if self._mode == 'cycle':
            self._mode = 'linked'
            if self._next_args:
                self._args = self._next_args

            if self.observer:
                self._perform_state_callback('on_deleted')

            if self._next_observer:
                self.observer = self._next_observer
                self._perform_state_callback('on_created')
                self._next_observer = None
            else:
                self.observer = None
            self._sm.advance(lambda sm: sm.ModeChange())
        elif self._mode == 'unlinked':
            self._perform_state_callback('on_deleted')
            self.observer = None

    def _is_connected(self):
        return self._connected

    def _is_ready_to_subscribe(self):
        return self._is_mode_not_unlinked() and self._is_connected()

    def connect(self):
        logger.debug('connect')
        with self._lock:
            self._connected = True
            self._sm.advance(lambda sm: sm.Connect())

    def disconnect(self):
        logger.debug('disconnect')
        with self._lock:
            self._connected = False
            self._sm.advance(lambda sm: sm.Disconnect())

    def on_subscription_data(self, data):
        logger.debug('Got channel data %s', data)
        accepting_states =\
            ['Subscription.' + s for s in
                ['Subscribed', 'Unsubscribing']]
        if self._sm.get_state_name() in accepting_states:
            self.update_position(data['position'])
            if self.observer:
                self.observer.on_subscription_data(data)

    def update_position(self, new_position):
        if not (self._delivery_mode.value &
                SubscriptionMode.TRACK_POSITION.value):
            return

        if self._args:
            self._args['position'] = new_position
        else:
            self._args = {'position': new_position}

    def on_subscription_error(self, error):
        self._sm.advance(lambda sm: sm.ChannelError(error))

    def _send_subscribe_request(self):
        logger.debug('_send_subscribe_request(%s)', self._args)
        args = {}
        if self._delivery_mode.value & SubscriptionMode.FAST_FORWARD.value:
            args['fast_forward'] = True
        if self._args:
            args.update(self._args)
        self._send_subscribe_request_(args)

    def _send_unsubscribe_request(self):
        logger.debug('_send_unsubscribe_request')
        self._send_unsubscribe_request_()

    def on_subscribe_ok(self, ack):
        with self._lock:
            logger.debug('on_subscribe_ok')
            if ack.get('body').get('position'):
                self.update_position(ack['body']['position'])
            self._sm.advance(lambda sm: sm.SubscribeOK())

    def on_subscribe_error(self):
        with self._lock:
            logger.debug('on_subscribe_error')
            self._sm.advance(lambda sm: sm.SubscribeError())

    def on_unsubscribe_ok(self):
        with self._lock:
            logger.debug('on_unsubscribe_ok')
            self._sm.advance(lambda sm: sm.UnsubscribeOK())

    def on_unsubscribe_error(self):
        with self._lock:
            logger.debug('on_unsubscribe_error')
            self._sm.advance(lambda sm: sm.UnsubscribeError())

    def on_enter_failed(self, reason):
        self._perform_state_callback('on_enter_failed', reason)

    def __getattr__(self, name):
        if name.startswith('on_leave_') or name.startswith('on_enter'):
            return lambda: self._perform_state_callback(name)
        raise AttributeError(
            'Subscription has no attribute {0}'.format(name))

    def _perform_state_callback(self, callback_name, *args):
        if self.observer:
            current_thread_name = threading.current_thread().name
            logger.debug(
                'entering subscription callback %s on %s',
                callback_name, current_thread_name)
            callback = None
            try:
                callback = getattr(self.observer, callback_name)
            except AttributeError:
                pass
            try:
                if callback:
                    callback(*args)
            except Exception as e:
                logger.error('Caught exception in subscription callback')
                logger.exception(e)
            finally:
                logger.debug(
                    'exiting subscription callback %s on %s',
                    callback_name,
                    current_thread_name)