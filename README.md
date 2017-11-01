Python SDK for Satori RTM
-------------------------

RTM is the realtime messaging service at the core of the
[Satori platform](https://www.satori.com).

Python SDK makes it more convenient to use Satori RTM
from [Python programming language](https://www.python.org).

# Installation

```
pip install satori-rtm-sdk
```

Secure WebSocket communication (``wss://``) is supported natively
for Python 2.7.9+ and PyPy 2.6+ only.

## Optional dependencies

### backports.ssl

If the SDK installation step detects Python older than 2.7.9 without secure
TLS socket implementation (For example CentOS 7 has Python 2.7.5), it installs
the secure replacement [backports.ssl][1]. Beware that it requires
OpenSSL library, Python development headers and a C compiler to be available.

This should work on CentOS 7:

```
yum install -y epel-release
yum install -y python-pip gcc python-devel openssl-devel
pip install satori-rtm-sdk
```

[1]: https://pypi.python.org/pypi/backports.ssl

### rapidjson

The SDK will take advantage of [python-rapidjson][2] for faster json processing
if it's installed.

[2]: https://pypi.python.org/pypi/python-rapidjson

### wsaccel

There are most two notable CPU intensive routines in websocket communication:
UTF-8 validation and payload masking. Fortunately there exists the
[wsaccel package][3] that provides optimized versions of said routines.

To enable the SDK to use wsaccel, use the following code:

```
import satori.rtm.connection
satori.rtm.connection.enable_wsaccel()
```

[3]: https://pypi.python.org/pypi/wsaccel

# String situation

Python has two string types: binary (like `b'foo'`) and unicode (like `u'bar'`).
Python 2 treats string literals like `'hello'` as binary while Python 3 considers
these unicode.

The SDK can talk to RTM using either JSON or CBOR protocol. JSON standard has
only unicode strings while CBOR supports both unicode and binary.

All this means that there are four kinds of clients: Py2+JSON, Py3+JSON, Py2+CBOR and Py3+CBOR.
As the publisher and the subscriber are usually different clients, it
means that there are 16 combinations of (publisher kind * subscriber kind).
In order to keep it simple, use a rule of thumb: use binary data only if
both publisher and subscriber are using CBOR protocol.

It's also important point that binary strings are not supported as dictionary keys.
Be sure to use unicode in both messages, like `{u"who": u"zebra"}` and API values, like
`subscribe(u"animals", ... args={u"filter": u"select ..."})` and `{u"history": {u"age": 42}}`.

# Documentation

You can view the latest SDK documentation
[here](https://www.satori.com/docs/rtm-sdks/overview).

# Using https proxy

The SDK supports working through an https (not http) proxy.

When constructing a client using the `Client` constructor or
the `make_client` context manager, add a keyword argument
`https_proxy=(host, port)` like this:

```
with make_client(endpoint, appkey, https_proxy=('127.0.0.1', 4443)) as client:
    print('Connected to Satori RTM through a proxy')
```

# Logging

The SDK uses the standard `logging` module using namespaces `satori.rtm` and
`miniws4py`. If you're writing an application using this SDK, be sure to configure
logging, the simplest way is to do the following at the startup of your application:

```
import logging
logging.basicConfig()
```

If you're writing a library, the best practice is not to configure logging at
all, leaving that for the applications.

# Development

## Development dependencies

There more build-time dependencies than runtime dependencies.
In order to work on satori-rtm-sdk development, you need:

 * [State Machine Compiler (SMC)][4]
    to convert state machines description into Python source code
 * [tox][5]
    to run tests using all supported Python interpreters in separate sandboxes.
 * [pytest][6] (recommended)
    the tests themselves are written only unittest module from stdlib, but using pytest as a runner is more convenient
 * [hypothesis][7]
    used in property tests

[4]: http://smc.sourceforge.net/
[5]: https://tox.readthedocs.org/en/latest/
[6]: https://docs.pytest.org/en/latest/
[7]: https://hypothesis.readthedocs.io/en/latest/

## Running Tests

Almost all tests are run against real Satori RTM service. The tests require
`credentials.json` file to be populated with RTM credentials. It must include
the following key-value pairs:

```
{
  "endpoint": "YOUR_ENDPOINT",
  "appkey": "YOUR_APPKEY",
  "auth_role_name": "YOUR_ROLE",
  "auth_role_secret_key": "YOUR_SECRET",
  "auth_restricted_channel": "YOUR_RESTRICTED_CHANNEL"
}
```

* `endpoint` is your customer-specific DNS name for RTM access.
* `appkey` is your application key.
* `auth_role_name` is a role name that permits publishing / subscribing to `auth_restricted_channel`. Must be not `default`.
* `auth_role_secret_key` is a secret key for `auth_role_name`.
* `auth_restricted_channel` is a channel with subscribe and publish access for `auth_role_name` role only.

You must use [Dev Portal](https://developer.satori.com/) to create the role and set channel permissions.

After setting up `credentials.json`, run SDK tests with the following commands:

```
export SMC_JAR=/path/to/Smc.jar
tox -e py27-test
```

Substitute `py27` with one of `pypy`, `py34` or `py35` to choose a
desired Python implementation.
