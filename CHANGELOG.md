Unreleased
----------

* Clearer error message for invalid endpoint
* Preserve subscriptions over the course of `client.stop() >> client.start()` sequence.
  This change unifies behavior with other Satori RTM SDKs

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
