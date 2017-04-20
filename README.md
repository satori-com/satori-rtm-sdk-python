# Satori RTM SDK for Python

Use the Satori RTM SDK for Python to create server-based applications
that use RTM to publish and subscribe.

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

# Documentation

You can view the latest Python SDK documentation
[here](https://www.satori.com/docs/client-libraries/python).

# Development

## Development dependencies

There more build-time dependencies than runtime dependencies.
In order to work on satori-rtm-sdk development, you need:

 * [State Machine Compiler (SMC)][4]
    to convert state machines description into Python source code
 * [tox][5]
    to run tests using all supported Python interpreters in separate sandboxes.

[4]: http://smc.sourceforge.net/
[5]: https://tox.readthedocs.org/en/latest/

## Running Tests

Tests require an active Satori to be available. The tests require `credentials.json` 
to be populated with the Satori properties.

The `credentials.json` file must include the following key-value pairs:

```
{ 
  "endpoint": "ws://<SATORI_HOST>/",
  "appkey": "my_appkey",
  "auth_role_name": "ROLE NAME"
  "auth_role_secret_key": "ROLE SECRET"
  "auth_restricted_channel": "RESTRICTED CHANNEL"
}
```

* `endpoint` is your customer-specific DNS name for RTM access.
* `appkey` is your application key.
* `auth_role_name` is a role name that permits publishing / subscribing to `auth_restricted_channel`. Must be not `default`.
* `auth_role_secret_key` is a secret key for `auth_role_name`.
* `auth_restricted_channel` is a channel with subscribe and publish access for `auth_role_name` role only.

You must use [DevPortal](https://developer.satori.com/) to create role and set channel permissions.

After setting up `credentials.json`, run SDK tests with the following commands:

```
export SMC_JAR=/path/to/Smc.jar
tox -e py27-test
```

Substitute `py27` with one of `pypy`, `py34` or `py35` to choose a
desired Python implementation.
