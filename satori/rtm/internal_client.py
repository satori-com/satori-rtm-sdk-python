
from __future__ import print_function
from collections import deque
import six
import threading
import time

import satori.rtm.internal_queue as queue
from satori.rtm.connection import Connection
import satori.rtm.internal_client_action as a
import satori.rtm.auth as auth
from satori.rtm.generated.statemap import StateUndefinedException
from satori.rtm.generated.client_sm import Client_sm
from satori.rtm.logger import logger
from satori.rtm.internal_subscription import Subscription

max_offline_queue_length = 1000


class InternalClient(object):
    def __init__(
            self, message_queue,
            endpoint, appkey,
            fail_count_threshold=float('inf'),
            reconnect_interval=1, max_reconnect_interval=300,
            observer=None, restore_auth_on_reconnect=True,
            proxy=None):

        self._endpoint = endpoint
        self._appkey = appkey
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_interval = max_reconnect_interval
        self.observer = observer
        self.fail_count_threshold = fail_count_threshold
        self.subscriptions = {}
        self.proxy = proxy

        self._reconnect_timer = None
        self._queue = message_queue
        self._sm = Client_sm(self)
        self._fail_count = 0
        self.restore_auth_on_reconnect = restore_auth_on_reconnect
        self.connection = None
        self._time_of_last_reconnect = None
        self.last_connecting_error = None
        self._connection_attempts_left = self.fail_count_threshold
        self._successful_auth_delegates = []
        self._offline_queue = deque([], max_offline_queue_length)

    def process_one_message(self, timeout=1):
        '''Must be called from a single thread
           returns True if the message was Dispose()'''

        try:
            m = self._queue.get(block=True, timeout=timeout)
        except queue.Empty:
            logger.debug('queue is empty')
            return False

        t = type(m)
        logger.info('Begin handling %s', t.__name__)

        if t == a.ChannelData:
            data = m.data
            channel = data['subscription_id']
            subscription = self.subscriptions.get(channel)
            if subscription:
                subscription.on_subscription_data(data)
            else:
                logger.error('Subscription for %s not found', data)
        elif t == a.Start:
            self._sm.Start()
        elif t == a.Stop:
            self._sm.Stop()
        elif t == a.Dispose:
            self._sm.Dispose()
            self._queue.task_done()
            return True

        elif t == a.Publish:
            if self.is_connected():
                try:
                    self.connection.publish(m.channel, m.message, m.callback)
                except Exception as e:
                    logger.exception(e)
            else:
                self._offline_queue.append(m)
        elif t == a.Subscribe:
            self._subscribe(
                m.channel_or_subscription_id,
                m.mode,
                m.observer,
                args=m.args)
        elif t == a.Unsubscribe:
            self._unsubscribe(m.channel_or_subscription_id)
        elif t == a.Read:
            self.connection.read(m.key, m.args, m.callback)
        elif t == a.Write:
            self.connection.write(m.key, m.value, m.callback)
        elif t == a.Delete:
            self.connection.delete(m.key, m.callback)
        elif t == a.Search:
            self.connection.search(m.prefix, m.callback)
        elif t == a.Authenticate:
            if self.is_connected():
                self._authenticate(m.auth_delegate, m.callback)
            else:
                self._offline_queue.append(m)
        elif t == a.Tick:
            self._sm.Tick()

        elif t == a.ConnectingComplete:
            self._sm.ConnectingComplete()
        elif t == a.ConnectingFailed:
            self._sm.ConnectingFailed()
        elif t == a.ConnectionClosed:
            self._sm.ConnectionClosed()
        elif t == a.ChannelError:
            self._sm.ChannelError(m.channel, m.payload)
        elif t == a.InternalError:
            self._sm.InternalError(m.payload)
        elif t == a.FastForward:
            self._perform_state_callback('on_fast_forward', m.channel)
        else:
            logger.error('Unexpected event %s: %s', m, t)

        self._queue.task_done()
        logger.info('Finish handling %s', t.__name__)
        return False

    # called back by connection from some thread
    def on_fast_forward(self, channel, payload):
        logger.info('on_fast_forward')
        self._queue.put(a.FastForward(channel, payload))

    # called back by connection from some thread
    def on_connection_closed(self):
        logger.info('on_connection_closed')
        self._queue.put(a.ConnectionClosed())

    # called back by connection from some thread
    def on_internal_error(self, message):
        logger.error('Internal error: %s', message)
        self._queue.put(a.InternalError(message))

    # called back by connection from some thread
    def on_subscription_data(self, data):
        self._queue.put(a.ChannelData(data))

    # called back by connection from some thread
    def on_subscription_error(self, channel, payload):
        self._queue.put(a.ChannelError(channel, payload))

    def _on_internal_error(self, payload):
        logger.error('RTM internal error: %s', payload)
        self._perform_state_callback('on_internal_error', payload)

    def _on_subscription_error(self, channel, payload):
        logger.error('Error on channel %s: %s', channel, payload)
        subscription = self.subscriptions.get(channel)
        if subscription:
            subscription.on_subscription_error(payload)
            if subscription.deleted():
                del self.subscriptions[channel]

    def _drain_offline_queue(self):
        logger.info('_drain_offline_queue')
        while self._offline_queue:
            action = self._offline_queue.popleft()
            self._queue.put(action)

    def __getattr__(self, name):
        if name.startswith('on_leave_') or name.startswith('on_enter'):
            return lambda: self._perform_state_callback(name)
        raise AttributeError(
            '{0} has no attribute {1}'.format(type(self).__name__, name))

    def _perform_state_callback(self, callback_name, *args):
        try:
            logger.info(
                'entering callback %s',
                callback_name)
            try:
                callback = getattr(self.observer, callback_name)
                callback(*args)
            except AttributeError:
                pass
        except Exception as e:
            logger.error('Caught exception in state callback')
            logger.exception(e)
        finally:
            logger.info(
                'exiting callback %s',
                callback_name)

    def _connect(self):
        logger.info('_connect')
        self._time_of_last_reconnect = time.time()
        self.connection = Connection(
            self._endpoint, self._appkey, self, self.proxy)
        try:
            self.connection.start()
            self._queue.put(a.ConnectingComplete())
        except Exception as e:
            logger.exception(e)
            self.last_connecting_error = e
            self._queue.put(a.ConnectingFailed())

    def _restore_auth_and_return_true_if_failed(self):
        logger.info('_restore_auth_and_return_true_if_failed')

        if not self.restore_auth_on_reconnect:
            return False

        counter = [len(self._successful_auth_delegates)]
        logger.debug('Restoring %d authentications', counter[0])

        if counter[0] == 0:
            return False

        ready_event = threading.Event()

        def callback(outcome):
            logger.debug('Outcome: %s', outcome)
            if type(outcome) == auth.Done:
                logger.debug('Restored auth')
                counter[0] -= 1
                if counter[0] == 0:
                    ready_event.set()
            else:
                ready_event.set()

        for ad in self._successful_auth_delegates:
            ready_event.clear()
            try:
                self.connection.authenticate(ad, callback)
            except Exception as e:
                logger.exception(e)
            ready_event.wait(10)

        if counter[0] == 0:
            logger.debug('Restoring authentications: done')
            return False
        else:
            logger.error('Failed to restore %d authentications', counter[0])
            return True

    def _connect_subscriptions(self):
        logger.info('connect_subscriptions')
        for _, s in six.iteritems(self.subscriptions):
            s.connect()

    def _reset_fail_count(self):
        logger.info('_reset_fail_count')
        self._fail_count = 0
        self._connection_attempts_left = self.fail_count_threshold

    def _increment_fail_count(self):
        logger.info(
            '_increment_fail_count: %s fails left',
            self._connection_attempts_left)
        self._fail_count += 1
        self._connection_attempts_left -= 1

    def _set_fail_count_to_critical(self):
        logger.info('_set_fail_count_to_critical')
        self._fail_count = self.fail_count_threshold
        self._connection_attempts_left = 0

    def _fail_count_is_small(self):
        result = self._connection_attempts_left > 0
        logger.info('_fail_count_is_small = %s', result)
        return result

    def _start_disconnecting(self):
        logger.info('_start_disconnecting')
        if self.connection:
            try:
                self.connection.stop()
            except Exception as e:
                logger.exception(e)

    def _forget_connection(self):
        logger.info('_forget_connection')
        if self.connection:
            self.connection.delegate = None
            try:
                self.connection.stop()
            except Exception:
                pass
            self.connection = None
        self._disconnect_subscriptions()

    def _disconnect_subscriptions(self):
        logger.info('_disconnect_subscriptions')
        existing = list(self.subscriptions.items())
        for _, subscription in existing:
            subscription.disconnect()

    def _subscribe(
            self, channel, mode, subscription_observer=None,
            args=None):
        logger.info('_subscribe')

        old_subscription = self.subscriptions.get(channel)
        if old_subscription:
            logger.debug('Old subscription found')
            # TODO: distinguish errors and legitimate resubscriptions
            #       and call an error callback on former
            old_subscription.subscribe(args, observer=subscription_observer)
            return

        def subscribe_callback(ack):
            logger.info('SAck: %s', ack)
            if ack.get('action') == 'rtm/subscribe/ok':
                subscription.on_subscribe_ok(ack)
            elif ack.get('action') == 'rtm/subscribe/error':
                logger.error('Subscription error: %s', ack)
                subscription.on_subscribe_error()
            else:
                self.on_internal_error(
                    'Unexpected subscribe ack: {0}'.format(ack))

        def send_subscribe_request(args_):
            try:
                self.connection.subscribe(
                    channel,
                    args_,
                    callback=subscribe_callback)
            except Exception as e:
                logger.exception(e)

        def unsubscribe_callback(ack):
            logger.info('USAck for channel %s: %s', channel, ack)
            if ack.get('action') == 'rtm/unsubscribe/ok':
                s = self.subscriptions.get(channel)
                if s:
                    del self.subscriptions[channel]
                subscription.on_unsubscribe_ok()
                if s and not subscription.deleted():
                    self.subscriptions[channel] = s

            elif ack.get('action') == 'rtm/unsubscribe/error':
                subscription.on_unsubscribe_error()
            else:
                self.on_internal_error(
                    'Unexpected unsubscribe ack: {0}'.format(ack))

        def send_unsubscribe_request():
            try:
                self.connection.unsubscribe(channel, unsubscribe_callback)
            except Exception as e:
                logger.exception(e)

        subscription = Subscription(
            mode,
            send_subscribe_request,
            send_unsubscribe_request,
            args)
        subscription.observer = subscription_observer
        if self.is_connected():
            subscription.connect()
        self.subscriptions[channel] = subscription

    def _authenticate(self, auth_delegate, callback):

        def callback_(outcome):
            if type(outcome) == auth.Done:
                if auth_delegate not in self._successful_auth_delegates:
                    self._successful_auth_delegates.append(auth_delegate)
            callback(outcome)
        try:
            self.connection.authenticate(auth_delegate, callback=callback_)
        except Exception as e:
            logger.exception(e)

    def _unsubscribe(self, channel):
        logger.info('unsubscribe from %s', channel)
        old_subscription = self.subscriptions.get(channel)
        if old_subscription:
            logger.info('found old subscription')
            old_subscription.unsubscribe()
        else:
            logger.error(
                "Trying to unsubscribe from unknown channel %s", channel)

    def is_connected(self):
        try:
            return self._sm.getState().getName() == "S.Connected"
        except StateUndefinedException:
            return False

    def _schedule_reconnect(self):
        now = time.time()
        target = self._time_of_last_reconnect +\
            min(
                self.reconnect_interval * (2 ** self._fail_count),
                self.max_reconnect_interval)
        delay = max(target - now, 0)
        logger.error('Reconnecting in %f seconds', delay)

        def reconnect():
            logger.warning('Time to reconnect')
            self._reconnect_timer = None
            self._queue.put(a.Tick())

        self._reconnect_timer = threading.Timer(delay, reconnect)
        self._reconnect_timer.start()

    def _cancel_reconnect(self):
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None