# -*- coding: utf-8 -*-
import logging
import socket
import types

try:
    from OpenSSL.SSL import Error as pyOpenSSLError
except ImportError:
    class pyOpenSSLError(Exception):
        pass

from miniws4py.streaming import Stream
from miniws4py.messaging import Message, PingControlMessage
from miniws4py.compat import basestring

DEFAULT_READING_SIZE = 2

logger = logging.getLogger('miniws4py')

__all__ = ['WebSocket']

class WebSocket(object):
    """ Represents a websocket endpoint and provides a high level interface to drive the endpoint. """

    def __init__(self, sock, protocols=None, extensions=None, proxy=None):
        """ The ``sock`` is an opened connection
        resulting from the websocket handshake.

        If ``protocols`` is provided, it is a list of protocols
        negotiated during the handshake as is ``extensions``.
        """

        self.stream = Stream()
        """
        Underlying websocket stream that performs the websocket
        parsing to high level objects.
        """

        self.protocols = protocols
        """
        List of protocols supported by this endpoint.
        Unused for now.
        """

        self.extensions = extensions
        """
        List of extensions supported by this endpoint.
        Unused for now.
        """

        self.sock = sock
        """
        Underlying connection.
        """

        self._is_secure = hasattr(sock, '_ssl') or hasattr(sock, '_sslobj')
        """
        Tell us if the socket is secure or not.
        """

        self.client_terminated = False
        """
        Indicates if the client has been marked as terminated.
        """

        self.server_terminated = False
        """
        Indicates if the server has been marked as terminated.
        """

        self.reading_buffer_size = DEFAULT_READING_SIZE
        """
        Current connection reading buffer size.
        """

    def opened(self):
        """
        Called by the server when the upgrade handshake
        has succeeeded.
        """

    def close(self, code=1000, reason=''):
        """
        Initiate the closing handshake with the server.
        """
        if not self.client_terminated:
            self.client_terminated = True
            self._write(self.stream.close(code=code, reason=reason).single())

    def closed(self, code, reason=None):
        """
        Called  when the websocket stream and connection are finally closed.
        The provided ``code`` is status set by the other point and
        ``reason`` is a human readable message.

        .. seealso:: Defined Status Codes http://tools.ietf.org/html/rfc6455#section-7.4.1
        """

    @property
    def terminated(self):
        """
        Returns ``True`` if both the client and server have been
        marked as terminated.
        """
        return self.client_terminated is True and self.server_terminated is True

    @property
    def connection(self):
        return self.sock

    def close_connection(self):
        """
        Shutdowns then closes the underlying connection.
        """
        if self.sock:

            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception as e:
                logger.info(e)

            try:
                self.sock.close()
            except Exception as e:
                logger.info(e)
            finally:
                self.sock = None

    def ping(self, message):
        """
        Send a ping message to the remote peer.
        The given `message` must be a unicode string.
        """
        self.send(PingControlMessage(message))

    def ponged(self, pong):
        """
        Pong message, as a :class:`messaging.PongControlMessage` instance,
        received on the stream.
        """

    def received_message(self, message):
        """
        Called whenever a complete ``message``, binary or text,
        is received and ready for application's processing.

        The passed message is an instance of :class:`messaging.TextMessage`
        or :class:`messaging.BinaryMessage`.

        .. note:: You should override this method in your subclass.
        """

    def unhandled_error(self, error):
        """
        Called whenever a socket, or an OS, error is trapped
        by miniws4py but not managed by it. The given error is
        an instance of `socket.error` or `OSError`.

        Note however that application exceptions will not go
        through this handler. Instead, do make sure you
        protect your code appropriately in `received_message`
        or `send`.

        The default behaviour of this handler is to log
        the error with a message.
        """
        logger.exception("Failed to receive data")

    def _write(self, b):
        """
        Trying to prevent a write operation
        on an already closed websocket stream.

        This cannot be bullet proof but hopefully
        will catch almost all use cases.
        """
        if self.terminated or self.sock is None:
            raise RuntimeError("Cannot send on a terminated websocket")

        self.sock.sendall(b, 0)

    def send(self, payload, binary=False, masked=False):
        """
        Sends the given ``payload`` out.

        If ``payload`` is some bytes or a bytearray,
        then it is sent as a single message not fragmented.

        If ``payload`` is a generator, each chunk is sent as part of
        fragmented message.

        If ``binary`` is set, handles the payload as a binary message.
        """
        message_sender = self.stream.binary_message if binary else self.stream.text_message

        if isinstance(payload, basestring) or isinstance(payload, bytearray):
            m = message_sender(payload).single(masked=masked)
            self._write(m)

        elif isinstance(payload, Message):
            data = payload.single(masked=masked)
            self._write(data)

        elif type(payload) == types.GeneratorType:
            bytes = next(payload)
            first = True
            for chunk in payload:
                self._write(message_sender(bytes).fragment(first=first))
                bytes = chunk
                first = False

            self._write(message_sender(bytes).fragment(last=True))

        else:
            raise ValueError("Unsupported type '%s' passed to send()" % type(payload))

    def _get_from_pending(self):
        """
        The SSL socket object provides the same interface
        as the socket interface but behaves differently.

        When data is sent over a SSL connection
        more data may be read than was requested from by
        the miniws4py websocket object.

        In that case, the data may have been indeed read
        from the underlying real socket, but not read by the
        application which will expect another trigger from the
        manager's polling mechanism as if more data was still on the
        wire. This will happen only when new data is
        sent by the other peer which means there will be
        some delay before the initial read data is handled
        by the application.

        Due to this, we have to rely on a non-public method
        to query the internal SSL socket buffer if it has indeed
        more data pending in its buffer.

        Now, some people in the Python community
        `discourage <https://bugs.python.org/issue21430>`_
        this usage of the ``pending()`` method because it's not
        the right way of dealing with such use case. They advise
        `this approach <https://docs.python.org/dev/library/ssl.html#notes-on-non-blocking-sockets>`_
        instead. Unfortunately, this applies only if the
        application can directly control the poller which is not
        the case with the WebSocket abstraction here.

        We therefore rely on this `technic <http://stackoverflow.com/questions/3187565/select-and-ssl-in-python>`_
        which seems to be valid anyway.

        This is a bit of a shame because we have to process
        more data than what wanted initially.
        """
        data = b""
        pending = self.sock.pending()
        while pending:
            data += self.sock.recv(pending, 0)
            pending = self.sock.pending()
        return data

    def once(self):
        """
        Performs the operation of reading from the underlying
        connection in order to feed the stream of bytes.

        We start with a small size of two bytes to be read
        from the connection so that we can quickly parse an
        incoming frame header. Then the stream indicates
        whatever size must be read from the connection since
        it knows the frame payload length.

        It returns `False` if an error occurred at the
        socket level or during the bytes processing. Otherwise,
        it returns `True`.
        """
        if self.terminated:
            logger.debug("WebSocket is already terminated")
            return False

        try:
            b = self.sock.recv(self.reading_buffer_size, 0)
            # This will only make sense with secure sockets.
            if self._is_secure:
                b += self._get_from_pending()
        except (socket.error, OSError, pyOpenSSLError) as e:
            self.unhandled_error(e)
            return False
        else:
            if not self.process(b):
                return False

        return True

    def terminate(self):
        """
        Completes the websocket by calling the `closed`
        method either using the received closing code
        and reason, or when none was received, using
        the special `1006` code.

        Finally close the underlying connection for
        good and cleanup resources by unsetting
        the `stream` attribute.
        """
        s = self.stream       

        try:
            if s.closing is None:
                self.closed(1006, "Going away")
            else:
                self.closed(s.closing.code, s.closing.reason)
        finally:
            self.client_terminated = self.server_terminated = True
            self.close_connection()

            # Cleaning up resources
            s._cleanup()
            self.stream = None

    def process(self, bytes):
        """ Takes some bytes and process them through the
        internal stream's parser. If a message of any kind is
        found, performs one of these actions:

        * A closing message will initiate the closing handshake
        * Errors will initiate a closing handshake
        * A message will be passed to the ``received_message`` method
        * Pings will see pongs be sent automatically
        * Pongs will be passed to the ``ponged`` method

        The process should be terminated when this method
        returns ``False``.
        """
        s = self.stream

        if not bytes and self.reading_buffer_size > 0:
            return False

        self.reading_buffer_size = s.parser.send(bytes) or DEFAULT_READING_SIZE

        if s.closing is not None:
            logger.debug("Closing message received (%d) '%s'" % (s.closing.code, s.closing.reason))
            if not self.server_terminated:
                self.close(s.closing.code, s.closing.reason)
            else:
                self.client_terminated = True
            return False

        if s.errors:
            for error in s.errors:
                logger.debug("Error message received (%d) '%s'" % (error.code, error.reason))
                self.close(error.code, error.reason)
            s.errors = []
            return False

        if s.has_message:
            self.received_message(s.message)
            if s.message is not None:
                s.message.data = None
                s.message = None
            return True

        if s.pings:
            for ping in s.pings:
                self._write(s.pong(ping.data))
            s.pings = []

        if s.pongs:
            for pong in s.pongs:
                self.ponged(pong)
            s.pongs = []

        return True

    def run(self):
        """
        Performs the operation of reading from the underlying
        connection in order to feed the stream of bytes.

        We start with a small size of two bytes to be read
        from the connection so that we can quickly parse an
        incoming frame header. Then the stream indicates
        whatever size must be read from the connection since
        it knows the frame payload length.

        Note that we perform some automatic opererations:

        * On a closing message, we respond with a closing
          message and finally close the connection
        * We respond to pings with pong messages.
        * Whenever an error is raised by the stream parsing,
          we initiate the closing of the connection with the
          appropiate error code.

        This method is blocking and should likely be run
        in a thread.
        """
        self.sock.setblocking(True)
        try:
            self.opened()
            while not self.terminated:
                if not self.once():
                    break
        finally:
            self.terminate()
