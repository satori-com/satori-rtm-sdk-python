# -*- coding: utf-8 -*-
from base64 import b64encode
import certifi
from hashlib import sha1
import logging
import os
import socket
import ssl
import sys

from miniws4py import WS_KEY, WS_VERSION
from miniws4py.exc import HandshakeError
from miniws4py.websocket import WebSocket
from miniws4py.compat import urlsplit

__all__ = ['WebSocketBaseClient']

logger = logging.getLogger('miniws4py')

class WebSocketBaseClient(WebSocket):
    def __init__(self, url, protocols=None, extensions=None,
                 ssl_options=None, headers=None):
        """
        A websocket client that implements :rfc:`6455` and provides a simple
        interface to communicate with a websocket server.

        This class works on its own but will block if not run in
        its own thread.

        When an instance of this class is created, a :py:mod:`socket`
        is created. If the connection is a TCP socket,
        the nagle's algorithm is disabled.

        The address of the server will be extracted from the given
        websocket url.

        The websocket key is randomly generated, reset the
        `key` attribute if you want to provide yours.

        For instance to create a TCP client:

        .. code-block:: python

           >>> from websocket.client import WebSocketBaseClient
           >>> ws = WebSocketBaseClient('ws://localhost/ws')


        Here is an example for a TCP client over SSL:

        .. code-block:: python

           >>> from websocket.client import WebSocketBaseClient
           >>> ws = WebSocketBaseClient('wss://localhost/ws')


        You may provide extra headers by passing a list of tuples
        which must be unicode objects.

        """
        self.url = url
        self.host = None
        self.scheme = None
        self.port = None
        self.resource = None
        self.ssl_options = ssl_options or {}
        self.extra_headers = headers or []

        self._parse_url()

        # Let's handle IPv4 and IPv6 addresses
        # Simplified from CherryPy's code
        try:
            family, socktype, proto, canonname, sa = socket.getaddrinfo(self.host, self.port,
                                                                        socket.AF_UNSPEC,
                                                                        socket.SOCK_STREAM,
                                                                        0, socket.AI_PASSIVE)[0]
        except socket.gaierror:
            family = socket.AF_INET
            if self.host.startswith('::'):
                family = socket.AF_INET6

            socktype = socket.SOCK_STREAM
            proto = 0

        sock = socket.socket(family, socktype, proto)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, 'AF_INET6') and family == socket.AF_INET6 and \
          self.host.startswith('::'):
            try:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except (AttributeError, socket.error):
                pass

        WebSocket.__init__(self, sock, protocols=protocols,
                           extensions=extensions)

        self.key = b64encode(os.urandom(16))

    def _parse_url(self):
        """
        Parses a URL which must have one of the following forms:

        - ws://host[:port][path]
        - wss://host[:port][path]

        The ``host`` and ``port``
        attributes will be set to the parsed values. If no port
        is explicitely provided, it will be either 80 or 443
        based on the scheme. Also, the ``resource`` attribute is
        set to the path segment of the URL (alongside any querystring).
        """
        # Python 2.6.1 and below don't parse ws or wss urls properly. netloc is empty.
        # See: https://github.com/Lawouach/WebSocket-for-Python/issues/59
        scheme, url = self.url.split(":", 1)

        parsed = urlsplit(url, scheme="http")
        if parsed.hostname:
            self.host = parsed.hostname
        else:
            raise ValueError("Invalid hostname from: %s", self.url)

        if parsed.port:
            self.port = parsed.port

        if scheme == "ws":
            if not self.port:
                self.port = 80
        elif scheme == "wss":
            if not self.port:
                self.port = 443
        else:
            raise ValueError("Invalid scheme: %s" % scheme)

        if parsed.path:
            resource = parsed.path
        else:
            resource = "/"

        if parsed.query:
            resource += "?" + parsed.query

        self.scheme = scheme
        self.resource = resource

    @property
    def bind_addr(self):
        return (self.host, self.port)

    def connect(self):
        """
        Connects this websocket and starts the upgrade handshake
        with the remote endpoint.
        """
        if self.scheme == "wss":

            if sys.version_info < (2, 7, 9):
                raise RuntimeError(
                    "Secure websockets are only supported with "
                    " Python 2.7.9+ and PyPy 2.6+ while this version is"
                    " {0}".format(sys.version))

            ctx = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH,
                cafile=certifi.where())

            self.sock = ctx.wrap_socket(self.sock, server_hostname=self.host)
        assert certifi

        try:
            self.sock.settimeout(300)
            self.sock.connect(self.bind_addr)

            self._write(self.handshake_request)

            response = b''
            doubleCLRF = b'\r\n\r\n'
            while True:
                bytes_ = self.sock.recv(128)
                if not bytes_:
                    break
                response += bytes_
                if doubleCLRF in response:
                    break

            if not response:
                self.close_connection()
                raise HandshakeError("No response")

            headers, _, body = response.partition(doubleCLRF)
            response_line, _, headers = headers.partition(b'\r\n')

            try:
                self.process_response_line(response_line)
                self.protocols, self.extensions =\
                    self.process_handshake_header(headers)
            except HandshakeError:
                self.close_connection()
                raise

            self.handshake_ok()
            if body:
                self.process(body)
        except Exception as e:
            logger.exception(e)
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
            raise e

    @property
    def handshake_headers(self):
        """
        List of headers appropriate for the upgrade
        handshake.
        """
        headers = [
            ('Host', '%s:%s' % (self.host, self.port)),
            ('Connection', 'Upgrade'),
            ('Upgrade', 'websocket'),
            ('Sec-WebSocket-Key', self.key.decode('utf-8')),
            ('Sec-WebSocket-Version', str(max(WS_VERSION)))
            ]
        
        if self.protocols:
            headers.append(('Sec-WebSocket-Protocol', ','.join(self.protocols)))

        if self.extra_headers:
            headers.extend(self.extra_headers)

        if not any(x for x in headers if x[0].lower() == 'origin'):

            scheme, url = self.url.split(":", 1)
            parsed = urlsplit(url, scheme="http")
            if parsed.hostname:
                self.host = parsed.hostname
            else:
                self.host = 'localhost'
            origin = scheme + '://' + parsed.hostname
            if parsed.port:
                origin = origin + ':' + str(parsed.port)
            headers.append(('Origin', origin))

        return headers

    @property
    def handshake_request(self):
        """
        Prepare the request to be sent for the upgrade handshake.
        """
        headers = self.handshake_headers
        request = [("GET %s HTTP/1.1" % self.resource).encode('utf-8')]
        for header, value in headers:
            request.append(("%s: %s" % (header, value)).encode('utf-8'))
        request.append(b'\r\n')

        return b'\r\n'.join(request)

    def process_response_line(self, response_line):
        """
        Ensure that we received a HTTP `101` status code in
        response to our request and if not raises :exc:`HandshakeError`.
        """
        protocol, code, status = response_line.split(b' ', 2)
        if code != b'101':
            raise HandshakeError(
                "Invalid response status for %s: %s %s" %
                    (self.url, code, status))

    def process_handshake_header(self, headers):
        """
        Read the upgrade handshake's response headers and
        validate them against :rfc:`6455`.
        """
        protocols = []
        extensions = []

        headers = headers.strip()

        for header_line in headers.split(b'\r\n'):
            header, value = header_line.split(b':', 1)
            header = header.strip().lower()
            value = value.strip().lower()

            if header == b'upgrade' and value != b'websocket':
                raise HandshakeError("Invalid Upgrade header: %s" % value)

            elif header == b'connection' and value != b'upgrade':
                raise HandshakeError("Invalid Connection header: %s" % value)

            elif header == b'sec-websocket-accept':
                match = b64encode(sha1(self.key + WS_KEY).digest())
                if value != match.lower():
                    raise HandshakeError("Invalid challenge response: %s" % value)

            elif header == b'sec-websocket-protocol':
                protocols = ','.join(value)

            elif header == b'sec-websocket-extensions':
                extensions = ','.join(value)

        return protocols, extensions

    def handshake_ok(self):
        self.opened()
