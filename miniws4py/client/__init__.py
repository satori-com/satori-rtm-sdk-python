# -*- coding: utf-8 -*-
from base64 import b64encode
import certifi
from hashlib import sha1
import logging
import os
import socket
import sys

from miniws4py import WS_KEY, WS_VERSION
from miniws4py.exc import HandshakeError
from miniws4py.websocket import WebSocket
from miniws4py.compat import urlsplit

__all__ = ['WebSocketBaseClient']

doubleCRLF = b'\r\n\r\n'
logger = logging.getLogger('miniws4py')

class WebSocketBaseClient(WebSocket):
    def __init__(self, url, protocols=None, extensions=None,
                 ssl_options=None, headers=None, proxy=None):
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
        self.proxy = proxy

        self._parse_url()

        # Let's handle IPv4 and IPv6 addresses
        # Simplified from CherryPy's code
        try:
            if self.proxy:
                host, port = self.proxy
            else:
                host, port = (self.host, self.port)
            family, socktype, proto, canonname, sa = socket.getaddrinfo(
                host, port,
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
        try:
            self.sock.settimeout(300)

            if self.scheme == "wss" and not self.proxy:
                self.sock = _ssl_wrap_socket(self.sock, self.host)
                self.sock.connect(self.bind_addr)
            elif self.scheme == "wss" and self.proxy:
                self.sock.connect(self.proxy)
                _send_http_connect(self.sock, self.host, self.port)
                self.sock = _ssl_wrap_socket(self.sock, self.host)
            else:
                self.sock.connect(self.bind_addr)

            self._write(self.handshake_request)

            try:
                code, status, headers, body = _read_http_response(self.sock)
                if code != b'101':
                    raise HandshakeError(
                        "Invalid response status for %s: %s %s" %
                            (self.url, code, status))
                self.protocols, self.extensions =\
                    self.process_handshake_header(headers)
            except HandshakeError:
                self.close_connection()
                raise

            if body:
                self.process(body)
        except Exception as e:
            logger.exception(e)
            try:
                if self.sock:
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

def _send_http_connect(sock, host, port):
    connect_header = "CONNECT {0}:{1} HTTP/1.0{2}".format(
        host, port, doubleCRLF)

    sock.send(connect_header)

    code, status, headers, body = _read_http_response(sock)

    if code != b'200':
        raise HandshakeError(
            "HTTP CONNECT to proxy failed: {0} {1}".format(code, status))

    return sock

def _read_http_response(sock):
    response = b''
    while True:
        bytes_ = sock.recv(128, 0)
        if not bytes_:
            break
        response += bytes_
        if doubleCRLF in response:
            break

    if not response:
        raise HandshakeError("No response")

    headers, _, body = response.partition(doubleCRLF)
    response_line, _, headers = headers.partition(b'\r\n')
    _protocol, code, status = response_line.split(b' ', 2)

    return code, status, headers, body

def _ssl_wrap_socket(sock, host):
    if sys.version_info < (2, 7, 9):
        if sys.version_info >= (2, 7, 0):
            try:
                import backports.ssl
            except ImportError:
                raise RuntimeError(
                    "In order to use secure websockets with "
                    "Python 2.7.8 and earlier please install "
                    " the backports.ssl package.")
            try:
                import OpenSSL
                assert OpenSSL
            except ImportError:
                raise RuntimeError(
                    "Please make sure PyOpenSSL >= 0.15 is installed")

            try:
                openssl_version = OpenSSL.__version__
                from distutils.version import LooseVersion
                assert LooseVersion(openssl_version) >= LooseVersion('0.15.0')
            except Exception:
                raise RuntimeError(
                    "Please make sure that PyOpenSSL version is"
                    "at least 0.15, found only {0}".format(openssl_version))

            ctx = backports.ssl.SSLContext(backports.ssl.PROTOCOL_SSLv23)
            ctx.verify_mode = backports.ssl.CERT_REQUIRED
            ctx.check_hostname = True
            ctx.ca_file = certifi.where()

        else:
            raise RuntimeError("Python 2.6 is not supported")
    else:
        import ssl
        ctx = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cafile=certifi.where())

    return ctx.wrap_socket(sock, server_hostname=host)
