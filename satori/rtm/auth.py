
r'''

satori.rtm.auth
===============

You can perform role-based authentication with the Python SDK. This method
uses a role and role secret key from the Dev Portal and authenticates a
client session with that role.

The operations that the client can perform depend
on the permissions for the role.

The role-based authentication method is a two-step authentication process
based on the HMAC process, using the MD5 hashing routine:

* The client obtains a nonce from the server in a handshake request.
* The client then sends an authorization request with its role secret key
  hashed with the received nonce.

Use the provided class `satori.rtm.auth.RoleSecretAuthDelegate` to
create a delegate (that knows the authentication process) and use the
delegate with the authenticate(role_auth_delegate, auth_callback) method of the
`satori.rtm.client.Client` or `satori.rtm.connection.Connection` class. The SDK
calls `auth_callback` on the response from RTM.

2. Custom authentication.
    You must manually create the delegate to use with this method.

For more information, see
*Authentication and Authorization* in the online docs.


 .. note:: Automatic reauthentication can be disable by passing
           'restore_auth_on_reconnect=False' to Client constructor or
           to make_client.


Use the client or connection authenticate method with the authentication
delegate and a callback to process the RTM response to the authentication
request::

  secret_key = '<ROLE_SECRET_KEY>'

  with sc.make_client(
          endpoint=endpoint,
          appkey=platform_appkey) as client:

      role_auth_delegate = auth.RoleSecretAuthDelegate(\
          '<USER_ROLE>', secret_key)

      auth_ack = threading.Event()

      def auth_callback(auth_result):
          if type(auth_result) == auth.Done:
              print('Auth success')
              auth_ack.set()
          else:
              print('Auth failure: {0}'.format(auth_result))
              auth_ack.set()

      client.authenticate(role_auth_delegate, auth_callback)
      if not auth_ack.wait(10):
          raise RuntimeError('No authentication reply in reasonable time')

'''


from __future__ import print_function
from collections import namedtuple as t
import base64
import hashlib
import hmac

Authenticate = t('Authenticate', ['method', 'credentials', 'callback'])
AuthenticateOK = t('AuthenticateOK', [])
Handshake = t('Handshake', ['method', 'data', 'callback'])
HandshakeOK = t('HandshakeOK', ['data'])
Done = t('Done', [])
Error = t('Error', ['message'])


class AuthDelegate(object):
    def start(self):
        return Done()


class RoleSecretAuthDelegate(AuthDelegate):
    def __init__(self, role, role_secret):
        self.role = role
        if isinstance(role_secret, bytes):
            self.role_secret = role_secret
        else:
            self.role_secret = role_secret.encode('utf8')

    def start(self):
        method = 'role_secret'

        def after_handshake(reply):
            if type(reply) == Error:
                return reply

            assert type(reply) == HandshakeOK

            if 'nonce' not in reply.data:
                return Error('No nonce in handshake reply')

            nonce = reply.data['nonce'].encode('utf8')

            binary_hash = hmac.new(
                self.role_secret, nonce, hashlib.md5).digest()
            ascii_hash = base64.b64encode(binary_hash)

            return Authenticate(
                method,
                {'hash': ascii_hash.decode('ascii')},
                after_authenticate)

        def after_authenticate(reply):
            if type(reply) == Error:
                return reply

            assert type(reply) == AuthenticateOK

            return Done()

        return Handshake(method, {'role': self.role}, after_handshake)
