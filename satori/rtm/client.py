
'''

satori.rtm.client
=================

The `satori.rtm.client` module is the main entry point to manage the WebSocket
connection from the Python SDK to RTM. Use the Client class to create a client
instance from which you can publish messages and subscribe to channels.

This class routes messages to respective subscription observers
and automatically reconnects and restores the authentication and subscription
state if the connection to RTM drops.

'''


from __future__ import print_function
from contextlib import contextmanager
import satori.rtm.auth as auth
from satori.rtm.exceptions import AuthError
import satori.rtm.internal_queue as queue
import threading

import satori.rtm.internal_client_action as a
from satori.rtm.internal_client import InternalClient
import satori.rtm.internal_subscription as s

from satori.rtm.logger import logger


SubscriptionMode = s.SubscriptionMode
Full = queue.Full


class Client(object):
    """
    This is the documentation for Client class
    """

    def __init__(
            self, endpoint, appkey,
            fail_count_threshold=float('inf'),
            reconnect_interval=1, max_reconnect_interval=300,
            observer=None, restore_auth_on_reconnect=True,
            max_queue_size=20000, https_proxy=None):
        r"""

Description
    Constructor for the Client.

Parameters
    * endpoint {string} [required] - RTM endpoint as a string. Example:
      "wss://rtm:8443/foo/bar". If port number is omitted, it defaults to 80 for
      ws:// and 443 for wss://. Available from the Dev Portal.
    * appkey {string} [required] - Appkey used to access RTM.
      Available from the Dev Portal.
    * reconnect_interval {int} [optional] - Time period, in seconds, between
      reconnection attempts. The timeout period between each successive
      connection attempt increases, but starts with this value. Use
      max_reconnect_interval to specify the maximum number of seconds between
      reconnection attempts. Default is 1.
    * max_reconnect_interval {int} [optional] - Maximum period of time, in
      seconds, to wait between reconnection attempts. Default is 300.
    * fail_count_threshold {int} [optional] - Number of times the SDK should
      attempt to reconnect if the connection disconnects. Specify any value
      that resolves to an integer. Default is inf (infinity).
    * observer {client_observer} [optional] - Instance of a client observer
      class, used to define functionality based on the state changes of a
      Client.

      Set this property with client.observer or in the `make_client(*args,
      **kwargs)` or `Client(*args, **kwargs)` methods.
    * restore_auth_on_reconnect {boolean} optional - Whether to restore
      authentication after reconnects. Default is True.
    * max_queue_size {int} optional - this parameter limits the amount of
      concurrent requests in order to avoid 'out of memory' situation.
      For example is max_queue_size is 10 and the client code sends 11
      publish requests so fast that by the time it sends 11th one the reply
      for the first one has not yet arrived, this 11th call to `client.publish`
      will throw the `satori.rtm.client.Full` exception.
    * https_proxy (string, int) [optional] - (host, port) tuple for https proxy

Syntax

    ::
        from satori.rtm.client import Client

        client = Client(endpoint='<ENDPOINT>', appkey=<APP_KEY>)
        ...

        """

        assert endpoint
        assert endpoint.startswith('ws://') or endpoint.startswith('wss://'),\
            'Endpoint must start with "ws(s)://" but "%s" does not' % endpoint

        self._queue = queue.Queue(maxsize=max_queue_size)

        self._internal = InternalClient(
            self._queue,
            endpoint, appkey,
            fail_count_threshold,
            reconnect_interval, max_reconnect_interval,
            observer, restore_auth_on_reconnect, https_proxy)

        self._disposed = False
        self._thread = threading.Thread(
            target=self._internal_event_loop,
            name='ClientLoop')
        self._thread.daemon = True
        self._thread.start()

    def last_connecting_error(self):
        """
Description
    If there were unsuccessful connection attempts, this function returns
    the exception for the last such attempt. Otherwise returns None.
        """
        return self._internal.last_connecting_error

    def _enqueue(self, msg, timeout=0.1):
        if not self._disposed:
            self._queue.put(msg, block=True, timeout=timeout)
        else:
            raise RuntimeError(
                'Trying to use a disposed satori.rtm.client.Client')

    def start(self):
        """
Description
    Starts a WebSocket connection to RTM for the Client object. You
    must call the start() method before you subscribe to a channel using the
    Client object methods.

    If you publish any messages before calling this method, the SDK queues the
    messages to publish after establishing the WebSocket connection.

Syntax
    ::

        with sc.make_client(
            endpoint=endpoint, appkey=appkey) as client:

            client.stop()
            ...
            client.start()
            ...

        """
        self._enqueue(a.Start())

    def stop(self):
        """
Description
    Closes a WebSocket connection to RTM for the Client object.

    Use this method if you want to explicitly stop all interaction with RTM.
    After you use this method, if you call publish or subscribe methods
    while the client is stopped, the SDK queues the requests and sends them when
    the client reconnects.

Syntax
    ::

        with make_client(
            endpoint=endpoint, appkey=appkey) as client:

            ...
            client.stop()
            ...

        """
        self._enqueue(a.Stop())

    def authenticate(self, auth_delegate, callback):
        """
Description
    Validates the identity of an application user after connecting to RTM
    with the Client class. After the user authenticates with RTM, the operations
    that the client can perform depends on the role.

    Since the authentication process is an asynchronous operation, the callback
    function is required. The callback function processes the PDU response from
    RTM.

    For more information about authentication, see
    *Authentication and Authorization* in the online docs.

Parameters
    * auth_delegate {AuthDelegate | RoleSecretAuthDelegate} [required] - An
      authentication delegate object. Use a
      satori.rtm.auth.RoleSecretAuthDelegate class for the role-based
      authentication process.
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

        client.authenticate(auth_delegate, auth_callback)

        auth_event.wait()

        """
        self._enqueue(a.Authenticate(auth_delegate, callback))

    def publish(self, channel, message, callback=None):
        """
Description
    Publishes a message to the specified channel.

    The channel and message parameters are required. The `message` parameter can
    be any JSON-supported value. For more information, see www.json.org.

    By default, this method does not acknowledge the completion of the publish
    operation. Optionally, you can specify a callback function to process the
    response from RTM. If you specify a callback, RTM
    returns an object that represents the Protocol Data Unit (PDU) response to
    the publish request. For more information about PDUs, see *RTM API* in the
    online docs.

Reference.
    Since this is an asynchronous method, you can also use the Python threading
    module to create an event to track completion of the publish operation in
    the callback function.

Parameters
    * message {string} [required] - JSON value to publish as message. It must be
      serializable using `json.dumps` from the Python standard `JSON` module.
    * channel {string} [required] - Name of the channel to which you want to
      publish.
    * callback {function} [optional] - Callback function to execute on the PDU
      response returned by RTM to the publish request.

Syntax
    ::

        with sc.make_client(
            endpoint=endpoint, appkey=appkey) as client:

            ...
            print('Publishing a message')
            client.publish(channel=channel, message=message)

        """
        self._enqueue(a.Publish(channel, message, callback))

    def read(self, channel, args=None, callback=None):
        """
Description
    Asynchronously reads a value from the specified channel. This function
    has no return value, but you can inspect
    the reply PDU in the callback function.

    You can also use the `args` parameter to add additional JSON key-value pairs
    to the PDU in the read request that the SDK sends
    to RTM. For more information about PDUs, see *RTM API* in the online docs.

Parameters
    * channel {string} [required] - Name of the channel to read from.
    * args {object} [optional] - Any JSON key-value pairs to send in the
      read request. To create a filter, use the desired fSQL query as a string
      value for `filter` key.
    * callback {function} [optional] - Callback function to execute on the PDU
      response returned to the subscribe request by RTM.

Syntax
    ::

        with make_client(endpoint=endpoint, appkey=appkey) as client:

            mailbox = []
            event = threading.Event()

            def read_callback(reply):
                mailbox.append(reply)
                event.set()

            client.read(channel, callback=read_callback)
            if not event.wait(5):
                print('Read request timed out')
            else:
                print('Read request returned {0}'.format(mailbox[0]))
        """
        self._enqueue(a.Read(channel, args, callback))

    def write(self, channel, value, callback=None):
        """
Description
    Asynchronously writes the given value to the specified channel.

Parameters
    * channel {string} [required] - Channel name.
    * value {json value} [required] - JSON that represents the message payload
      to publish.
    * callback {function} [optional] - Callback passed the response PDU from
      RTM.

Syntax
    ::

        with make_client(endpoint=endpoint, appkey=appkey) as client:

            mailbox = []
            event = threading.Event()

            def write_callback(reply):
                mailbox.append(reply)
                event.set()

            client.write("answer", 42, callback=write_callback)
            if not event.wait(5):
                print('Write request timed out')
            else:
                print('Write request returned {0}'.format(mailbox[0]))
        """
        self._enqueue(a.Write(channel, value, callback))

    def delete(self, channel, callback=None):
        """
Description
    Asynchronously deletes any value from the specified channel.

Parameters
    * channel {string} [required] - Channel name.
    * callback {function} [optional] - Callback passed the response PDU from
      RTM.

Syntax
    ::

        with make_client(endpoint=endpoint, appkey=appkey) as client:

            mailbox = []
            event = threading.Event()

            def delete_callback(reply):
                mailbox.append(reply)
                event.set()

            client.delete("old_stuff", callback=delete_callback)
            if not event.wait(5):
                print('Delete request timed out')
            else:
                print('Delete request returned {0}'.format(mailbox[0]))
        """
        self._enqueue(a.Delete(channel, callback))

    def subscribe(
            self, channel_or_subscription_id, mode,
            subscription_observer, args=None):
        """
Description
    Subscribes to the specified channel.

    Optionally, you can also use an observer that implements the subscription
    callback functions and pass the observer as the `subscription_observer`
    parameter. The callback functions represent each possible state for the
    channel subscription. See *Subscription Observer*.

    You can also use the `args` parameter to add additional JSON key-value pairs
    to the PDU in the subscribe request that the SDK sends
    to RTM. For more information about PDUs, see *RTM API* in the online docs.

    .. note:: To receive data published to a channel after you subscribe to it,
              use the `on_subscription_data()` callback function in a
              subscription observer.

Parameters
    * channel_or_subscription_id {string} [required] - String that identifies
      the channel. If you do not use the `filter` parameter, it is the channel
      name. Otherwise, it is a unique identifier for the channel (subscription
      id).
    * subscription_mode {SubscriptionMode} [required] - this mode determines the
      behaviour of the Python SDK and RTM when resubscribing after a
      reconnection. Use SubscriptionMode.ADVANCED, SubscriptionMode.RELIABLE, or
      SubscriptionMode.SIMPLE.
    * subscription_observer {object} [optional] - Instance of an observer class
      that implements the subscription observer callback functions.
    * args {object} [optional] - Any JSON key-value pairs to send in the
      subscribe request. To include a filter, put the desired fSQL query
      as a string value for the `filter` key. See *Subscribe PDU* in the
      online docs.

Syntax
    ::

        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            class SubscriptionObserver(object):
                def on_subscription_data(self, data):
                    for message in data['messages']:
                        print('Client got message {0}'.format(message))

            subscription_observer = SubscriptionObserver()
            client.subscribe(
                channel,
                SubscriptionMode.RELIABLE,
                subscription_observer)

        """
        self._enqueue(
            a.Subscribe(
                channel_or_subscription_id, mode,
                subscription_observer, args))

    def unsubscribe(self, channel_or_subscription_id):
        """
Description
    Unsubscribes from a channel.

    After you unsubscribe, the application no longer receives messages for the
    channel. To identify when the unsubscribe operation has completed, use the
    `on_leave_subscribed()` callback function of a subscription observer class.

Parameters
    * channel {string} [required] - Name of the channel from which you want to
      unsubscribe.

Syntax
    ::

        with make_client(
                endpoint=endpoint, appkey=appkey) as client:

            ...
            client.subscribe(
                "My Channel",
                SubscriptionMode.RELIABLE,
                subscription_observer)
            ...
            client.unsubscribe("My Channel")

        """
        self._enqueue(a.Unsubscribe(channel_or_subscription_id))

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
        self._enqueue(a.Search(prefix, callback))

    def dispose(self):
        """
Description
    Client finishes all work, release all resources and becomes unusable.
    Upon completion, `client.observer.on_enter_disposed()` is called.
        """
        if not self._disposed:
            self._enqueue(a.Dispose(), timeout=None)
            self._disposed = True
            if self._thread != threading.current_thread():
                self._thread.join()

    @property
    def observer(self):
        return self._internal.observer

    @observer.setter
    def observer(self, o):
        self._internal.observer = o

    def is_connected(self):
        """
Description
    Returns `True` if the Client object is connected via a
    WebSocket connection to RTM and `False` otherwise.

Returns
    Boolean

Syntax
    ::

        with sc.make_client(
            endpoint=platform_endpoint,
            appkey=platform_appkey) as client:

            ...
            if client.is_connected()
                # do something
            else:
                # do something else

        """
        return self._internal.is_connected()

    def _internal_event_loop(self):
        while True:
            if self._internal.process_one_message(timeout=None):
                break


