Unreleased
----------

* Added https proxy support (no authentication)

v1.0.4 (2017-05-08)
-------------------

* Rename to satori-rtm-sdk
* Unhardcode role name for tests

v1.0.3 (2017-04-21)
-------------------

* Made error message for invalid endpoint clearer
* Added optional parameter auth_delegate to make_client function for easier
  authentication
* Fixed docstring in logger module
* Subscriptions are now preserved over the course of
  `client.stop() >> client.start()` sequence.
  This change unifies behavior with other Satori RTM SDKs
* Introduced AuthError exception class (this class is a subclass of
  RuntimeException so it's a backward compatible change)
* Fixed curses_chat example
* Authentication is now repeated on reconnects by default (was opt-in earlier,
  now opt-out)

v1.0.2 (2017-03-24)
-------------------

* Fixed double call of `opened()` that could lead to spurious reconnects
* No longer require users to install backports.ssl and PyOpenSSL manually for
  older Python versions

v1.0.1 (2017-03-14)
-------------------

* Added support for secure websockets with CPython 2.7.0 - 2.7.8
* Fixed RoleSecretAuthDelegate name in docstrings about authentication
* Fixed random failure to autoreconnect in satori.rtm.client

v1.0.0 (2017-03-07)
-------------------
* Initial release
