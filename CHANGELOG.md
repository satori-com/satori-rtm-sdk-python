v1.5.0 (2017-09-21)
-------------------

* Added support for binary RTM protocol.
  Enable by passing protocol='cbor' to make_client, Client or Connection constructors

v1.4.0 (2017-08-21)
-------------------

* satori.rtm.logger module is now internal. Client code should access the logger
  object as `logging.getLogger('satori.rtm')` for configuration. If in doubt,
  configure logging at the startup of your application like this:
  ```
  import logging
  logging.basicConfig()
  ```

v1.3.0 (2017-08-15)
-------------------

* Serialize messages before publishing to avoid issues with mutable messages
* All callbacks (state changes, subscription data and errors, request replies) are now called from a single thread.
* Client object now stops when any user callback throws an exception

v1.2.1 (2017-06-23)
-------------------

* Propagate subscribe error reason into SubscriptionObserver.on_enter_failed callback

v1.2 (2017-06-13)
-----------------

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