class ClientStateObserver(object):
    def on_enter_stopped(self):
        logger.info('on_enter_stopped')

    def on_leave_stopped(self):
        logger.info('on_leave_stopped')

    def on_enter_connecting(self):
        logger.info('on_enter_connecting')

    def on_leave_connecting(self):
        logger.info('on_leave_connecting')

    def on_enter_awaiting(self):
        logger.info('on_enter_awaiting')

    def on_leave_awaiting(self):
        logger.info('on_leave_awaiting')

    def on_enter_connected(self):
        logger.info('on_enter_connected')

    def on_leave_connected(self):
        logger.info('on_leave_connected')

    def on_enter_disposed(self):
        logger.info('on_enter_disposed')

    def on_enter_stopping(self):
        logger.info('on_enter_stopping')

    def on_leave_stopping(self):
        logger.info('on_leave_stopping')


@contextmanager
def make_client(*args, **kwargs):
    r"""
make_client(\*args, \*\*kwargs)
-------------------------------

Description
    The `make_client()` function is a context manager. Call `make_client()`
    using a `with` statement and the SDK automatically starts the WebSocket
    connection. The SDK stops and then closes the WebSocket connection when the
    statement completes or terminates due to an error.

    This function takes the same parameters as the Client constructor plus
    optional `auth_delegate`.

    To use this function, import it from the client module::

        `from satori.rtm.client import make_client`

Parameters
    * endpoint {string} [required] - RTM endpoint as a string. Example:
      "wss://rtm:8443/foo/bar". If port number is omitted, it defaults to 80 for
      ws:// and 443 for wss://. Available from the Dev Portal.
    * appkey {string} [required] - Appkey used to access RTM.
      Available from the Dev Portal.
    * reconnect_interval {int} [optional] - Time period, in seconds, between
      reconnection attempts. The timeout period between each successive
      connection attempt increases, but starts with this value. Use
      max_reconnect_interval to specify the maximum number of seconds between
      reconnection attempts. Default is 1.
    * max_reconnect_interval {int} [optional] - Maximum period of time, in
      seconds, to wait between reconnection attempts. Default is 300.
    * fail_count_threshold {int} [optional] - Number of times the SDK should
      attempt to reconnect if the connection disconnects. Specify any value
      that resolves to an integer. Default is inf (infinity).
    * observer {client_observer} [optional] - Instance of a client observer
      class, used to define functionality based on the state changes of a
      Client.

      Set this property with client.observer or in the `make_client(*args,
      **kwargs)` or `Client(*args, **kwargs)` methods.
    * restore_auth_on_reconnect {boolean} optional - Whether to restore
      authentication after reconnects. Default is True.
    * max_queue_size {int} optional - this parameter limits the amount of
      concurrent requests in order to avoid 'out of memory' situation.
      For example is max_queue_size is 10 and the client code sends 11
      publish requests so fast that by the time it sends 11th one the reply
      for the first one has not yet arrived, this 11th call to `client.publish`
      will throw the `satori.rtm.client.Full` exception.
    * auth_delegate {AuthDelegate} [optional] - if auth_delegate parameter is
      present, the client yielded by make_client will be already authenticated.

Syntax
    ::

        import satori.rtm.client as sc

        endpoint = 'ENDPOINT'
        appkey = 'APPKEY'

        with sc.make_client(endpoint=endpoint, appkey=appkey) as client:

Client Observer
---------------

Use the client observer callback functions in an observer to implement
functionality based on the Client object state changes.

Set this observer with the `client.observer` property on the Client.

The following table lists the Client object states and the associated
callback functions:

============ ====================== =====================
Client State Enter Callback         Exit Callback
============ ====================== =====================
Awaiting     on_enter_awaiting()    on_leave_awaiting()
Connecting   on_enter_connecting()  on_leave_connecting()
Connected    on_enter_connected()   on_leave_connected()
Stopped      on_enter_stopped()     on_leave_stopped()
Disposed     on_enter_disposed()    n/a
============ ====================== =====================

The following figure shows an example client observer with implemented callback
function::

    class ClientObserver(object):
        def __init__(self):
            self.connection_attempt_count = 0

        def on_enter_connecting(self):
            self.connection_attempt_count += 1
            print('Establishing connection #{0}'.format(
                self.connection_attempt_count))

    client = Client(endpoint='<ENDPOINT>', appkey=None)
    client.observer = ClientObserver()
    client.start()
    client.stop()
    client.start()

Subscription Observer
---------------------

Use callback functions in a subscription observer to implement functionality
based on the state changes for a channel subscription. The subscribe(channel,
SubscriptionMode.RELIABLE, subscription_observer, args) method takes
a subscription observer for the subscription_observer parameter.

.. note:: Depending on your application, these callbacks are optional, except
          `on_subscription_data`. To process received messages, you must
          implement `on_subscription_data(data)` callback.

The following table lists a subscription observer subscription states and
callback functions:

============= ======================== ========================
State         Enter Callback           Exit Callback
============= ======================== ========================
Subscribing   on_enter_subscribing()   on_leave_subscribing()
Subscribed    on_enter_subscribed()    on_leave_subscribed()
Unsubscribing on_enter_unsubscribing() on_leave_unsubscribing()
Unsubscribed  on_enter_unsubscribed()  on_leave_unsubscribed()
Failed        on_enter_failed()        on_leave_failed()
Deleted       on_deleted()             n/a
============= ======================== ========================

Other Callbacks

=================== ======================
Event               Callback
=================== ======================
Created             on_created()
Message(s) Received on_subscription_data()
=================== ======================

The following figure shows an example subscription observer with an implemented
callback function::

    class SubscriptionObserver(object):
        def __init__(self, channel):
                self.message_count = 0
                self.channel = channel

        def on_subscription_data(self, data):
                for message in data['messages']:
                        print('Got message {0}'.format(message))
                self.message_count += len(data['messages'])

        def on_enter_subscribed(self):
                print('Subscription is now active')

        def on_deleted(self):
                print('Received {0} messages from channel ""{1}""'.format(
                        self.message_count, self.channel))

    subscription_observer = SubscriptionObserver()
    client.subscribe(
        channel,
        SubscriptionMode.RELIABLE,
        subscription_observer(channel))

    # wait for some time

    client.unsubscribe(channel)

    """

    observer = kwargs.get('observer')
    auth_delegate = kwargs.get('auth_delegate')
    if 'auth_delegate' in kwargs:
        del kwargs['auth_delegate']

    client = Client(*args, **kwargs)
    ready_event = threading.Event()

    class Observer(ClientStateObserver):
        def on_enter_connected(self):
            ClientStateObserver.on_enter_connected(self)
            ready_event.set()

        def on_enter_stopped(self):
            ClientStateObserver.on_enter_stopped(self)
            ready_event.set()

    client.observer = Observer()
    client.start()
    if not ready_event.wait(70):
        if client.last_connecting_error():
            client.dispose()
            raise RuntimeError(
                "Client connection timeout, last connection error: {0}".format(
                    client.last_connecting_error()))
        else:
            raise RuntimeError("Client connection timeout")
    ready_event.clear()
    if not client.is_connected():
        client.dispose()
        raise RuntimeError(
            "Client connection error: {0}".format(
                client.last_connecting_error()))

    auth_mailbox = []

    def auth_callback(auth_result):
        auth_mailbox.append(auth_result)
        ready_event.set()

    if auth_delegate:
        client.authenticate(auth_delegate, callback=auth_callback)

        if not ready_event.wait(20):
            client.dispose()
            raise AuthError('Authentication process has timed out')

        auth_result = auth_mailbox[0]

        if type(auth_result) == auth.Error:
            raise AuthError(auth_result.message)

        logger.debug('Auth success in make_client')

    try:
        client.observer = observer
        yield client
    finally:
        logger.info('make_client.finally')
        client.dispose()
