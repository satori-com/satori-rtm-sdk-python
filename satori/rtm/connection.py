
'''

satori.rtm.connection
=====================

Provides a low-level API for managing a connection to RTM.

'''

from __future__ import print_function

import itertools
import posixpath
import satori.rtm.internal_json as json
import cbor2
import re
import sys
import threading
import time

import satori.rtm.internal_logger
from satori.rtm.internal_connection_miniws4py import RtmWsClient
import satori.rtm.auth as auth
import satori.rtm.exceptions as exs

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

    def __init__(
            self, endpoint, appkey,
            delegate=None, https_proxy=None, protocol='json'):
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
    * https_proxy (string, int) [optional] - (host, port) tuple for https proxy
    * protocol {string} [optional] - one of 'cbor' or 'json' (default)
        """

        validate_endpoint(endpoint, appkey, protocol)

        self.logger = satori.rtm.internal_logger.logger

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
        self.https_proxy = https_proxy
        self._auth_lock = threading.RLock()
        self._next_auth_action = None
        self.ws = None
        self._last_ping_time = None
        self._last_ponged_time = None
        self._time_to_stop_pinging = False
        self._auth_callback = None
        self._ping_thread = None
        self._ws_thread = None
        self.protocol = protocol
        if self.protocol == 'cbor':
            self._dumps = cbor2.dumps
        else:
            self._dumps = json.dumps

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
        ps = ['cbor'] if self.protocol == 'cbor' else []
        self.ws = RtmWsClient(self.url, proxy=self.https_proxy, protocols=ps)
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
            except Exception as e:
                # we could be trying to write a goodbye
                # into already closed socket
                # or just sending a close frame can fail for
                # any number of reasons
                self.logger.exception(e)
        else:
            self.logger.info('Trying to close a connection that is not open')

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
        self.action_with_preserialized_body(name, self._dumps(body), callback)

    def action_with_preserialized_body(self, name, body, callback=None):
        if callback:
            if len(self.ack_callbacks_by_id) >= high_ack_count_watermark:
                self.logger.debug('Throttling %s request', name)
                time.sleep(0.001)

            action_id = next(self.action_id_iterator)
            if self.protocol == 'cbor':
                payload =\
                    b''.join([
                        b'\xa3',
                        cbor2.dumps(u'action'),
                        cbor2.dumps(name),
                        cbor2.dumps(u'id'),
                        cbor2.dumps(action_id),
                        cbor2.dumps(u'body'),
                        body])
            else:
                payload =\
                    u''.join([
                        u'{"action":"',
                        name,
                        u'","id":',
                        str(action_id),
                        u',"body":',
                        body,
                        u'}']).encode('utf8')
            self.ack_callbacks_by_id[action_id] = callback
        else:
            if self.protocol == 'cbor':
                payload =\
                    b''.join([
                        b'\xa2',
                        cbor2.dumps(u'action'),
                        cbor2.dumps(name),
                        cbor2.dumps(u'body'),
                        body])
            else:
                payload =\
                    u''.join([
                        u'{"action":"',
                        name,
                        u'","body":',
                        body,
                        u'}']).encode('utf8')
        self.send(payload)

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
        """

        self.action(
            u'rtm/publish',
            {u'channel': channel, u'message': message},
            callback)

    def publish_preserialized_message(self, channel, message, callback=None):
        if self.protocol == 'json':
            body = u'{{"channel":"{0}","message": {1}}}'.format(
                channel, message)
        elif self.protocol == 'cbor':
            body =\
                b''.join([
                    b'\xa2',
                    cbor2.dumps(u'channel'),
                    cbor2.dumps(channel),
                    cbor2.dumps(u'message'),
                    message])
        self.action_with_preserialized_body(u'rtm/publish', body, callback)

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
        """
        body = args or {}
        body[u'channel'] = channel
        self.action(u'rtm/read', body, callback)

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
      ...

        """
        mailbox = []
        time_to_return = threading.Event()

        def callback(ack):
            mailbox.append(ack)
            time_to_return.set()
        body = args or {}
        body[u'channel'] = channel
        self.action(u'rtm/read', body, callback)
        if not time_to_return.wait(timeout):
            raise RuntimeError('Timeout in read_sync')
        ack = mailbox[0]
        if ack[u'action'] == u'rtm/read/ok':
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
        """
        self.action(
            u'rtm/write',
            {u'channel': channel, u'message': value},
            callback)

    def write_preserialized_value(self, channel, value, callback=None):
        if self.protocol == 'json':
            body = u'{{"channel":"{0}","message": {1}}}'.format(channel, value)
        elif self.protocol == 'cbor':
            body =\
                b''.join([
                    b'\xa2',
                    cbor2.dumps(u'channel'),
                    cbor2.dumps(channel),
                    cbor2.dumps(u'message'),
                    value])
        self.action_with_preserialized_body(u'rtm/write', body, callback)

    def delete(self, key, callback=None):
        """
Description
    Asynchronously deletes any value from the specified channel.

