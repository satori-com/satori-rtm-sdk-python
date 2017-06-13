
'''

satori.rtm.connection
=====================

Provides a low-level API for managing a connection to RTM.

'''

from __future__ import print_function

import itertools
import posixpath
try:
    import rapidjson as json
except ImportError:
    import json
import re
import sys
import threading
import time

import satori.rtm.logger
from satori.rtm.internal_connection_miniws4py import RtmWsClient
import satori.rtm.auth as auth

ping_interval_in_seconds = 60
high_ack_count_watermark = 20000

# FIXME: *_sync functions are very similar


class Connection(object):
    """
You can use the Connection object as long as it stays connected to the RTM.
If a disconnect occurs, you must create a new Connection object,
resubscribe to all channels, and perform authentication again, if necessary.

.. note:: The `satori.rtm.client` module includes a default implementation to
          handle disconnects automatically and reconnect and resubscribes as
          necessary.
    """

    def __init__(self, endpoint, appkey, delegate=None, proxy=None):
        """
Description
    Constructor for the Connection class. Creates and returns an instance of the
    Connection class. Use this function to create a instance from which you can
    subscribe and publish, authenticate an application user, and manage the
    WebSocket connection to RTM. The Connection class allows you to
    publish and subscribe synchronously and asynchronously.

    The `endpoint` and `appkey` parameters are required. Optionally, you can
    choose to create a delegate to process received messages and handle
    connection and channel errors. To set the delegate property, specify it in
    the constructor or use `connection.delegate = MyCustomDelegate()`.

Returns
    Connection

Parameters
    * endpoint {string} [required] - RTM endpoint as a string.
    * appkey {string} [required] - Appkey used to access RTM. Available from the
      Dev Portal.
    * delegate {object} [optional] - Delegate object to handle received
      messages, channel errors, internal errors, and closed connections.
    * proxy (string, int) [optional] - (host, port) tuple for https proxy

Syntax

::

    ...
    connection = Connection(endpoint, appkey, delegate=None)
    after_receive = threading.Event()

    class ConnectionDelegate(object):
        def on_connection_closed(self):
            print('connection closed')

        def on_internal_error(error):
            print('internal error', error)

        def on_subscription_data(data):
            print('data:', data)
            after_receive.set()

    connection.delegate = ConnectionDelegate()
    connection.start()

        """

        assert endpoint
        assert appkey
        assert endpoint.startswith('ws://') or endpoint.startswith('wss://'),\
            'Endpoint must start with "ws(s)://" but "%s" does not' % endpoint

        self.logger = satori.rtm.logger.logger

        re_version = re.compile(r'/v(\d+)$')
        version_match = re_version.search(endpoint)
        if version_match:
            warning = (
                'Specifying a version as a part of the endpoint is deprecated.'
                ' Please remove the {0} from {1}.'.format(
                    version_match.group(), endpoint))
            print(warning, file=sys.stderr)
            endpoint = re_version.sub('', endpoint)

        self.url = posixpath.join(endpoint, 'v2')
        self.url += '?appkey={0}'.format(appkey)
        self.delegate = delegate
        self.ack_callbacks_by_id = {}
        self.action_id_iterator = itertools.count()
        self.proxy = proxy
        self._auth_lock = threading.RLock()
        self._next_auth_action = None
        self.ws = None
        self._last_ping_time = None
        self._last_ponged_time = None
        self._time_to_stop_pinging = False
        self._auth_callback = None
        self._ping_thread = None
        self._ws_thread = None

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    def start(self):
        """
Description
    Starts a WebSocket connection to RTM for the Connection object.
    You must call the `start()` method before publish or subscribe requests
    using the Connection object methods will completed successfully.
        """

        if self.ws:
            raise RuntimeError('Connection is already open')

        self.logger.debug('connection.start %s', self.url)
        self.ws = RtmWsClient(self.url, proxy=self.proxy)
        self.ws.delegate = self

        try:
            self.ws.connect()
        except Exception:
            self.ws.delegate = None
            self.ws = None
            raise

        self._ws_thread = threading.Thread(target=self.ws.run)
        self._ws_thread.name = 'WebSocketReader'
        self._ws_thread.daemon = True
        self._ws_thread.start()

    def stop(self):
        """
Description
    Closes a WebSocket connection to RTM for the Connection object.

    Use this method if you want to explicitly stop all interaction with RTM.
    After you use this method, you can no longer publish or subscribe
    to any channels for the Connection object. You must use `start()` to restart
    the WebSocket connection and then publish or subscribe.
        """

        self._time_to_stop_pinging = True

        if self.ws:
            try:
                self.ws.close()
                self.logger.debug('Waiting for WS thread')
                self._ws_thread.join()
                self.logger.debug('WS thread finished normally')
            except OSError as e:
                # we could be trying to write a goodbye
                # into already closed socket
                self.logger.exception(e)
        else:
            raise RuntimeError('Connection is not open yet')

    def send(self, payload):
        """
Description
    Synchronously sends the specified message to RTM.
    This is a lower-level method suitable for manually performing
    PDU serialization.

        """
        if not self.ws:
            raise RuntimeError(
                'Attempting to send data, but connection is not open yet')
        self.logger.debug('Sending payload %s', payload)

        try:
            self.ws.send(payload)
        except Exception as e:
            self.logger.exception(e)
            self.on_ws_closed()
            raise

    def action(self, name, body, callback=None):
        """
Description
    Synchronously sends a PDU created with the specified `action` and `body` to
    RTM. This is a lower-level method that can be used, for example, to take
    advantage of changes to PDU specifications by Satori without requiring an
    updated SDK.
        """
        payload = {'action': name, 'body': body}
        if callback:

            # throttle if waiting for many acks already
            if len(self.ack_callbacks_by_id) >= high_ack_count_watermark:
                self.logger.debug('Throttling %s request', name)
                time.sleep(0.001)

            action_id = next(self.action_id_iterator)
            payload['id'] = action_id
            self.ack_callbacks_by_id[action_id] = callback
        self.send(json.dumps(payload))

    def publish(self, channel, message, callback=None):
        """
Description
    Publishes a message to the specified channel.

    The channel and message parameters are required. The `message` parameter can
    be any JSON-supported value. For more information, see www.json.org.

    By default, this method does not acknowledge the completion of the publish
    operation. Optionally, you can specify a callback function to process the
    response from RTM. If you specify a callback, RTM
    returns an object that represents the PDU response to
    the publish request. For more information about PDUs, see *RTM API* in the
    online docs.

    Because this is an asynchronous method, you can also use the Python
    `threading` module to create an event to track completion of the publish
    operation in the callback function.

Parameters
    * message {string} [required] - JSON value to publish as a message. It must
      be serializable using `json.dumps` from the Python standard `JSON` module.
    * channel {string} [required] - Name of the channel to which you want to
      publish.
    * callback {function} [optional] - Callback function to execute on the PDU
      returned by RTM as a response to the publish request.

Syntax

::

    connection.start()
    connection.publish("My Channel", "Message text to publish")

        """

        self.action(
            'rtm/publish',
            {'channel': channel, 'message': message},
            callback)

    def read(self, channel, args=None, callback=None):
        """
Description
    Asynchronously reads a value from the specified channel. This function
    has no return value, but you can inspect
    the response PDU in the callback function.

    You can also use the `args` parameter to add additional JSON key-value pairs
    to the PDU in the read request that the SDK sends
    to RTM. For more information about PDUs, see *RTM API* in the online docs.

    By default, this method does not acknowledge the completion of the subscribe
    operation. Optionally, you can specify a callback function to process the
    response from RTM. If you specify a callback, RTM
    returns an object that represents the response to
    the publish request as a PDU.

Parameters
    * channel {string} [required] - Name of the channel to read from.
    * callback {function} [optional] - Callback function to execute on the
      response returned to the subscribe request as a PDU.
    * args {object} [optional] - Any JSON key-value pairs to send in the
      subscribe request. See *Subscribe PDU* in the online docs.

Syntax

::

    connection.start()

    position = connection.publish_sync(channel, message)
    connection.subscribe(channel, {'position': position})

        """
        body = args or {}
        body['channel'] = channel
        self.action('rtm/read', body, callback)

    def read_sync(self, channel, args=None, timeout=60):
        """
Description
    Synchronously reads a message from the specified channel.

    This method generates a `RuntimeError` if the read operation does not
    complete within the timeout period.

Returns
    JSON value

Parameters
    * channel {string} [required] - Name of the channel to read from.
    * timeout {int} [optional] - Amount of time, in seconds, to allow RTM
      to complete the read operation before it generates an error.
      Default is 60.

Syntax

::

    connection.start()

    message = 'hello'
    connection.publish_sync(channel, message)
    value = connection.read_sync(channel)
    # value should be "hello"
    ...

        """
        mailbox = []
        time_to_return = threading.Event()

        def callback(ack):
            mailbox.append(ack)
            time_to_return.set()
        body = args or {}
        body['channel'] = channel
        self.action('rtm/read', body, callback)
        if not time_to_return.wait(timeout):
            raise RuntimeError('Timeout in read_sync')
        ack = mailbox[0]
        if ack['action'] == 'rtm/read/ok':
            return ack['body']['message']
        raise RuntimeError(ack)

    def write(self, channel, value, callback=None):
        """
Description
    Asynchronously writes a value into the specified channel.

    The `channel` and `value` parameters are required. The `value` parameter can
    be any JSON-supported value. For more information, see www.json.org.

    By default, this method does not acknowledge the completion of the publish
    operation. Optionally, you can specify a callback function to process the
    response from RTM. If you specify a callback, RTM returns an object that
    represents the response to the publish request as a PDU. For more
    information about PDUs, see the RTM API Reference.

    Because this is an asynchronous method, you can also use the Python
    `threading` module to create an event to track completion of the write
    operation in the callback function.

Parameters
    * message {string} [required] - JSON value to publish as message. It must be
      serializable using `json.dumps` from the Python standard `JSON` module.
    * channel {string} [required] - Name of the channel.
    * callback {function} [optional] - Callback function to execute on the
      response to the publish request, returned by RTM as a PDU.

Syntax

::

    connection.start()
    connection.write("my_dog", {"latitude": 52.52, "longitude":13.405})

        """
        self.action(
            'rtm/write',
            {'channel': channel, 'message': value},
            callback)

    def delete(self, key, callback=None):
        """
Description
    Asynchronously deletes any value from the specified channel.

Parameters
    * channel {string} [required] - Name of the channel.
    * callback {function} [optional] -  Callback to execute on the response
      PDU from RTM. The response PDU is passed as a parameter to this function.
      RTM does not send a response PDU if a callback is not specified.

Syntax
    ::

        connection.start()

        mailbox = []
        event = threading.Event()

        def delete_callback(reply):
            mailbox.append(reply)
            event.set()

        connection.delete("old_stuff", callback=delete_callback)
        if not event.wait(5):
            print('Delete request timed out')
        else:
            print('Delete request returned {0}'.format(mailbox[0]))
        """
        self.action('rtm/delete', {'channel': key}, callback)

    def publish_sync(self, channel, message, timeout=60):
        """
Description
    Synchronously publishes a message to the specified channel and returns the
    `position` property for the message stream position to which the message was
    published. For more information about the position value, see *RTM API*
    in the online docs.

    This method generates a `RuntimeError` if the publish operation does not
    complete within the timeout period.

    The message parameter can be any JSON-supported value. For more information,
    see www.json.org.

    .. note:: To send a publish request asynchronously for a Connection object,
              use publish(channel, message, callback).

Returns
    position

Parameters
    * message {string} [required] - JSON value to publish as message. It must be
      serializable using `json.dumps` from the Python standard `JSON` module.
    * channel {string} [required] - Name of the channel.
    * timeout {int} [optional] - Amount of time, in seconds, to allow RTM
      to complete the publish operation before it generates an error.
      Default is 60.

Syntax

::

    connection.start()

    position = connection.publish_sync(channel, message)
    connection.subscribe_sync(channel, {'position': position})
    ...

        """

        error = []
        position = []
        time_to_return = threading.Event()

        def callback(ack):
            if ack['action'] != 'rtm/publish/ok':
                error.append(ack)
            else:
                position.append(ack['body']['position'])
            time_to_return.set()
        self.publish(channel, message, callback)
        if not time_to_return.wait(timeout):
            raise RuntimeError('Timeout in publish_sync')
        if error:
            raise RuntimeError(error[0])
        return position[0]

    def subscribe(
            self, channel_or_subscription_id,
            args=None, callback=None):
        """
Description
    Subscribes to the specified channel.

    You can use the `args` parameter to add additional JSON values to the
    Protocol Data Unit (PDU) in the subscribe request that the SDK sends to RTM.
    For more information about PDUs, see *RTM API* in the online docs.

    By default, this method does not acknowledge the completion of the subscribe
    operation. Optionally, you can specify a callback function to process the
    response from RTM. If you specify a callback, RTM
    returns an object that represents the PDU response to
    the publish request.

    .. note:: To receive data published to a channel after you subscribe to it,
              use the `on_subscription_data()` callback function in a
              subscription observer class.

Parameters
    * channel {string} [required] - Name of the channel.
    * callback {function} [optional] - Callback function to execute on the
      response to the subscribe request, returned by RTM as a PDU.
    * args {object} [optional] - Any JSON key-value pairs to send in the
      subscribe request. See *Subscribe PDU* in the online docs.

Syntax

::

    connection.start()

    position = connection.publish_sync(channel, message)
    connection.subscribe(channel, {'position': position})

        """

        if args is not None and args.get('filter'):
            body = {'subscription_id': channel_or_subscription_id}
        else:
            body = {'channel': channel_or_subscription_id}
        if args:
            body.update(args)
        self.action('rtm/subscribe', body, callback)

    def subscribe_sync(self, channel, args=None, timeout=60):
        """
Description
    Subscribes to the specified channel and generates a `RuntimeError` if the
    request does not complete within the timeout period.

    You can use the `args` parameter to add additional JSON values to the PDU
    in the subscribe request that the SDK sends to RTM.
    For more information about PDUs, see *RTM API* in the online docs.

Parameters
    * channel {string} [required] - Name of the channel.
    * args {object} [optional] - Any additional JSON values to send in the
      subscribe request.
    * timeout {int} [optional] - Amount of time, in seconds, to allow RTM
      to complete the subscribe operation before it generates an error.
      Default is 60.

Syntax

::

    ...
    connection.start()

    position = connection.publish_sync(channel, message)
    connection.subscribe_sync(channel, {'position': position})
    ...

        """

        error = []
        time_to_return = threading.Event()

        def callback(ack):
            if ack['action'] != 'rtm/subscribe/ok':
                error.append(ack)
            time_to_return.set()
        self.subscribe(channel, args, callback=callback)
        if not time_to_return.wait(timeout):
            raise RuntimeError('Timeout in subscribe_sync')
        if error:
            raise RuntimeError(error[0])

    def unsubscribe(self, channel, callback=None):
        """
Description
    Unsubscribes from the specified channel.

    After you unsubscribe, the application no longer receives messages for the
    channel until after RTM completes the unsubscribe operation.

    By default, this method does not acknowledge the completion of the subscribe
    operation. Optionally, you can specify a callback function to process the
    response from RTM. If you specify a callback, RTM
    returns an object that represents the PDU response to
    the publish request. For more information about PDUs, see *RTM API*
    in the online docs.

Parameters
    * channel {string} [required] - Name of the channel.
    * callback {function} [optional] - Callback function to execute on the
      response to the unsubscribe request, returned by RTM as a PDU.

Syntax

::

    ...
    connection.start()

    position = connection.publish_sync(channel, message)
    connection.subscribe(channel, {'position': position})
    ...
    connection.unsubscribe(channel)
    ...

        """

        self.action('rtm/unsubscribe', {'subscription_id': channel}, callback)

    def unsubscribe_sync(self, channel, timeout=60):
        """
unsubscribe_sync(channel, timeout)
----------------------------------

Description
    Unsubscribes from all messages for a channel and generates a `RuntimeError`
    if the unsubscribe operation does not complete within the timeout period.

Parameters
    * channel {string} [required] - Name of the channel.
    * timeout {int} [optional] - Amount of time, in seconds, to allow RTM
      to complete the unsubscribe operation before it generates an
      error. Default is 60.

Syntax

::

    ...
    connection.start()

    position = connection.publish_sync(channel, message)
    connection.subscribe_sync(channel, {'position': position})
    ...
    unsubscribe_sync(channel)
    ...
        """

        error = []
        time_to_return = threading.Event()

        def callback(ack):
            if ack['action'] != 'rtm/unsubscribe/ok':
                error.append(ack)
            time_to_return.set()
        self.unsubscribe(channel, callback)
        if not time_to_return.wait(timeout):
            raise RuntimeError('Timeout in unsubscribe_sync')
        if error:
            raise RuntimeError(error[0])

    def search(self, prefix, callback):
        """
Description
    Asynchronously performs a channel search for a given user-defined prefix.
    This method passes RTM replies to the callback. RTM may send multiple
    responses to the same search request: zero or more search result PDUs with
    an action of `rtm/search/data` (depending on the results of the search).
    Each channel found is only sent once.

    After the search result PDUs, RTM follows with a positive response PDU:
    `rtm/search/ok`. Callback must inspect the reply object passed to the
    callback for the reply['body']['channels'] list. The callback is called on
    each response.
        """
        self.action('rtm/search', {'prefix': prefix}, callback)

    def authenticate(self, auth_delegate, callback):
        """
authenticate(auth_delegate, callback)
-------------------------------------

Description
    Validates the identity of a client after connecting to RTM
    with the Connection module. After the user authenticates with
    RTM, the operations that the client can perform depends on the role.

    Since the authentication process is an asynchronous operation, the callback
    function is required. The callback function processes the PDU response from
    RTM.

    For more information about authentication, see *Authentication and
    Authorization* in the online docs.

Parameters
    * auth_delegate {AuthDelegate | RoleSecretAuthDelegate} [required] - An
      authentication delegate object created with
      the `RoleSecretAuthDelegate(role, role_key)` method for
      the role-based authentication process.
    * callback {function} [required] - Function to execute after RTM
      returns a response.

Syntax

::

    secret_key = '<ROLE_SECRET_KEY>'

    auth_delegate = auth.RoleSecretAuthDelegate('<ROLE>', secret_key)
    auth_event = threading.Event()

    def auth_callback(auth_result):
        if type(auth_result) == auth.Done:
            auth_event.set()
        """

        with self._auth_lock:
            if self._next_auth_action:
                return callback(
                    auth.Error('Authentication is already in progress'))
            self._next_auth_action = auth_delegate.start()
            self._auth_callback = callback
            return self._handle_next_auth_action()

    def _handle_next_auth_action(self):
        with self._auth_lock:
            if type(self._next_auth_action) in [auth.Done, auth.Error]:
                self._auth_callback(self._next_auth_action)
                self._auth_callback = None
                self._next_auth_action = None
                return

            if type(self._next_auth_action) == auth.Handshake:
                action_id = next(self.action_id_iterator)
                payload = json.dumps({
                    'action': 'auth/handshake',
                    'body': {
                        'method': self._next_auth_action.method,
                        'data': self._next_auth_action.data},
                    'id': action_id
                    })
                return self.send(payload)
            elif type(self._next_auth_action) == auth.Authenticate:
                action_id = next(self.action_id_iterator)
                payload = json.dumps({
                    'action': 'auth/authenticate',
                    'body': {
                        'method': self._next_auth_action.method,
                        'credentials': self._next_auth_action.credentials},
                    'id': action_id
                    })
                return self.send(payload)

            self._auth_callback(auth.Error(
                'auth_delegate returned {0} instead of an auth action'.format(
                    self._next_auth_action)))
            self._auth_callback = None

    def on_ws_opened(self):
        self.logger.debug('on_ws_opened')
        self._ping_thread = threading.Thread(
            target=self._ping_until_the_end,
            name='Pinger')
        self._ping_thread.daemon = True
        self._ping_thread.start()

    def _ping_until_the_end(self):
        self.logger.debug('Starting ping thread')
        try:
            while not self._time_to_stop_pinging:
                time.sleep(ping_interval_in_seconds)
                self.logger.debug('send ping')
                self.ws.send_ping()
                if self._last_ping_time:
                    if not self._last_ponged_time or\
                            self._last_ping_time > self._last_ponged_time:
                        self.logger.error(
                            'Server has not responded to WS ping')
                        try:
                            ws = self.ws
                            self.on_ws_closed()
                            ws.delegate = None
                            ws.close()
                        except Exception as e:
                            self.logger.exception(e)
                self._last_ping_time = time.time()
                self.logger.debug('pinging')
        except Exception:
            pass
        self.logger.debug('Finishing ping thread')

    def on_ws_closed(self):
        self._time_to_stop_pinging = True
        if self.delegate:
            self.delegate.on_connection_closed()
        if self.ws:
            self.ws.delegate = None
            try:
                self.ws.close()
            except Exception as e:
                self.logger.exception(e)
            self.ws = None

    def on_ws_ponged(self):
        self._last_ponged_time = time.time()

    def on_auth_reply(self, reply):
        self.logger.debug('on_auth_reply: %s', reply)
        with self._auth_lock:
            if self._next_auth_action:
                continuation = getattr(self._next_auth_action, 'callback')
                if continuation:
                    self._next_auth_action = continuation(reply)
                    self._handle_next_auth_action()
                else:
                    self._auth_callback(reply)
            else:
                self.logger.error(
                    'Unexpected auth reply %s while not doing auth',
                    reply)

    def on_subscription_data(self, data):
        if self.delegate:
            self.delegate.on_subscription_data(data)

    def on_subscription_error(self, payload):
        channel = payload.get('subscription_id')
        if self.delegate:
            self.delegate.on_subscription_error(channel, payload)

    def on_fast_forward(self, payload):
        channel = payload.get('subscription_id')
        if self.delegate:
            self.delegate.on_fast_forward(channel, payload)

    def on_internal_error(self, message):
        if self.delegate:
            self.delegate.on_internal_error(message)

    def on_incoming_text_frame(self, incoming_text):
        self.logger.debug('incoming text: %s', incoming_text)

        self.on_ws_ponged()

        try:
            if isinstance(incoming_text, bytes):
                incoming_text = incoming_text.decode('utf-8')
            incoming_json = json.loads(incoming_text)
        except ValueError as e:
            self.logger.exception(e)
            message = '"{0}" is not valid JSON'.format(incoming_text)
            return self.on_internal_error(message)

        action = incoming_json.get('action')
        if not action:
            message = '"{0}" has no "action" field'.format(incoming_text)
            return self.on_internal_error(message)

        body = incoming_json.get('body')

        maybe_bodyless_actions = ['rtm/delete/ok', 'rtm/publish/ok']
        if body is None and action not in maybe_bodyless_actions:
            message = '"{0}" has no "body" field'.format(incoming_text)
            self.logger.error(message)
            return self.on_internal_error(message)

        if action == 'rtm/subscription/data':
            return self.on_subscription_data(body)
        elif action == 'rtm/subscription/error':
            return self.on_subscription_error(body)
        elif action == 'rtm/subscription/info'\
                and body.get('info') == 'fast_forward':
            return self.on_fast_forward(body)

        if action == '/error':
            return self.on_internal_error(
                'General error: {0}'.format(incoming_json))

        id_ = incoming_json.get('id')
        if id_ is None:
            message = '"{0}" has no "id" field'.format(incoming_text)
            return self.on_internal_error(message)

        if action.startswith('auth/'):
            def convert(pdu):
                if pdu['action'] == 'auth/handshake/ok':
                    return auth.HandshakeOK(pdu['body']['data'])
                if pdu['action'] == 'auth/authenticate/ok':
                    return auth.AuthenticateOK()
                return auth.Error(pdu['body']['reason'])

            return self.on_auth_reply(convert(incoming_json))

        callback = self.ack_callbacks_by_id.get(id_)
        if callback:
            callback(incoming_json)
            if not incoming_json.get('action').endswith('/data'):
                del self.ack_callbacks_by_id[id_]


def enable_wsaccel():
    """
    Use optimized Cython versions of CPU-intensive routines
    provided by the `wsaccel` package.
    """
    import wsaccel.utf8validator
    import wsaccel.xormask
    import miniws4py.streaming
    import miniws4py.framing
    miniws4py.streaming.Utf8Validator = wsaccel.utf8validator.Utf8Validator

    def fast_mask(data):
        masker = wsaccel.xormask.XorMaskerSimple(b'\xFF\xFF\xFF\xFF')
        return masker.process(data)

    miniws4py.framing.mask = fast_mask