Parameters
    * channel {string} [required] - Name of the channel.
    * callback {function} [optional] -  Callback to execute on the response
      PDU from RTM. The response PDU is passed as a parameter to this function.
      RTM does not send a response PDU if a callback is not specified.
        """
        self.action(u'rtm/delete', {u'channel': key}, callback)

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
        """

        error = []
        position = []
        time_to_return = threading.Event()

        def callback(ack):
            if ack[u'action'] != u'rtm/publish/ok':
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
        """

        if args is not None and args.get('filter'):
            body = {u'subscription_id': channel_or_subscription_id}
        else:
            body = {u'channel': channel_or_subscription_id}
        if args:
            body.update(args)
        self.action(u'rtm/subscribe', body, callback)

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
        """

        error = []
        time_to_return = threading.Event()

        def callback(ack):
            if ack[u'action'] != u'rtm/subscribe/ok':
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
        """

        self.action(u'rtm/unsubscribe', {u'subscription_id': channel}, callback)

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
        """

        error = []
        time_to_return = threading.Event()

        def callback(ack):
            if ack[u'action'] != u'rtm/unsubscribe/ok':
                error.append(ack)
            time_to_return.set()
        self.unsubscribe(channel, callback)
        if not time_to_return.wait(timeout):
            raise RuntimeError('Timeout in unsubscribe_sync')
        if error:
            raise RuntimeError(error[0])

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
                payload = self._dumps({
                    u'action': u'auth/handshake',
                    u'body': {
                        u'method': self._next_auth_action.method,
                        u'data': self._next_auth_action.data},
                    u'id': action_id
                    })
                return self.send(payload)
            elif type(self._next_auth_action) == auth.Authenticate:
                action_id = next(self.action_id_iterator)
                payload = self._dumps({
                    u'action': u'auth/authenticate',
                    u'body': {
                        u'method': self._next_auth_action.method,
                        u'credentials': self._next_auth_action.credentials},
                    u'id': action_id
                    })
                return self.send(payload)

            self._auth_callback(auth.Error(
                u'auth_delegate returned {0} instead of an auth action'.format(
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
                time.sleep(min(ping_interval_in_seconds, 1))
                now = time.time()
                if self._last_ping_time and\
                        now - self._last_ping_time < ping_interval_in_seconds:
                    continue
                if self.ws is None:
                    break
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
        except Exception as e:
            self.logger.exception(e)
        self.logger.debug('Finishing ping thread')

    def on_ws_closed(self):
        self._time_to_stop_pinging = True
        if self.delegate:
            self.delegate.on_connection_closed()
        if self.ws:
            self.ack_callbacks_by_id.clear()
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

    def on_incoming_json(self, incoming_json):
        self.on_ws_ponged()

        action = incoming_json.get('action')
        if not action:
            message = u'"{0}" has no "action" field'.format(incoming_json)
            return self.on_internal_error(message)

        body = incoming_json.get('body')

        maybe_bodyless_actions = [u'rtm/delete/ok', u'rtm/publish/ok']
        if body is None and action not in maybe_bodyless_actions:
            message = u'"{0}" has no "body" field'.format(incoming_json)
            self.logger.error(message)
            return self.on_internal_error(message)

        if action == u'rtm/subscription/data':
            return self.on_subscription_data(body)
        elif action == u'rtm/subscription/error':
            return self.on_subscription_error(body)
        elif action == u'rtm/subscription/info'\
                and body.get(u'info') == u'fast_forward':
            return self.on_fast_forward(body)

        id_ = incoming_json.get(u'id')

        if id_ is None:
            message = u'"{0}" has no "id" field'.format(incoming_json)
            if action == u'/error':
                return self.on_internal_error(
                    'General error: {0}'.format(incoming_json))

            return self.on_internal_error(message)

        if action.startswith('auth/'):
            def convert(pdu):
                if pdu[u'action'] == u'auth/handshake/ok':
                    return auth.HandshakeOK(pdu['body']['data'])
                if pdu[u'action'] == u'auth/authenticate/ok':
                    return auth.AuthenticateOK()
                return auth.Error(pdu['body']['reason'])

            return self.on_auth_reply(convert(incoming_json))

        callback = self.ack_callbacks_by_id.get(id_)
        if callback:

            try:
                delegate_on_solicited =\
                    getattr(self.delegate, 'on_solicited_pdu')
            except AttributeError:
                delegate_on_solicited = None

            if delegate_on_solicited:
                delegate_on_solicited(callback, incoming_json)
            else:
                callback(incoming_json)

            if not incoming_json.get('action').endswith('/data'):
                del self.ack_callbacks_by_id[id_]

    def on_incoming_binary_frame(self, incoming_binary):
        try:
            self.logger.debug(incoming_binary)
            incoming_json = cbor2.loads(incoming_binary)
        except ValueError as e:
            self.logger.exception(e)
            message = '"{0}" is not valid CBOR'.format(incoming_binary)
            return self.on_internal_error(message)
        self.on_incoming_json(incoming_json)

    def on_incoming_text_frame(self, incoming_text):
        self.logger.debug('incoming text: %s', incoming_text)

        self.on_ws_ponged()

        try:
            incoming_json = json.loads(incoming_text)
        except ValueError as e:
            self.logger.exception(e)
            message = '"{0}" is not valid JSON'.format(incoming_text)
            return self.on_internal_error(message)

        self.on_incoming_json(incoming_json)


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


def validate_endpoint(endpoint, appkey, protocol):
    if not endpoint:
        raise exs.MalformedCredentials("Missing endpoint")

    if not appkey:
        raise exs.MalformedCredentials("Missing appkey")

    if not endpoint.startswith('ws://') and not endpoint.startswith('wss://'):
        raise exs.MalformedCredentials(
            'Endpoint must start with "ws(s)://" but "%s" does not' % endpoint)

    if protocol not in ('cbor', 'json'):
        raise exs.MalformedCredentials(
            'Protocol must be one of "cbor", "json", not %s' % protocol)